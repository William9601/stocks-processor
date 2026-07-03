"""LiveRunner loop tests, driven by a fake broker (no Alpaca dependency).

These cover the logic that is the same in paper and live: one action per
completed bar, entry -> market + protective stop, time-exit -> cancel + close,
and risk veto. The Alpaca wiring itself (paper.py) is a thin shell smoke-tested
separately with real credentials.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.execution.live_runner import LiveRunner
from core.loader import load_strategy
from core.risk.sizing import RiskLimits, RiskManager
from core.strategy import Position, Side

STRAT_DIR = "strategies/intraday-momentum"


def _up_day(date="2020-06-01"):
    idx = pd.date_range(f"{date} 09:35", f"{date} 16:00", freq="5min", tz="America/New_York")
    idx = idx.tz_convert("UTC")
    n = len(idx)
    close = np.linspace(300.0, 303.0, n)
    open_ = np.empty(n)
    open_[0] = 299.9
    open_[1:] = close[:-1]
    high = np.maximum(open_, close) + 0.05
    low = np.minimum(open_, close) - 0.05
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close,
         "volume": np.full(n, 1e5)}, index=idx
    )


class FakeBroker:
    """Serves a prebuilt day up to a moving 'now' and records order calls."""

    def __init__(self, day: pd.DataFrame):
        self.day = day
        self._position = Position()
        self.calls: list[tuple] = []
        self._oid = 0

    def recent_bars(self, symbol, start, end):
        return self.day[self.day.index <= end]

    def account(self):
        return 100_000.0, 100_000.0

    def position(self, symbol):
        return self._position

    def submit_market(self, symbol, qty, is_buy):
        self._oid += 1
        self.calls.append(("market", qty, is_buy))
        # Simulate the resulting position for subsequent polls.
        self._position = Position(
            side=Side.LONG if is_buy else Side.SHORT, qty=qty, avg_price=302.0
        )
        return f"o{self._oid}"

    def wait_fill(self, order_id, timeout=30.0):
        return 302.0

    def submit_stop(self, symbol, qty, is_buy, stop_price):
        self._oid += 1
        self.calls.append(("stop", qty, is_buy, round(stop_price, 2)))
        return f"o{self._oid}"

    def cancel(self, order_id):
        self.calls.append(("cancel", order_id))

    def close_position(self, symbol):
        self.calls.append(("close",))
        self._position = Position()


def _runner(broker, **params):
    strat = load_strategy(STRAT_DIR, {"k": 0.0, **params})
    return LiveRunner(strat, RiskManager(RiskLimits()), broker, "SPY")


def test_only_acts_on_new_completed_bars():
    day = _up_day()
    broker = FakeBroker(day)
    runner = _runner(broker)
    ts = day.index[3]
    assert runner.poll_once(ts) is True   # first sight of this bar
    assert runner.poll_once(ts) is False  # same bar again -> no action


def test_entry_places_market_then_protective_stop():
    day = _up_day()
    broker = FakeBroker(day)
    runner = _runner(broker)
    decision = day.tz_convert("America/New_York")
    ts_15 = decision.index[decision.index.time == pd.Timestamp("15:00").time()][0]
    runner.poll_once(ts_15.tz_convert("UTC"))

    kinds = [c[0] for c in broker.calls]
    assert "market" in kinds and "stop" in kinds
    market = next(c for c in broker.calls if c[0] == "market")
    stop = next(c for c in broker.calls if c[0] == "stop")
    assert market[2] is True          # bought (up morning -> long)
    assert stop[2] is False           # protective sell-stop
    assert stop[3] < 302.0            # stop below entry for a long


def test_time_exit_cancels_stop_and_closes():
    day = _up_day()
    broker = FakeBroker(day)
    runner = _runner(broker)
    et = day.tz_convert("America/New_York")
    ts_15 = et.index[et.index.time == pd.Timestamp("15:00").time()][0]
    ts_1555 = et.index[et.index.time == pd.Timestamp("15:55").time()][0]
    runner.poll_once(ts_15.tz_convert("UTC"))
    runner.poll_once(ts_1555.tz_convert("UTC"))

    kinds = [c[0] for c in broker.calls]
    assert "cancel" in kinds and "close" in kinds


def test_risk_veto_blocks_order(monkeypatch):
    day = _up_day()
    broker = FakeBroker(day)
    strat = load_strategy(STRAT_DIR, {"k": 0.0})
    # Force sizing to veto everything.
    risk = RiskManager(RiskLimits())
    monkeypatch.setattr(risk, "size", lambda *a, **k: None)
    runner = LiveRunner(strat, risk, broker, "SPY")
    et = day.tz_convert("America/New_York")
    ts_15 = et.index[et.index.time == pd.Timestamp("15:00").time()][0]
    runner.poll_once(ts_15.tz_convert("UTC"))
    assert broker.calls == []
