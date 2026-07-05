"""Risk limits: the 2*R daily-loss lock must fire for sparse-order strategies.

The historical bug: RiskManager only saw equity inside size(), which runs on
order-emitting bars. For an overnight strategy the morning CLOSE realizes the
overnight loss *before* the afternoon entry sizes, so day-start equity was
captured post-loss and the daily lock never fired. The fix anchors each day at
the prior session's closing equity via an every-bar on_bar() hook.
"""

from __future__ import annotations

import pandas as pd

from core.risk.sizing import RiskLimits, RiskManager
from core.strategy import Action, Context, Order, Position


def _ctx(ts_et: str, equity: float) -> Context:
    ts = pd.Timestamp(ts_et, tz="America/New_York").tz_convert("UTC")
    hist = pd.DataFrame(
        {"open": [300.0], "high": [300.0], "low": [300.0], "close": [300.0], "volume": [1e6]},
        index=pd.DatetimeIndex([ts], name="ts"),
    )
    return Context("QQQ", hist, Position(), cash=equity, equity=equity)


def _entry() -> Order:
    return Order(Action.ENTER_LONG, stop_distance=15.0, resting_stop=False)


def test_overnight_gap_loss_trips_daily_lock():
    rm = RiskManager(RiskLimits(risk_per_trade=0.005, daily_loss_limit_r=2.0))
    # Day 1: flat equity through the close.
    rm.on_bar(_ctx("2024-06-03 15:40", 100_000.0))
    rm.on_bar(_ctx("2024-06-03 16:00", 100_000.0))
    # Day 2: the morning exit realized a -1.2% overnight gap (> 2R = 1.0%).
    rm.on_bar(_ctx("2024-06-04 09:35", 98_800.0))
    # The afternoon entry must be vetoed.
    assert rm.size(_entry(), _ctx("2024-06-04 15:40", 98_800.0), ref_price=300.0) is None
    # Day 3 rolls the lock: entries are allowed again.
    assert rm.size(_entry(), _ctx("2024-06-05 15:40", 98_800.0), ref_price=300.0) is not None


def test_lock_fires_even_when_risk_only_sees_order_bars():
    """The sparse path (size() only) also works: the day anchors at the prior
    day's last observed equity, so the morning-exit loss is visible."""
    rm = RiskManager(RiskLimits(risk_per_trade=0.005, daily_loss_limit_r=2.0))
    # Day 1: the only risk touchpoint is sizing the 15:40 entry.
    assert rm.size(_entry(), _ctx("2024-06-03 15:40", 100_000.0), ref_price=300.0) is not None
    # Day 2 morning: the CLOSE order passes through size() after the gap loss.
    close = Order(Action.CLOSE)
    assert rm.size(close, _ctx("2024-06-04 09:35", 98_800.0), ref_price=296.0) is close
    # Day 2 afternoon: entry vetoed — loss measured from day-1 equity.
    assert rm.size(_entry(), _ctx("2024-06-04 15:40", 98_800.0), ref_price=300.0) is None


def test_drawdown_kill_switch_halts_by_default_but_not_in_measurement_mode():
    # -20% from peak trips the switch under the default 15% limit. The daily
    # loss cap is parked out of the way so only the kill switch is in play.
    rm = RiskManager(RiskLimits(max_drawdown=0.15, daily_loss_limit_r=1e9))
    rm.on_bar(_ctx("2024-06-03 10:00", 100_000.0))
    rm.on_bar(_ctx("2024-06-03 15:40", 80_000.0))
    assert rm.halted
    assert rm.size(_entry(), _ctx("2024-06-03 15:45", 80_000.0), ref_price=300.0) is None

    # Measurement mode: the switch still trips (reported) but entries continue,
    # so a backtest can measure the true drawdown its criterion judges.
    rm2 = RiskManager(
        RiskLimits(max_drawdown=0.15, halt_on_drawdown=False, daily_loss_limit_r=1e9)
    )
    rm2.on_bar(_ctx("2024-06-03 10:00", 100_000.0))
    rm2.on_bar(_ctx("2024-06-03 15:40", 80_000.0))
    assert rm2.halted  # still set: it is reported, just not entry-vetoing
    assert rm2.size(_entry(), _ctx("2024-06-03 15:45", 80_000.0), ref_price=300.0) is not None


def test_small_overnight_loss_does_not_lock():
    rm = RiskManager(RiskLimits(risk_per_trade=0.005, daily_loss_limit_r=2.0))
    rm.on_bar(_ctx("2024-06-03 16:00", 100_000.0))
    rm.on_bar(_ctx("2024-06-04 09:35", 99_500.0))  # -0.5% < 2R
    assert rm.size(_entry(), _ctx("2024-06-04 15:40", 99_500.0), ref_price=300.0) is not None
