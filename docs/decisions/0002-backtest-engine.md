# ADR 0002: Backtest engine — thin event-driven loop

- **Date**: 2026-07-03
- **Status**: accepted

## Decision

Build a thin, event-driven backtest loop in-house (`core/backtest/engine.py`) rather
than adopt a vectorized library (`vectorbt`) or a heavier framework (`backtrader`,
`nautilus_trader`).

## Why

- The `Strategy` contract is `on_bar(ctx: Context) -> list[Order]` — inherently
  event-driven. A vectorized engine would fight this shape.
- Lookahead prevention is the project's top correctness concern. An explicit loop that
  hands the strategy a `Context` sliced to end at the current bar, and fills orders on
  the *next* bar's open, makes the no-lookahead guarantee auditable in a few dozen lines
  — "no dark corners."
- At bar-level (minutes) frequency the loop is fast enough; we don't need vectorized
  speed.

## Consequences

- We own the fill model, cost model, and metrics. More code, but full control.
- If a future strategy needs tick-level or vectorized parameter sweeps, that's a new ADR,
  not a rewrite — the engine stays behind `core/backtest` so strategies never depend on
  it directly.

## Alternatives rejected

- **vectorbt**: vectorized paradigm clashes with the event-driven `on_bar` contract and
  makes intrabar stop logic awkward.
- **backtrader / nautilus_trader**: more machinery than a bar-frequency lab needs;
  harder to audit for lookahead than ~300 lines we control.
