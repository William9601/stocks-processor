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


@dataclass
class Order:
    """An order *intent* emitted by a strategy.

    ``qty`` is left ``None`` by the strategy and filled in by ``core.risk``.
    For :attr:`Action.CLOSE` the executor closes the full open position, so
    ``qty`` is ignored. ``stop_distance`` (price points) is required on entries:
    ``core.risk`` uses it to size the position, and the broker places a
    protective stop that far from the actual fill price.
    """

    action: Action
    stop_distance: float | None = None
    qty: float | None = None
    tag: str = ""


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
