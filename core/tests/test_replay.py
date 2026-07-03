"""ReplayBroker + simulate: the live loop over canned days behaves sanely."""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.backtest.costs import CostModel
from core.execution.live_runner import LiveRunner
from core.execution.replay import ReplayBroker, simulate
from core.loader import load_strategy
from core.risk.sizing import RiskLimits, RiskManager
from core.strategy import ET, Side

STRAT_DIR = "strategies/intraday-momentum"


def _day(closes, date="2024-03-15"):
    idx = pd.date_range(f"{date} 09:35", f"{date} 16:00", freq="5min", tz=ET).tz_convert("UTC")
    n = len(idx)
    closes = np.asarray(closes, float)
    open_ = np.empty(n)
    open_[0] = closes[0]
    open_[1:] = closes[:-1]
    high = np.maximum(open_, closes) + 0.05
    low = np.minimum(open_, closes) - 0.05
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": closes, "volume": np.full(n, 1e5)},
        index=idx,
    )


def _run(bars, **params):
    strat = load_strategy(STRAT_DIR, {"k": 0.2, **params})
    broker = ReplayBroker("SPY", bars, 100_000.0, CostModel())
    runner = LiveRunner(strat, RiskManager(RiskLimits()), broker, "SPY")
    trades = simulate(runner, broker)
    return broker, trades


def test_up_day_makes_one_winning_long_flat_by_close():
    n = len(pd.date_range("2024-03-15 09:35", "2024-03-15 16:00", freq="5min"))
    broker, trades = _run(_day(np.linspace(300.0, 303.0, n)))
    assert len(trades) == 1
    assert trades[0].side is Side.LONG
    assert trades[0].net_pnl > 0
    assert broker._pos_qty == 0.0  # flat at close


def test_down_day_makes_one_winning_short():
    n = len(pd.date_range("2024-03-15 09:35", "2024-03-15 16:00", freq="5min"))
    broker, trades = _run(_day(np.linspace(300.0, 297.0, n)))
    assert len(trades) == 1
    assert trades[0].side is Side.SHORT
    assert trades[0].net_pnl > 0


def test_reversal_day_stops_out_the_long():
    idx = pd.date_range("2024-03-15 09:35", "2024-03-15 16:00", freq="5min")
    n = len(idx)
    closes = np.linspace(300.0, 301.0, n)
    entry_i = int(np.where(idx.time == pd.Timestamp("15:00").time())[0][0])
    closes[entry_i:] = np.linspace(301.0, 296.5, n - entry_i)
    broker, trades = _run(_day(closes))
    assert len(trades) == 1
    assert trades[0].side is Side.LONG
    assert trades[0].exit_reason == "stop"
    assert trades[0].net_pnl < 0  # a stop-out on a reversal is a loss
