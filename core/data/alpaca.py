"""Normalize Alpaca bar data into the core's canonical schema.

Two Alpaca-specific things are handled here, in one place used by both the
historical fetch (`scripts/fetch_data.py`) and the live broker
(`core/execution/paper.py`):

1. **Timestamp convention.** Alpaca stamps a bar with its *open* time (a 5-min
   bar at 09:30 covers [09:30, 09:35)). The core treats the index as the bar's
   *close* time (so "the 10:00 bar" is the one ending at 10:00). We shift open
   -> close by adding the bar duration.
2. **Regular trading hours.** Alpaca can return extended-hours bars; the
   strategy's session logic (session open, 10:00, 15:00, 15:55) assumes RTH
   only, so we keep 09:35..16:00 ET (close-stamped) bars.
"""

from __future__ import annotations

from datetime import time

import pandas as pd

from core.data.feed import load_bars
from core.strategy import ET

RTH_OPEN = time(9, 30)
RTH_CLOSE = time(16, 0)


def bars_to_canonical(
    df: pd.DataFrame, symbol: str, bar_minutes: int = 5, timestamp: str = "open"
) -> pd.DataFrame:
    """Alpaca bars DataFrame (`.df`) -> canonical UTC/OHLCV, close-stamped."""
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.index, pd.MultiIndex):
        df = df.xs(symbol, level=0)
    df = df.reset_index().rename(columns={"timestamp": "ts"})
    ts = pd.to_datetime(df["ts"], utc=True)
    if timestamp == "open":
        ts = ts + pd.Timedelta(minutes=bar_minutes)  # open-stamp -> close-stamp
    df["ts"] = ts
    return load_bars(df[["ts", "open", "high", "low", "close", "volume"]])


def filter_rth(bars: pd.DataFrame) -> pd.DataFrame:
    """Keep only close-stamped RTH bars (09:35..16:00 ET)."""
    if bars.empty:
        return bars
    et = bars.index.tz_convert(ET).time
    mask = [(RTH_OPEN < t) & (t <= RTH_CLOSE) for t in et]
    return bars[mask]
