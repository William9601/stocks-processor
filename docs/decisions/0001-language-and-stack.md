# ADR 0001: Python + uv monorepo

- **Date**: 2026-07-03
- **Status**: accepted

## Decision

Python ≥3.12 for everything, dependencies and workspace managed with `uv`, single
monorepo with a shared `core/` and per-strategy packages.

## Why

- Python has the deepest ecosystem for market data, backtesting, and analysis
  (pandas/polars, vectorbt, broker SDKs), and it's what AI assistants generate most
  reliably in this domain.
- Day trading at bar-level frequency (minutes, not microseconds) doesn't need a
  low-latency language. If a strategy ever needs sub-second execution, that's a new
  ADR, not a rewrite.
- Monorepo over repo-per-strategy: strategies must share the exact same data, cost,
  and risk code for comparisons to mean anything, and AI agents work best when the
  whole system is in one context.

## Alternatives rejected

- **Rust/C++ core**: premature; latency isn't the bottleneck at this frequency.
- **Repo per strategy**: guarantees drift between backtest harnesses, making
  cross-strategy comparison unreliable — which defeats the project's purpose.

## Deferred decisions (future ADRs)

- 0002: backtest engine — build thin event loop vs. vectorbt/backtrader/nautilus
- 0003: market data provider — Alpaca vs. Polygon vs. Databento
- 0004: paper/live broker
