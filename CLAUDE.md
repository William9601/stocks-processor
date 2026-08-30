# stockProcessor — AI Operating Manual

Day-trading strategy lab. Multiple strategies are built as independent packages, all
running through one shared core (data, backtesting, risk, execution) so their
performance can be compared apples-to-apples.

## Current phase

**Scaffolding.** The shared core and strategies are not implemented yet. Do not write
trading logic unless the user explicitly asks for it. The immediate work is specs,
architecture, and tooling.

## Repo layout

- `core/` — shared library: `data/` (market data ingestion + storage), `backtest/`
  (event-driven backtest engine + metrics), `risk/` (position sizing, limits),
  `execution/` (broker abstraction; paper first, live behind an explicit flag)
- `strategies/<name>/` — one package per strategy. Each starts from
  `strategies/_template/` and must have a `SPEC.md` **before any code is written**
- `experiments/` — backtest run outputs (config + metrics + notes per run), committed
  to git so results are reproducible and comparable
- `docs/` — architecture, workflow, AI setup; `docs/decisions/` holds ADRs
- `data/` — raw/cached market data, **gitignored**, never committed

## Hard rules

1. **Spec before code.** A strategy without an approved `SPEC.md` does not get implemented.
2. **No lookahead.** Signals at time T may only use data available strictly before T.
   Flag any `.shift(-1)`, future-indexed joins, or same-bar fill assumptions.
   See also rule 7 — a bar the market was closed for is not tradeable data.
3. **Costs are mandatory.** Every backtest models commissions, spread, and slippage.
   A result without costs is not a result.
4. **Paper before live. Live never by default.** Anything touching a real brokerage
   account requires an explicit, per-session confirmation from the user. Never store
   API keys in the repo — use `.env` (gitignored).
5. **Reproducibility.** Every experiment records its config, data range, seed, and git
   commit. If it can't be re-run, it didn't happen.
6. **In-sample / out-of-sample discipline.** Strategies are tuned on the in-sample
   window only. Out-of-sample and walk-forward results are the numbers that count.
7. **Load bars through the feed, never `pd.read_parquet` directly.** Vendor files carry
   **phantom bars stamped after a half-day's 13:00 close**, built from thin after-hours
   prints (0.1–0.4% of bars, 15–18 sessions per intraday file; verified across every
   parquet on 2026-08-30). Filling on one is a fill at a time the market was shut.
   `DataFeed.from_source` applies `core.data.calendar.filter_to_sessions` at load, and
   the backtest engine and paper path inherit it — **so use them.** A standalone
   diagnostic that reads parquet directly silently opts out of the fix: all seven
   `scripts/pregate_*.py` do. The three that read **intraday** bars
   (`pregate_rsi5050`, `pregate_orb`, `pregate_keltner`) now carry an opt-in
   `--filter-sessions` — default OFF, so their recorded verdicts still reproduce
   byte-for-byte, verified. The other four consume **daily** bars, which are
   midnight-stamped one-per-session and cannot carry a phantom, so they need no flag.
   New scripts get the filter on by default or go through the feed.
   Related: derive session close times from `session_closes`/`session_close_et`, never
   from "the last bar present on that date" — on an unfiltered half-day that is a
   post-close bar, which silently moves both arm-cutoff and forced-flat exit times.
   Evidence: `experiments/data-audits/2026-08-30-phantom-half-day-bars/`.

## Conventions

- Python ≥3.12, managed with `uv`. Format/lint with `ruff`, test with `pytest`.
- Every strategy implements the common `Strategy` interface defined in
  `docs/architecture.md` — no strategy talks to data or brokers directly.
- Config-driven runs: strategies are parameterized via YAML, not edited constants.

## AI roles (see docs/ai-setup.md)

- `strategy-designer` agent — turns an idea into a `SPEC.md`
- `quant-reviewer` agent — reviews strategy code for lookahead bias, overfitting,
  unrealistic execution assumptions, and risk-limit gaps
- `backtest-analyst` agent — interprets experiment results and compares strategies
- `/new-strategy` skill — scaffolds a new strategy from the template
- `/compare-strategies` skill — builds a comparison report from `experiments/`

## Workflow

The full loop (idea → spec → implement → backtest → review → compare → iterate) is
defined in `docs/workflow.md`. Follow its gates; don't skip review before promoting a
strategy to paper trading.
