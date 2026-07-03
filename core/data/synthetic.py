"""Synthetic intraday bars for tests and pre-data demos.

This is NOT market data and must never stand in for a real backtest result.
It exists so the engine, strategy, and metrics can be exercised end-to-end
before a real provider (Alpaca live / a historical vendor) is wired in.

``make_intraday_bars`` can optionally inject a *market-intraday-momentum*
signal (afternoon return correlated with the morning return) so tests can
assert the strategy actually earns on days it should.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.strategy import ET

RTH_START = "09:30"
RTH_END = "16:00"


def _session_index(day: pd.Timestamp, freq_min: int) -> pd.DatetimeIndex:
    """Bar *close* timestamps for one RTH session, as tz-aware UTC."""
    start = pd.Timestamp(f"{day.date()} {RTH_START}", tz=ET) + pd.Timedelta(minutes=freq_min)
    end = pd.Timestamp(f"{day.date()} {RTH_END}", tz=ET)
    idx = pd.date_range(start, end, freq=f"{freq_min}min", tz=ET)
    return idx.tz_convert("UTC")


def make_intraday_bars(
    symbol: str = "SPY",
    start: str = "2020-01-01",
    days: int = 60,
    freq_min: int = 5,
    price0: float = 300.0,
    seed: int = 7,
    momentum: float = 0.0,
) -> pd.DataFrame:
    """Generate ``days`` weekday RTH sessions of ``freq_min`` bars.

    ``momentum`` in [0, 1] scales how strongly the afternoon drift follows the
    morning return; 0 = pure noise (no edge), higher = a cleaner MIM signal.
    """
    rng = np.random.default_rng(seed)
    bar_sigma = 0.0009  # per-bar return stdev, ~SPY 5-min

    frames = []
    price = price0
    day = pd.Timestamp(start, tz=ET).normalize()
    made = 0
    while made < days:
        if day.weekday() < 5:  # weekdays only
            idx = _session_index(day, freq_min)
            n = len(idx)
            rets = rng.normal(0, bar_sigma, n)

            # Morning window = first 30 minutes worth of bars.
            n_ref = max(1, 30 // freq_min)
            morning_ret = rets[:n_ref].sum()
            # Inject afternoon drift in the direction of the morning move.
            aft = slice(n - n_ref, n)
            rets[aft] += momentum * morning_ret / n_ref

            closes = price * np.cumprod(1 + rets)
            opens = np.empty(n)
            opens[0] = price
            opens[1:] = closes[:-1]
            wig = np.abs(rng.normal(0, bar_sigma, n)) * closes
            highs = np.maximum(opens, closes) + wig
            lows = np.minimum(opens, closes) - wig
            vol = rng.integers(50_000, 200_000, n).astype(float)

            frames.append(
                pd.DataFrame(
                    {"open": opens, "high": highs, "low": lows, "close": closes, "volume": vol},
                    index=idx,
                )
            )
            price = closes[-1]
            made += 1
        day += pd.Timedelta(days=1)

    bars = pd.concat(frames)
    bars.index.name = "ts"
    bars.attrs["symbol"] = symbol
    return bars
