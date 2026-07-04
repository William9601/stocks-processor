"""Session calendar: half-day closes, phantom-bar filtering, fallbacks."""

from __future__ import annotations

from datetime import date, time

import numpy as np
import pandas as pd

from core.data.calendar import filter_to_sessions, session_close_et, session_closes


def _bars(day: str, start="09:35", end="16:00") -> pd.DataFrame:
    idx = pd.date_range(f"{day} {start}", f"{day} {end}", freq="5min",
                        tz="America/New_York").tz_convert("UTC")
    n = len(idx)
    px = np.linspace(300.0, 301.0, n)
    df = pd.DataFrame({"open": px, "high": px + 0.1, "low": px - 0.1,
                       "close": px, "volume": np.full(n, 1e5)}, index=idx)
    df.index.name = "ts"
    return df


def test_session_close_et_knows_half_days():
    assert session_close_et(date(2024, 11, 29)).time() == time(13, 0)
    assert session_close_et(date(2018, 7, 3)).time() == time(13, 0)
    assert session_close_et(date(2024, 6, 3)).time() == time(16, 0)
    assert session_close_et(date(2024, 6, 1)) is None  # Saturday


def test_filter_drops_phantom_half_day_bars():
    # Half-day carrying after-hours bars all the way to a 16:00 stamp
    # (the pattern verified in the on-hand parquet: 2018-07-03, 2024-11-29...).
    bars = _bars("2024-11-29")
    out = filter_to_sessions(bars)
    et = out.index.tz_convert("America/New_York")
    assert et[-1].time() == time(13, 0)
    assert len(out) < len(bars)


def test_filter_keeps_full_sessions_untouched():
    bars = _bars("2024-06-03")
    out = filter_to_sessions(bars)
    assert out.equals(bars)


def test_filter_keeps_unrecognized_dates():
    # Synthetic data on a holiday: not an XNYS session, kept as-is.
    bars = _bars("2020-01-01")
    assert filter_to_sessions(bars).equals(bars)


def test_session_closes_calendar_and_fallback():
    bars = pd.concat([_bars("2024-11-29"), _bars("2020-01-01", end="15:30")])
    closes = session_closes(bars.index.tz_convert("America/New_York"))
    assert closes[date(2024, 11, 29)].time() == time(13, 0)  # calendar wins
    assert closes[date(2020, 1, 1)].time() == time(15, 30)  # last-bar fallback
