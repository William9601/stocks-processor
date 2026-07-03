# Development workflow

The loop every strategy goes through. Each gate must pass before the next stage; the
AI roles in parentheses do the heavy lifting at each step.

```
idea ──> spec ──> implement ──> backtest ──> review ──> compare ──> paper ──> (live)
          │                                    │                      │
          └── rejected ideas die here          └── failed review      └── kill switch
              (cheapest place to fail)             goes back to           returns to
                                                   implement/spec         backtest
```

## 1. Spec (`/new-strategy` + strategy-designer agent)

Every strategy starts as a `SPEC.md` from `strategies/_template/`. The
strategy-designer agent drafts it and stress-tests the hypothesis. **Gate:** user
approves the spec; success criteria are now locked and may not be adjusted to fit
results later.

## 2. Implement (main Claude Code session)

Build against the shared `core/` interfaces only — no direct data or broker access
from strategy code. Unit tests for signal logic are required (given a fixed bar
sequence, assert exact entries/exits). **Gate:** tests pass, `ruff` clean.

## 3. Backtest (core/backtest harness)

Run in-sample first for development, then one out-of-sample run (ideally
walk-forward). Every run writes to `experiments/<strategy>/<YYYY-MM-DD-HHMM>-<tag>/`:
`config.yaml` (full parameters + data range + git commit), `metrics.json`, `notes.md`.
**Gate:** out-of-sample run exists with realistic costs.

## 4. Review (quant-reviewer agent)

Mandatory before trusting results. The reviewer hunts lookahead bias, unrealistic
fills, overfitting, and unenforced risk limits. **Gate:** no blocker findings.

## 5. Compare (`/compare-strategies` + backtest-analyst agent)

Strategies compete on identical date ranges, universes, and cost models. The analyst
issues per-strategy verdicts against locked success criteria. **Gate:** strategy meets
its own SPEC criteria — not "beats the others", meets its own bar.

## 6. Paper trade

Passing strategies run against a paper account through `core/execution`. Compare
paper fills to backtest assumptions weekly — slippage divergence is the #1 reason
backtests lie. **Gate:** N weeks of paper results within tolerance of backtest
expectations (define N and tolerance in the SPEC before starting).

## 7. Live (far future)

Requires explicit per-session user confirmation, real risk limits enforced at the
broker level where possible, and the kill switch tested. Never enabled by default.

## Iteration rules

- Tuning happens on in-sample data only. Each new out-of-sample look "spends" that
  data — you get very few honest looks; walk-forward gives you more.
- A strategy that fails its criteria twice after revision gets retired, not endlessly
  tuned. Record the post-mortem in its SPEC and keep it in the repo as institutional
  memory.
