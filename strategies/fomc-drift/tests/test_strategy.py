"""fomc-drift signal tests: fixed daily-bar sequences -> exact MOC fills.

Runs end-to-end through the real engine/broker on real XNYS session dates
(bars stamped at their true session close, as the re-stamped production parquet
is) so the asserted fills exercise the daily-bar NEXT_CLOSE path exactly as a
backtest does. The off-by-one that matters — BUY decided on T-2 fills at
close(T-1); SELL decided on T-1 fills at close(T) — is asserted directly.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from core.backtest.costs import CostModel
from core.backtest.engine import BacktestEngine
from core.data.calendar import session_close_et
from core.data.feed import DataFeed
from core.loader import load_strategy
from core.risk.sizing import RiskLimits, RiskManager
from core.strategy import Side

# Load via the path-based loader (unique module name per strategy dir), never
# `from strategy import build` — that registers a bare ``strategy`` module and
# collides with orb's identically-named test import under full-suite collection.
STRAT_DIR = Path(__file__).resolve().parents[1]

ET = "America/New_York"

# Real XNYS sessions around the 2018-06-13 (Wed) FOMC announcement.
#   T-2 = 2018-06-11 (Mon), T-1 = 2018-06-12 (Tue), T = 2018-06-13 (Wed)
# A few leading sessions give the strategy some (sub-window) history.
DAYS = [
    ("2018-06-06", 500.0, 501.0, 499.0, 500.0),
    ("2018-06-07", 500.0, 502.0, 499.5, 501.0),
    ("2018-06-08", 501.0, 503.0, 500.5, 502.0),
    ("2018-06-11", 502.0, 504.0, 501.5, 503.0),  # T-2: BUY decided here
    ("2018-06-12", 503.0, 505.0, 502.5, 504.0),  # T-1: BUY fills at this close
    ("2018-06-13", 504.0, 506.0, 503.5, 505.0),  # T  : SELL fills at this close
    ("2018-06-14", 505.0, 507.0, 504.5, 506.0),
]


def _daily_bars(rows: list[tuple[str, float, float, float, float]]) -> pd.DataFrame:
    """Daily bars stamped at each date's true session close (16:00 ET)."""
    idx = pd.DatetimeIndex(
        [session_close_et(pd.Timestamp(d).date()) for d, *_ in rows]
    ).tz_convert("UTC")
    df = pd.DataFrame(
        [(o, h, lo, c, 1e6) for _, o, h, lo, c in rows],
        index=idx,
        columns=["open", "high", "low", "close", "volume"],
    )
    df.index.name = "ts"
    return df


def _calendar(tmp_path: Path, rows: list[tuple[str, str, str, bool]]) -> Path:
    """Write a fixture FOMC calendar CSV (start, end/T, type, press_conf)."""
    df = pd.DataFrame(
        [(s, e, t, pc, "fixture") for s, e, t, pc in rows],
        columns=["start_date", "end_date", "type", "press_conference", "source_note"],
    )
    path = tmp_path / "fomc_calendar_fixture.csv"
    df.to_csv(path, index=False)
    return path


def _run(bars: pd.DataFrame, calendar: Path, costs: CostModel | None = None) -> BacktestEngine:
    engine = BacktestEngine(
        load_strategy(STRAT_DIR, {"calendar_source": str(calendar)}),
        DataFeed("SPY", bars),
        RiskManager(RiskLimits(risk_per_trade=0.005, max_drawdown=0.05, halt_on_drawdown=False)),
        costs or CostModel(0.0, 0.0, 0.0, 0.0),
    )
    engine.run()
    return engine


def _close_ts(d: str) -> pd.Timestamp:
    return session_close_et(pd.Timestamp(d).date()).tz_convert("UTC")


def test_one_event_entry_at_close_Tm1_exit_at_close_T():
    cal = None
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        cal = _calendar(Path(td), [("2018-06-13", "2018-06-13", "scheduled", True)])
        eng = _run(_daily_bars(DAYS), cal)

    assert len(eng.broker.trades) == 1
    t = eng.broker.trades[0]
    assert t.side is Side.LONG
    # BUY decided on T-2 (2018-06-11) fills at close(T-1) = 2018-06-12 close.
    assert t.entry_time == _close_ts("2018-06-12")
    assert t.entry_price == 504.0
    # SELL decided on T-1 fills at close(T) = 2018-06-13 close.
    assert t.exit_time == _close_ts("2018-06-13")
    assert t.exit_price == 505.0
    assert t.exit_reason == "fomc_exit"


def test_no_lookahead_entry_is_not_close_Tm2():
    """The BUY must never fill on the bar it was decided on (T-2)."""
    with __import__("tempfile").TemporaryDirectory() as td:
        cal = _calendar(Path(td), [("2018-06-13", "2018-06-13", "scheduled", True)])
        eng = _run(_daily_bars(DAYS), cal)
    t = eng.broker.trades[0]
    assert t.entry_price != 503.0  # close(T-2) — would mean a same-bar fill
    assert t.entry_time != _close_ts("2018-06-11")


def test_scheduled_only_conference_call_and_cancelled_never_trade():
    with __import__("tempfile").TemporaryDirectory() as td:
        cal = _calendar(
            Path(td),
            [
                ("2018-06-13", "2018-06-13", "conference_call", False),
                ("2018-06-13", "2018-06-13", "cancelled", False),
            ],
        )
        eng = _run(_daily_bars(DAYS), cal)
    assert eng.broker.trades == []
    assert eng.broker.fills == []


def test_no_event_in_window_means_no_trades():
    with __import__("tempfile").TemporaryDirectory() as td:
        # A scheduled meeting far outside the bar window.
        cal = _calendar(Path(td), [("2020-01-29", "2020-01-29", "scheduled", True)])
        eng = _run(_daily_bars(DAYS), cal)
    assert eng.broker.trades == []


def test_costs_push_entry_up_and_exit_down():
    """2.0 bps round trip (0.5 half-spread + 0.5 close-slippage per side)."""
    costs = CostModel(commission_per_unit=0.0, half_spread_bps=0.5, slippage_bps=0.5,
                      stop_slippage_bps=1.0, close_slippage_bps=0.5)
    with __import__("tempfile").TemporaryDirectory() as td:
        cal = _calendar(Path(td), [("2018-06-13", "2018-06-13", "scheduled", True)])
        eng = _run(_daily_bars(DAYS), cal, costs=costs)
    t = eng.broker.trades[0]
    # Both legs are MOC (close) fills: buy pays +1.0 bps, sell receives -1.0 bps.
    assert t.entry_price == pytest.approx(504.0 * (1 + 1.0e-4), rel=0, abs=1e-9)
    assert t.exit_price == pytest.approx(505.0 * (1 - 1.0e-4), rel=0, abs=1e-9)


def test_one_position_at_a_time_and_flat_after_exit():
    with __import__("tempfile").TemporaryDirectory() as td:
        cal = _calendar(Path(td), [("2018-06-13", "2018-06-13", "scheduled", True)])
        eng = _run(_daily_bars(DAYS), cal)
    # Exactly one round trip; the book ends flat.
    assert len(eng.broker.trades) == 1
    assert eng.broker.position().is_flat
