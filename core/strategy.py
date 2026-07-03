"""The Strategy contract and the point-in-time types strategies see.

Lookahead prevention lives in the interface, not only in review: a strategy is
handed a :class:`Context` that exposes bars *up to and including* the current
one and nothing after it. There is structurally no way to read a future bar.

Strategies emit :class:`Order` *intents*; they never size positions or place
trades. ``core.risk`` sizes and vetoes, ``core.execution`` fills.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

import pandas as pd

ET = "America/New_York"

# Canonical OHLCV column names used everywhere in the core.
BAR_COLUMNS = ["open", "high", "low", "close", "volume"]


class Action(Enum):
    """A strategy's intent for a bar. Sizing and fills happen downstream."""

    ENTER_LONG = "enter_long"
    ENTER_SHORT = "enter_short"
    CLOSE = "close"


class FillTiming(Enum):
    """When a queued order fills, relative to the bar after it was submitted.

    Orders never fill on the bar they were decided on. ``NEXT_OPEN`` fills at
    the open of the following bar (a market-on-open / next-open fill — the
    original and only behavior); ``NEXT_CLOSE`` fills at the *close* of the
    following bar (a market-on-close fill — the decision is committed on the
    prior bar's close, strictly before the fill print). See broker/engine.
    """

    NEXT_OPEN = "next_open"
    NEXT_CLOSE = "next_close"


@dataclass
class Order:
    """An order *intent* emitted by a strategy.

    ``qty`` is left ``None`` by the strategy and filled in by ``core.risk``.
    For :attr:`Action.CLOSE` the executor closes the full open position, so
    ``qty`` is ignored. ``stop_distance`` (price points) is required on entries:
    ``core.risk`` uses it to size the position. When ``resting_stop`` is true the
    broker also places a protective stop that far from the actual fill price;
    when false, ``stop_distance`` is a *sizing basis only* and no stop is placed
    (used by positions that cannot be stopped, e.g. an overnight hold while the
    market is closed). ``fill`` selects the fill timing (see :class:`FillTiming`).
    """

    action: Action
    stop_distance: float | None = None
    qty: float | None = None
    tag: str = ""
    fill: FillTiming = FillTiming.NEXT_OPEN
    resting_stop: bool = True


class Side(Enum):
    LONG = 1
    SHORT = -1


@dataclass
class Position:
    """The current open position. ``qty == 0`` means flat."""

    side: Side | None = None
    qty: float = 0.0
    avg_price: float = 0.0
    stop_price: float | None = None

    @property
    def is_flat(self) -> bool:
        return self.qty == 0.0


@dataclass
class Context:
    """Everything a strategy may see at one bar — and nothing from the future.

    ``history`` is a DataFrame indexed by tz-aware UTC timestamp with the
    :data:`BAR_COLUMNS`, sliced to end at the current bar. ``now`` is the close
    timestamp of the current (last) bar.
    """

    symbol: str
    history: pd.DataFrame
    position: Position
    cash: float
    equity: float
    extra: dict = field(default_factory=dict)

    @property
    def now(self) -> pd.Timestamp:
        """Close timestamp of the current bar (tz-aware UTC)."""
        return self.history.index[-1]

    @property
    def now_et(self) -> pd.Timestamp:
        """Current bar close in US Eastern time (session-relative logic)."""
        return self.now.tz_convert(ET)

    def today_et(self) -> pd.DataFrame:
        """Bars belonging to the current ET session date, in ET-indexed form."""
        et = self.history.tz_convert(ET)
        return et[et.index.date == self.now_et.date()]


class Strategy(Protocol):
    """The one method every strategy implements.

    Called once per bar with a point-in-time :class:`Context`. Returns a list
    of :class:`Order` intents (empty list = do nothing). Strategies may hold
    internal per-day state but must derive all market information from ``ctx``.
    """

    def on_bar(self, ctx: Context) -> list[Order]: ...
