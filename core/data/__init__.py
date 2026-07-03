"""Market data: a single DataFeed API and the canonical bar schema.

``core.data`` owns the schema (tz-aware UTC index, OHLCV columns) so that
swapping data providers never touches strategies.
"""

from core.data.feed import DataFeed, load_bars

__all__ = ["DataFeed", "load_bars"]
