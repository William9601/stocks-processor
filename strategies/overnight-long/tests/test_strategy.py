"""Overnight-long: gated vs ungated entry, MOC/MOO fills, never shorts."""

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
SMALL = dict(sma_window=3, overnight_vol_window=3)


def _daily_file(tmp_path: Path, closes: list[float], name="d.parquet"):
    dates = pd.date_range("2020-01-01", periods=len(closes), freq="B", tz="America/New_York")
    close = np.array(closes, dtype=float)
    open_ = np.concatenate([[close[0]], close[:-1]])
    df = pd.DataFrame(
        {"open": open_, "high": np.maximum(open_, close) + 0.5,
         "low": np.minimum(open_, close) - 0.5, "close": close,
         "volume": np.full(len(close), 1e6)},
        index=dates.tz_convert("UTC"))
    df.index.name = "ts"
    path = tmp_path / name
    df.to_parquet(path)
    return path, dates


def _strategy(daily_source: Path, **params):
    return load_strategy(STRAT_DIR, {"daily_source": str(daily_source), **SMALL, **params})


def _ctx(et_date, hhmm: str, position: Position, close=300.0, session_close=None) -> Context:
    ts = pd.Timestamp(f"{et_date} {hhmm}", tz="America/New_York").tz_convert("UTC")
    hist = pd.DataFrame(
        {"open": [close], "high": [close], "low": [close], "close": [close], "volume": [1e6]},
        index=pd.DatetimeIndex([ts], name="ts"),
    )
    extra = {}
    if session_close is not None:
        extra["session_close_et"] = pd.Timestamp(
            f"{et_date} {session_close}", tz="America/New_York"
        )
    return Context("SPY", hist, position, cash=100_000, equity=100_000, extra=extra)


def test_gated_enters_overnight_long_when_risk_on(tmp_path):
    path, dates = _daily_file(tmp_path, [100, 101, 102, 103, 104, 105, 106])
    strat = _strategy(path, use_regime_gate=True)
    d = (dates[-1] + pd.offsets.BDay(1)).date()
    orders = strat.on_bar(_ctx(d, "15:40", Position()))
    assert len(orders) == 1
    o = orders[0]
    assert o.action is Action.ENTER_LONG
    assert o.fill is FillTiming.NEXT_CLOSE
    assert o.resting_stop is False and o.stop_distance > 0


def test_gated_sits_out_when_risk_off(tmp_path):
    path, dates = _daily_file(tmp_path, [106, 105, 104, 103, 102, 101, 100])  # downtrend
    strat = _strategy(path, use_regime_gate=True)
    d = (dates[-1] + pd.offsets.BDay(1)).date()
    assert strat.on_bar(_ctx(d, "15:40", Position())) == []


def test_ungated_holds_even_when_below_sma(tmp_path):
    path, dates = _daily_file(tmp_path, [106, 105, 104, 103, 102, 101, 100])  # downtrend
    strat = _strategy(path, use_regime_gate=False)  # hold every night
    d = (dates[-1] + pd.offsets.BDay(1)).date()
    orders = strat.on_bar(_ctx(d, "15:40", Position()))
    assert len(orders) == 1 and orders[0].action is Action.ENTER_LONG


def test_exits_at_open_and_never_shorts(tmp_path):
    path, dates = _daily_file(tmp_path, [100, 101, 102, 103, 104, 105, 106])
    strat = _strategy(path, use_regime_gate=True)
    d = (dates[-1] + pd.offsets.BDay(1)).date()
    long_pos = Position(side=Side.LONG, qty=10, avg_price=300.0)
    orders = strat.on_bar(_ctx(d, "16:00", long_pos))
    # Exit the overnight long at the open — and only that. No short leg.
    assert [o.action for o in orders] == [Action.CLOSE]
    assert orders[0].fill is FillTiming.NEXT_OPEN


def test_half_day_decisions_offset_from_early_close(tmp_path):
    """On a 13:00 close the decision bar is 12:40 and the exit bar 13:00 —
    nothing fires at the full-day 15:40/16:00 times."""
    path, dates = _daily_file(tmp_path, [100, 101, 102, 103, 104, 105, 106])
    strat = _strategy(path, use_regime_gate=True)
    d = (dates[-1] + pd.offsets.BDay(1)).date()

    orders = strat.on_bar(_ctx(d, "12:40", Position(), session_close="13:00"))
    assert len(orders) == 1 and orders[0].action is Action.ENTER_LONG

    long_pos = Position(side=Side.LONG, qty=10, avg_price=300.0)
    orders = strat.on_bar(_ctx(d, "13:00", long_pos, session_close="13:00"))
    assert [o.action for o in orders] == [Action.CLOSE]

    # The full-day times are dead on a half-day (those bars would be phantom).
    assert strat.on_bar(_ctx(d, "15:40", Position(), session_close="13:00")) == []
    assert strat.on_bar(_ctx(d, "16:00", long_pos, session_close="13:00")) == []


def test_integration_only_long_trades_span_overnight(tmp_path):
    dates = pd.bdate_range("2020-02-03", periods=12)
    frames = []
    for i, day in enumerate([d.date() for d in dates]):
        idx = pd.date_range(f"{day} 09:35", f"{day} 16:00", freq="5min",
                            tz="America/New_York").tz_convert("UTC")
        n = len(idx)
        start = 300.0 + i
        close = np.linspace(start, start + 0.5, n)
        open_ = np.concatenate([[start - 0.2], close[:-1]])
        frames.append(pd.DataFrame(
            {"open": open_, "high": np.maximum(open_, close) + 0.1,
             "low": np.minimum(open_, close) - 0.1, "close": close,
             "volume": np.full(n, 1e5)}, index=idx))
    bars = pd.concat(frames)
    bars.index.name = "ts"

    ddates = pd.bdate_range("2020-01-20", periods=25, tz="America/New_York")
    closes = list(300.0 + np.arange(25) * 1.0)
    ddf = pd.DataFrame({"open": [closes[0]] + closes[:-1],
                        "high": [c + 0.5 for c in closes], "low": [c - 0.5 for c in closes],
                        "close": closes, "volume": [1e6] * 25}, index=ddates.tz_convert("UTC"))
    ddf.index.name = "ts"
    dpath = tmp_path / "spy_daily.parquet"
    ddf.to_parquet(dpath)

    strat = _strategy(dpath, use_regime_gate=True)
    engine = BacktestEngine(strat, DataFeed("SPY", bars), RiskManager(RiskLimits()),
                            CostModel(close_slippage_bps=2.0, slippage_bps=3.0))
    engine.run()
    trades = engine.broker.trades
    assert len(trades) > 3
    assert all(t.side is Side.LONG for t in trades)  # never shorts
    # Every real trade is an overnight hold (different ET entry/exit dates). The
    # final position is force-flatted at end-of-series (no next open), so exclude it.
    held = [t for t in trades if t.exit_reason != "eod_flat"]
    assert held and all(
        t.entry_time.tz_convert("America/New_York").date()
        != t.exit_time.tz_convert("America/New_York").date()
        for t in held
    )
