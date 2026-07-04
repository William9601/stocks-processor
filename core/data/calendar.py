"""US-equity session calendar: true close times and phantom-bar filtering.

Half-day sessions (13:00 ET close: July 3rd, day after Thanksgiving, Christmas
Eve, ...) break two assumptions baked into naive RTH handling:

1. Vendor 5-minute files can carry bars stamped after the early close, built
   from after-hours prints (verified in the on-hand Alpaca SIP parquet:
   2018-07-03, 2024-11-29, 2024-12-24 run all the way to a 16:00 stamp with
   collapsing volume). A backtest that "fills MOC" on those bars is filling on
   a phantom print. :func:`filter_to_sessions` drops them at load.
2. A strategy that hardcodes 15:55/16:00 decision times skips half-day entries
   and can strand orders. :func:`session_closes` gives the true close per
   session so decision times can be *offsets from the close* instead.

The authority is the XNYS exchange calendar (``exchange_calendars``) — session
close times are published schedule, not price data, so consulting today's
close time is calendar knowledge, never lookahead. Dates the calendar does not
recognize (synthetic test data on holidays, non-US symbols) fall back to the
last bar actually present on that date.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache

import pandas as pd

from core.strategy import ET


@lru_cache(maxsize=1)
def _xnys():
    import exchange_calendars as xcals

    return xcals.get_calendar("XNYS", start="2015-01-01")


def session_close_et(day: date) -> pd.Timestamp | None:
    """Official close (ET) of the session on ``day``; None if not a session."""
    cal = _xnys()
    ts = pd.Timestamp(day)
    try:
        if not cal.is_session(ts):
            return None
        return cal.session_close(ts).tz_convert(ET)
    except Exception:  # date outside the calendar's range
        return None


def session_closes(et_index: pd.DatetimeIndex) -> dict[date, pd.Timestamp]:
    """True close (ET) per session date present in ``et_index``.

    Exchange-calendar close when the date is a known XNYS session; otherwise
    the last bar of that date (synthetic or non-XNYS data).
    """
    frame = pd.Series(et_index, index=et_index.date)
    last_bar = frame.groupby(level=0).max()
    return {
        d: (session_close_et(d) or last_bar[d])
        for d in last_bar.index
    }


def filter_to_sessions(bars: pd.DataFrame) -> pd.DataFrame:
    """Drop bars stamped after their session's official close.

    Applies only to dates the XNYS calendar recognizes as sessions; bars on
    unrecognized dates are kept as-is (synthetic data / other markets).
    """
    if bars.empty:
        return bars
    et_index = bars.index.tz_convert(ET)
    closes = {d: session_close_et(d) for d in set(et_index.date)}
    keep = [
        (c := closes[d]) is None or ts <= c
        for d, ts in zip(et_index.date, et_index, strict=True)
    ]
    return bars[keep]
