"""Backtest: event-driven engine, cost model, metrics.

The engine is a thin event loop (ADR 0002) rather than a vectorized library:
the ``on_bar(ctx) -> [Order]`` contract is inherently event-driven, and
keeping the loop explicit is what makes the no-lookahead guarantee auditable.
"""

from core.backtest.costs import CostModel
from core.backtest.engine import BacktestEngine, BacktestResult
from core.backtest.metrics import compute_metrics

__all__ = ["CostModel", "BacktestEngine", "BacktestResult", "compute_metrics"]
