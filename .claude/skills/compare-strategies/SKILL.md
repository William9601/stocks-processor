---
name: compare-strategies
description: Build a comparison report across strategies from experiments/ results. Use when the user asks how strategies stack up, which one is best, or wants a leaderboard.
---

# Compare strategies

1. Enumerate runs under `experiments/`, reading each run's `config.yaml` and
   `metrics.json`.
2. Select the runs to compare: latest out-of-sample (or walk-forward) run per
   strategy. Verify comparability — same date range, universe, cost model, and capital
   base. If runs are not comparable, report exactly what differs and stop; do not
   produce a misleading table.
3. Launch the `backtest-analyst` agent to analyze the selected runs.
4. Write the report to `experiments/comparisons/<YYYY-MM-DD>-comparison.md` with:
   - a summary table (net return, Sharpe, Sortino, max DD, trade count, cost drag)
   - per-strategy verdict against its own SPEC success criteria
   - regime notes: where each strategy makes and loses its money
   - an explicit ranking with reasoning, and any strategies that should be retired
5. Summarize the verdicts for the user in chat.
