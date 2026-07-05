"""orb signal-logic tests: fixed bar sequences -> exact entries/exits/stops.

Runs end-to-end through the real engine/broker so the asserted fills exercise
the locked intrabar-stop semantics, the EoD open fill, and the skip rules
exactly as a backtest would. Real XNYS dates so the session calendar applies
(including the 2024-07-03 13:00 ET early close).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

from core.backtest.costs import CostModel
from core.backtest.engine import BacktestEngine
from core.data.feed import DataFeed
from core.risk.sizing import RiskLimits, RiskManager
from core.strategy import Side

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from strategy import build  # noqa: E402

ET = "America/New_York"

# A clean up-day: bar 1 is directional long (C1 > O1), stop would sit at 499.5.
UP_DAY = [
    ("09:35", 500.0, 501.0, 499.5, 500.8),
    ("09:40", 500.9, 502.0, 500.5, 501.5),
    ("15:55", 504.0, 505.0, 503.5, 504.5),
    ("16:00", 504.6, 505.0, 504.0, 504.8),
]


def _bars(day: str, rows: list[tuple[str, float, float, float, float]]) -> pd.DataFrame:
    idx = pd.DatetimeIndex(
        [pd.Timestamp(f"{day} {hhmm}", tz=ET) for hhmm, *_ in rows]
    ).tz_convert("UTC")
    df = pd.DataFrame(
        [(o, h, lo, c, 1e5) for _, o, h, lo, c in rows],
        index=idx,
        columns=["open", "high", "low", "close", "volume"],
    )
    df.index.name = "ts"
    return df


def _run(days: dict[str, list], costs: CostModel | None = None) -> BacktestEngine:
    bars = pd.concat([_bars(day, rows) for day, rows in days.items()])
    engine = BacktestEngine(
        build({}),
        DataFeed("QQQ", bars),
        RiskManager(RiskLimits(max_drawdown=0.10)),
        costs or CostModel(0.0, 0.0, 0.0, 0.0),
    )
    engine.run()
    return engine


def _stamp(day: str, hhmm: str) -> pd.Timestamp:
    return pd.Timestamp(f"{day} {hhmm}", tz=ET).tz_convert("UTC")


def test_long_entry_at_bar2_open_and_eod_exit_at_final_bar_open():
    eng = _run({"2024-06-03": UP_DAY})
    assert len(eng.broker.trades) == 1
    t = eng.broker.trades[0]
    assert t.side is Side.LONG
    assert t.entry_time == _stamp("2024-06-03", "09:40")
    assert t.entry_price == 500.9  # bar 2 open, zero costs
    assert t.exit_time == _stamp("2024-06-03", "16:00")
    assert t.exit_price == 504.6  # OPEN of the session's final bar (15:55 print)
    assert t.exit_reason == "eod_flat"


def test_short_entry_with_stop_at_bar1_high():
    day = [
        ("09:35", 500.0, 500.6, 499.0, 499.2),  # down bar -> short, stop 500.6
        ("09:40", 499.1, 499.5, 498.0, 498.5),
        ("15:55", 497.0, 497.5, 496.5, 497.0),
        ("16:00", 496.9, 497.2, 496.5, 497.0),
    ]
    eng = _run({"2024-06-03": day})
    t = eng.broker.trades[0]
    assert t.side is Side.SHORT
    assert t.entry_price == 499.1
    assert t.exit_price == 496.9
    assert t.exit_reason == "eod_flat"


def test_doji_and_zero_range_days_are_skipped():
    doji = [
        ("09:35", 500.0, 501.0, 499.0, 500.0),  # C1 == O1
        ("09:40", 500.1, 501.0, 500.0, 500.5),
        ("15:55", 502.0, 502.5, 501.5, 502.0),
        ("16:00", 502.1, 502.4, 501.9, 502.2),
    ]
    zero_range = [
        ("09:35", 500.0, 500.0, 500.0, 500.0),  # H1 == L1
        ("09:40", 500.1, 501.0, 500.0, 500.5),
        ("15:55", 502.0, 502.5, 501.5, 502.0),
        ("16:00", 502.1, 502.4, 501.9, 502.2),
    ]
    eng = _run({"2024-06-03": doji, "2024-06-04": zero_range})
    assert eng.broker.trades == []
    assert eng.broker.fills == []


def test_born_stopped_day_is_skipped():
    day = [
        ("09:35", 500.0, 501.0, 499.5, 500.8),  # long signal, stop 499.5
        ("09:40", 499.4, 500.0, 499.0, 499.8),  # O2 <= stop: born stopped out
        ("15:55", 504.0, 505.0, 503.5, 504.5),
        ("16:00", 504.6, 505.0, 504.0, 504.8),
    ]
    eng = _run({"2024-06-03": day})
    assert eng.broker.trades == []
    assert any("born_stopped" in r for _, r in eng.broker.cancels)


def test_stop_touch_fills_at_stop_price():
    day = [
        ("09:35", 500.0, 501.0, 499.5, 500.8),
        ("09:40", 500.9, 502.0, 500.5, 501.5),
        ("10:35", 500.0, 500.2, 499.3, 499.4),  # opens above 499.5, touches it
        ("15:55", 504.0, 505.0, 503.5, 504.5),
        ("16:00", 504.6, 505.0, 504.0, 504.8),
    ]
    eng = _run({"2024-06-03": day})
    t = eng.broker.trades[0]
    assert t.exit_reason == "stop"
    assert t.exit_time == _stamp("2024-06-03", "10:35")
    assert t.exit_price == 499.5  # the stop price (bar-1 low)
    assert len(eng.broker.trades) == 1  # no re-entry after the stop-out


def test_stop_gap_through_fills_at_bar_open():
    day = [
        ("09:35", 500.0, 501.0, 499.5, 500.8),
        ("09:40", 500.9, 502.0, 500.5, 501.5),
        ("10:35", 498.0, 498.5, 497.5, 498.2),  # opens through the 499.5 stop
        ("15:55", 504.0, 505.0, 503.5, 504.5),
        ("16:00", 504.6, 505.0, 504.0, 504.8),
    ]
    eng = _run({"2024-06-03": day})
    t = eng.broker.trades[0]
    assert t.exit_reason == "stop"
    assert t.exit_price == 498.0  # bar open, never the stop price


def test_stop_is_live_on_the_entry_bar_itself():
    day = [
        ("09:35", 500.0, 501.0, 499.5, 500.8),
        ("09:40", 500.9, 501.0, 499.2, 499.3),  # entry bar dips through the stop
        ("15:55", 504.0, 505.0, 503.5, 504.5),
        ("16:00", 504.6, 505.0, 504.0, 504.8),
    ]
    eng = _run({"2024-06-03": day})
    t = eng.broker.trades[0]
    assert t.exit_reason == "stop"
    assert t.exit_time == _stamp("2024-06-03", "09:40")  # same bar as the entry
    assert t.exit_price == 499.5


def test_early_close_session_exits_at_1255_print():
    # 2024-07-03 closed at 13:00 ET: the final bar is close-stamped 13:00 and
    # its open is the 12:55 print; the EoD decision moves to the 12:55 bar.
    day = [
        ("09:35", 500.0, 501.0, 499.5, 500.8),
        ("09:40", 500.9, 502.0, 500.5, 501.5),
        ("12:55", 503.0, 503.5, 502.5, 503.2),
        ("13:00", 503.3, 503.6, 503.0, 503.4),
    ]
    eng = _run({"2024-07-03": day})
    t = eng.broker.trades[0]
    assert t.exit_reason == "eod_flat"
    assert t.exit_time == _stamp("2024-07-03", "13:00")
    assert t.exit_price == 503.3  # final bar's open = the 12:55 print


def test_one_trade_per_day_two_days_trade_independently():
    eng = _run({"2024-06-03": UP_DAY, "2024-06-04": UP_DAY})
    assert len(eng.broker.trades) == 2
    days = [t.exit_time.tz_convert(ET).date().isoformat() for t in eng.broker.trades]
    assert days == ["2024-06-03", "2024-06-04"]


def test_missing_bar1_means_no_trade_that_day():
    late_start = [
        ("09:40", 500.9, 502.0, 500.5, 501.5),  # first bar of the day isn't 09:35
        ("15:55", 504.0, 505.0, 503.5, 504.5),
        ("16:00", 504.6, 505.0, 504.0, 504.8),
    ]
    eng = _run({"2024-06-03": late_start})
    assert eng.broker.trades == []


def test_gap_guard_flattens_a_position_stranded_past_its_session():
    # Day 1's data dies right after the entry (no EoD decision bar, no final
    # bar): the never-overnight guard must flatten at day 2's first open.
    # Day 2 trades entirely above the stranded stop (499.5) so the guard,
    # not the resting stop, is what closes the position.
    day1 = [
        ("09:35", 500.0, 501.0, 499.5, 500.8),
        ("09:40", 500.9, 502.0, 500.5, 501.5),
    ]
    day2 = [
        ("09:35", 502.0, 503.0, 501.5, 502.8),
        ("09:40", 502.9, 503.5, 502.0, 503.0),
        ("15:55", 504.0, 505.0, 503.5, 504.5),
        ("16:00", 504.6, 505.0, 504.0, 504.8),
    ]
    eng = _run({"2024-06-03": day1, "2024-06-04": day2})
    assert len(eng.broker.trades) == 1
    t = eng.broker.trades[0]
    assert t.exit_reason == "gap_flat_guard"
    assert t.exit_time == _stamp("2024-06-04", "09:40")
    assert eng.broker.position().is_flat


def test_locked_cost_model_applied_to_fills():
    costs = CostModel(
        commission_per_unit=0.0, half_spread_bps=0.1, slippage_bps=0.4, stop_slippage_bps=1.0
    )
    eng = _run({"2024-06-03": UP_DAY}, costs=costs)
    t = eng.broker.trades[0]
    assert abs(t.entry_price - 500.9 * (1 + 0.5 / 10_000)) < 1e-9  # 0.1 + 0.4 bps
    assert abs(t.exit_price - 504.6 * (1 - 0.5 / 10_000)) < 1e-9

    day_stopped = [
        ("09:35", 500.0, 501.0, 499.5, 500.8),
        ("09:40", 500.9, 502.0, 500.5, 501.5),
        ("10:35", 500.0, 500.2, 499.3, 499.4),
        ("15:55", 504.0, 505.0, 503.5, 504.5),
        ("16:00", 504.6, 505.0, 504.0, 504.8),
    ]
    eng2 = _run({"2024-06-03": day_stopped}, costs=costs)
    t2 = eng2.broker.trades[0]
    assert abs(t2.exit_price - 499.5 * (1 - 1.1 / 10_000)) < 1e-9  # 0.1 + 1.0 bps


def test_build_rejects_params_everything_is_pre_registered():
    with pytest.raises(ValueError, match="pre-registered"):
        build({"range_minutes": 15})
