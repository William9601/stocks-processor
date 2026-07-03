"""Overnight-drift: regime gate, MOC/MOO leg emission, causal daily lookup."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from core.backtest.costs import CostModel
from core.backtest.engine import BacktestEngine
from core.data.feed import DataFeed
from core.loader import load_strategy
from core.risk.sizing import RiskLimits, RiskManager
from core.strategy import Action, Context, FillTiming, Position, Side

STRAT_DIR = Path(__file__).resolve().parents[1]

# Small indicator windows so a handful of synthetic daily bars are enough.
SMALL = dict(sma_window=3, atr_window=3, overnight_vol_window=3)


def _daily_file(tmp_path: Path, closes: list[float], name="d.parquet") -> Path:
    """Write a synthetic daily OHLCV parquet (UTC-indexed) from a close path."""
    dates = pd.date_range("2020-01-01", periods=len(closes), freq="B", tz="America/New_York")
    close = np.array(closes, dtype=float)
    open_ = np.concatenate([[close[0]], close[:-1]])  # open = prior close (flat overnight)
    df = pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) + 0.5,
            "low": np.minimum(open_, close) - 0.5,
            "close": close,
            "volume": np.full(len(close), 1e6),
        },
        index=dates.tz_convert("UTC"),
    )
    df.index.name = "ts"
    path = tmp_path / name
    df.to_parquet(path)
    return path, dates


def _strategy(daily_source: Path, **params):
    return load_strategy(STRAT_DIR, {"daily_source": str(daily_source), **SMALL, **params})


def _ctx(et_date, hhmm: str, position: Position, close=300.0) -> Context:
    ts = pd.Timestamp(f"{et_date} {hhmm}", tz="America/New_York").tz_convert("UTC")
    hist = pd.DataFrame(
        {"open": [close], "high": [close], "low": [close], "close": [close], "volume": [1e6]},
        index=pd.DatetimeIndex([ts], name="ts"),
    )
    return Context("SPY", hist, position, cash=100_000, equity=100_000)


def test_risk_on_enters_overnight_long_moc(tmp_path):
    path, dates = _daily_file(tmp_path, [100, 101, 102, 103, 104, 105, 106])  # steady uptrend
    strat = _strategy(path)
    # A session date after enough daily history for the 3-day SMA.
    d = (dates[-1] + pd.offsets.BDay(1)).date()
    orders = strat.on_bar(_ctx(d, "15:55", Position()))  # flat at the close decision
    assert len(orders) == 1
    o = orders[0]
    assert o.action is Action.ENTER_LONG
    assert o.fill is FillTiming.NEXT_CLOSE
    assert o.resting_stop is False  # cannot stop overnight
    assert o.stop_distance > 0  # gap-budget sizing basis


def test_risk_off_blocks_overnight_long(tmp_path):
    path, dates = _daily_file(tmp_path, [106, 105, 104, 103, 102, 101, 100])  # downtrend
    strat = _strategy(path)
    d = (dates[-1] + pd.offsets.BDay(1)).date()
    assert strat.on_bar(_ctx(d, "15:55", Position())) == []  # flat + regime off -> nothing


def test_close_bar_flips_long_to_intraday_short(tmp_path):
    path, dates = _daily_file(tmp_path, [100, 101, 102, 103, 104, 105, 106])
    strat = _strategy(path)
    d = (dates[-1] + pd.offsets.BDay(1)).date()
    long_pos = Position(side=Side.LONG, qty=10, avg_price=300.0)
    orders = strat.on_bar(_ctx(d, "16:00", long_pos))
    assert [o.action for o in orders] == [Action.CLOSE, Action.ENTER_SHORT]
    assert orders[0].fill is FillTiming.NEXT_OPEN  # exit overnight at the open
    assert orders[1].fill is FillTiming.NEXT_OPEN  # enter short at the same open
    assert orders[1].resting_stop is True  # intraday leg carries a real stop


def test_short_is_covered_at_close_even_when_regime_off(tmp_path):
    path, dates = _daily_file(tmp_path, [106, 105, 104, 103, 102, 101, 100])  # regime off
    strat = _strategy(path)
    d = (dates[-1] + pd.offsets.BDay(1)).date()
    short_pos = Position(side=Side.SHORT, qty=10, avg_price=300.0)
    orders = strat.on_bar(_ctx(d, "15:55", short_pos))
    # Flat-by-close is unconditional; no new overnight long in a risk-off regime.
    assert [o.action for o in orders] == [Action.CLOSE]
    assert orders[0].fill is FillTiming.NEXT_CLOSE


def test_no_action_outside_decision_bars(tmp_path):
    path, dates = _daily_file(tmp_path, [100, 101, 102, 103, 104, 105, 106])
    strat = _strategy(path)
    d = (dates[-1] + pd.offsets.BDay(1)).date()
    assert strat.on_bar(_ctx(d, "12:00", Position())) == []


def test_daily_lookup_is_causal(tmp_path):
    """The regime uses only daily rows strictly before the session date."""
    # Uptrend then a sharp drop on the LAST daily date. If the strategy peeked at
    # the same-date row the regime could differ; using the prior row it stays on.
    path, dates = _daily_file(tmp_path, [100, 101, 102, 103, 104, 105, 106])
    strat = _strategy(path)
    # Session on the same ET date as the last daily bar -> must use the PRIOR day.
    same_day = dates[-1].date()
    orders = strat.on_bar(_ctx(same_day, "15:55", Position()))
    # Prior rows are a clean uptrend -> risk-on -> an overnight long is scheduled.
    assert len(orders) == 1 and orders[0].action is Action.ENTER_LONG


# --- integration: a multi-day run actually cycles the two legs ---

def _sessions(dates_et) -> pd.DataFrame:
    """RTH 5-min bars over several sessions with a mild uptrend (regime-on)."""
    frames = []
    base = 300.0
    for i, day in enumerate(dates_et):
        idx = pd.date_range(f"{day} 09:35", f"{day} 16:00", freq="5min",
                            tz="America/New_York").tz_convert("UTC")
        n = len(idx)
        start = base + i * 1.0
        close = np.linspace(start, start + 0.5, n)
        open_ = np.concatenate([[start - 0.2], close[:-1]])
        frames.append(pd.DataFrame(
            {"open": open_, "high": np.maximum(open_, close) + 0.1,
             "low": np.minimum(open_, close) - 0.1, "close": close,
             "volume": np.full(n, 1e5)}, index=idx))
    bars = pd.concat(frames)
    bars.index.name = "ts"
    return bars


def test_integration_cycles_overnight_and_intraday_legs(tmp_path):
    dates = pd.bdate_range("2020-02-03", periods=12)
    bars = _sessions([d.date() for d in dates])
    # Daily file: steady uptrend covering (and preceding) the intraday dates.
    daily_dates = pd.bdate_range("2020-01-20", periods=25, tz="America/New_York")
    closes = list(300.0 + np.arange(25) * 1.0)
    ddf = pd.DataFrame({
        "open": [closes[0]] + closes[:-1],
        "high": [c + 0.5 for c in closes], "low": [c - 0.5 for c in closes],
        "close": closes, "volume": [1e6] * 25,
    }, index=daily_dates.tz_convert("UTC"))
    ddf.index.name = "ts"
    dpath = tmp_path / "spy_daily.parquet"
    ddf.to_parquet(dpath)

    strat = _strategy(dpath)
    feed = DataFeed("SPY", bars)
    engine = BacktestEngine(strat, feed, RiskManager(RiskLimits()),
                            CostModel(close_slippage_bps=2.0, slippage_bps=3.0))
    engine.run()

    trades = engine.broker.trades
    assert len(trades) > 4
    sides = {t.side for t in trades}
    assert Side.LONG in sides and Side.SHORT in sides  # both legs fired
    # Overnight longs span a session boundary; intraday shorts stay within a day.
    longs = [t for t in trades if t.side is Side.LONG]
    assert any(
        t.entry_time.tz_convert("America/New_York").date()
        != t.exit_time.tz_convert("America/New_York").date()
        for t in longs
    )
