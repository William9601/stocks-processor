"""Alpaca bar ingest: open->close timestamp shift and RTH filtering.

Testable without alpaca-py by faking the shape of Alpaca's ``.df`` (a
(symbol, timestamp) MultiIndex, timestamps at the bar *open*, including some
pre-market bars that must be dropped).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.data.alpaca import bars_to_canonical, filter_rth
from core.strategy import BAR_COLUMNS, ET


def _fake_alpaca_df(date="2024-03-15"):
    # Open-stamped 5-min bars from 09:00 ET (pre-market) through 15:55 ET (last RTH open).
    opens_et = pd.date_range(f"{date} 09:00", f"{date} 15:55", freq="5min", tz=ET)
    ts = opens_et.tz_convert("UTC")
    n = len(ts)
    idx = pd.MultiIndex.from_arrays([["SPY"] * n, ts], names=["symbol", "timestamp"])
    rng = np.arange(n, dtype=float)
    return pd.DataFrame(
        {
            "open": 300 + rng * 0.01,
            "high": 300 + rng * 0.01 + 0.05,
            "low": 300 + rng * 0.01 - 0.05,
            "close": 300 + rng * 0.01 + 0.02,
            "volume": 1e5 + rng,
            "trade_count": 10 + rng,
            "vwap": 300 + rng * 0.01,
        },
        index=idx,
    )


def test_open_stamps_are_shifted_to_close_stamps():
    canonical = bars_to_canonical(_fake_alpaca_df(), "SPY", bar_minutes=5, timestamp="open")
    assert list(canonical.columns) == BAR_COLUMNS
    assert canonical.index.tz is not None
    # First open at 09:00 ET -> first close-stamp at 09:05 ET.
    first_et = canonical.index[0].tz_convert(ET)
    assert first_et.strftime("%H:%M") == "09:05"


def test_filter_rth_keeps_0935_to_1600_only():
    canonical = bars_to_canonical(_fake_alpaca_df(), "SPY", bar_minutes=5, timestamp="open")
    rth = filter_rth(canonical)
    et = rth.index.tz_convert(ET)
    assert et.time.min().strftime("%H:%M") == "09:35"  # first RTH close
    assert et.time.max().strftime("%H:%M") == "16:00"  # last RTH close
    assert len(rth) == 78  # a full 5-min RTH session


def test_empty_input_returns_empty():
    assert bars_to_canonical(pd.DataFrame(), "SPY").empty
