"""DataFeed: load intraday bars into the canonical schema.

Canonical schema: a pandas DataFrame indexed by a tz-aware UTC DatetimeIndex
named ``ts``, with float columns ``open, high, low, close, volume``. The index
is the bar *close* time and must be sorted and unique.

Providers (Alpaca, Polygon, Databento, CSV/parquet cache) are adapted *into*
this schema here, so nothing downstream depends on a vendor's quirks.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.strategy import BAR_COLUMNS


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce a raw bar frame into the canonical schema (UTC index, OHLCV)."""
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]

    # Locate the timestamp column and make it the index.
    if not isinstance(df.index, pd.DatetimeIndex):
        ts_col = next(
            (c for c in ("ts", "timestamp", "time", "datetime", "date") if c in df.columns),
            None,
        )
        if ts_col is None:
            raise ValueError("No timestamp column found (expected one of ts/timestamp/time).")
        df = df.set_index(ts_col)

    idx = pd.DatetimeIndex(pd.to_datetime(df.index, utc=True), name="ts")
    df.index = idx

    missing = [c for c in BAR_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Bars missing required columns: {missing}")

    df = df[BAR_COLUMNS].astype(float)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df


def load_bars(source: str | Path | pd.DataFrame) -> pd.DataFrame:
    """Load bars from a parquet/CSV path or an in-memory DataFrame."""
    if isinstance(source, pd.DataFrame):
        return _normalize(source)
    path = Path(source)
    if path.suffix in (".parquet", ".pq"):
        raw = pd.read_parquet(path)
    elif path.suffix == ".csv":
        raw = pd.read_csv(path)
    else:
        raise ValueError(f"Unsupported bar file type: {path.suffix}")
    return _normalize(raw)


class DataFeed:
    """Point-in-time iterator over bars for one symbol.

    Holds the full history internally but only ever *yields* a Context-ready
    slice ending at the current bar, so the engine cannot accidentally look
    ahead.
    """

    def __init__(self, symbol: str, bars: pd.DataFrame):
        self.symbol = symbol
        self.bars = _normalize(bars) if not _is_canonical(bars) else bars

    @classmethod
    def from_source(cls, symbol: str, source: str | Path | pd.DataFrame) -> DataFeed:
        return cls(symbol, load_bars(source))

    def between(self, start: str | None, end: str | None) -> DataFeed:
        """Restrict to a [start, end] date range (inclusive), UTC-aware."""
        bars = self.bars
        if start is not None:
            bars = bars[bars.index >= pd.Timestamp(start, tz="UTC")]
        if end is not None:
            # end date inclusive: bump to end-of-day
            end_ts = pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)
            bars = bars[bars.index < end_ts]
        return DataFeed(self.symbol, bars)

    def __len__(self) -> int:
        return len(self.bars)


def _is_canonical(df: pd.DataFrame) -> bool:
    return (
        isinstance(df.index, pd.DatetimeIndex)
        and df.index.tz is not None
        and list(df.columns) == BAR_COLUMNS
    )
