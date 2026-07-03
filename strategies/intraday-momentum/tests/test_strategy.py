"""Intraday-momentum signal, gate, and direction behavior."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from core.backtest.costs import CostModel
from core.backtest.engine import BacktestEngine
from core.data.feed import DataFeed
from core.data.synthetic import make_intraday_bars
from core.loader import load_strategy
from core.risk.sizing import RiskLimits, RiskManager
from core.strategy import Action, Context, Position

STRAT_DIR = Path(__file__).resolve().parents[1]


def _strategy(**params):
    return load_strategy(STRAT_DIR, params)


def _one_day_up(date="2020-06-01"):
    """A handcrafted RTH session: strong up morning, drifting afternoon."""
    idx = pd.date_range(f"{date} 09:35", f"{date} 16:00", freq="5min", tz="America/New_York")
    idx = idx.tz_convert("UTC")
    n = len(idx)
    close = np.linspace(300.0, 303.0, n)  # steady rise all day
    open_ = np.empty(n)
    open_[0] = 299.9
    open_[1:] = close[:-1]
    high = np.maximum(open_, close) + 0.05
    low = np.minimum(open_, close) - 0.05
    vol = np.full(n, 100_000.0)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": vol}, index=idx
    )


def test_enters_long_on_up_morning():
    bars = _one_day_up()
    strat = _strategy(k=0.0)  # gate off: always trade on a nonzero morning
    # Feed the strategy bars up to the 15:00 decision and check the intent.
    et = bars.tz_convert("America/New_York")
    decision_ts = et.index[et.index.time == pd.Timestamp("15:00").time()][0]
    hist = bars.loc[:decision_ts.tz_convert("UTC")]
    ctx = Context("SPY", hist, Position(), cash=100_000, equity=100_000)
    orders = strat.on_bar(ctx)
    assert len(orders) == 1
    assert orders[0].action is Action.ENTER_LONG
    assert orders[0].stop_distance > 0


def test_high_threshold_blocks_trade():
    bars = _one_day_up()
    strat = _strategy(k=100.0)  # absurd gate: never passes
    feed = DataFeed("SPY", bars)
    engine = BacktestEngine(strat, feed, RiskManager(), CostModel())
    engine.run()
    assert engine.broker.trades == []


def test_full_backtest_on_momentum_data_trades_and_profits():
    bars = make_intraday_bars(days=120, momentum=0.8, seed=3)
    feed = DataFeed("SPY", bars)
    strat = _strategy(k=0.3)
    engine = BacktestEngine(strat, feed, RiskManager(RiskLimits()), CostModel())
    result = engine.run()

    assert result.metrics["trade_count"] > 10
    # With a strong injected MIM signal, net-of-cost return should be positive.
    assert result.metrics["net_return"] > 0
    # Both directions should occur over many days.
    sides = {t.side for t in engine.broker.trades}
    assert len(sides) == 2


def test_flat_by_close_every_day():
    bars = make_intraday_bars(days=30, momentum=0.5, seed=1)
    feed = DataFeed("SPY", bars)
    engine = BacktestEngine(_strategy(k=0.2), feed, RiskManager(), CostModel())
    engine.run()
    # No trade may span more than one ET calendar date.
    for t in engine.broker.trades:
        entry_day = t.entry_time.tz_convert("America/New_York").date()
        exit_day = t.exit_time.tz_convert("America/New_York").date()
        assert entry_day == exit_day
