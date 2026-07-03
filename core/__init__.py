"""Shared trading core: data, backtest, risk, execution.

Strategies are thin plugins that implement the ``Strategy`` contract in
``core.strategy`` and run through this identical machinery, so performance
differences are attributable to the strategy, not the harness.
"""
