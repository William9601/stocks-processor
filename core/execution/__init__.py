"""Execution: broker abstraction. BacktestBroker now, PaperBroker (Alpaca) next.

Both implement the same fill/position interface so a strategy runs identically
in backtest and paper trading — the only thing that changes is which broker the
runner constructs.
"""

from core.execution.broker import BacktestBroker, Fill, Trade
from core.execution.live_runner import LiveBroker, LiveRunner

__all__ = ["BacktestBroker", "Fill", "Trade", "LiveBroker", "LiveRunner"]
