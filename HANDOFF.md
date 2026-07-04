# Handoff: get overnight-long (QQQ gated) ready for paper trading this week

Paste this into a new Claude Code session in `~/projects/stockProcessor` (or just say
"read HANDOFF.md and execute it"). Delete this file when the work is done.

## Context (verify against the repo, don't re-derive)

- `strategies/overnight-long/` — buy QQQ at the close (MOC), sell at the next open
  (MOO), only when prior close > 200-day SMA. Status in SPEC.md: **qualified
  paper-candidate (QQQ gated only) — borderline OOS, walk-forward-carried.**
- Master verdict v2: `experiments/overnight-long/2026-07-03-2323-qqqgate-wf-evcost/notes.md`.
  Cost study: `experiments/execution-cost-study/2026-07-03-2319-spy-qqq-auction/notes.md`.
- Key numbers: measured real MOC/MOO cost QQQ ≈ 2.9 bps round-trip (vs 7 assumed);
  OOS net Sharpe 0.715 engine-convention / **0.584 zero-filled (below the 0.7 bar)**;
  walk-forward 2025-01→2026-07: 1.14 / 1.08 corrected — the WF carries the candidacy.
- The user has explicitly approved moving to **paper** trading (never live; paper only,
  `paper=True` stays hardcoded). User wants to start Monday 2026-07-06.
- The working tree may still be uncommitted. **Step 0: commit the current state first**
  (user has approved committing it) so the re-runs below diff against a clean baseline.

## Build tasks (in order)

1. **Fix `core/backtest/metrics.py` Sharpe convention.** `_daily_equity` builds the
   equity curve from trade days only; gate-flat sessions vanish from the denominator
   before √252. Zero-fill over the true session calendar; keep the old number as
   `sharpe_trade_days` for comparability with committed runs. Sanity anchors: QQQ-gated
   evcost OOS 0.715 → 0.5843 (752 sessions), WF 1.141 → 1.0845 (375 sessions),
   IS 0.843 → 0.7747 (1008 sessions).
2. **Fix the dead 2·R daily-loss limit in `core/risk/sizing.py`.** `size()` only runs
   on order-emitting bars, so `_day_start_equity` is captured after the morning exit
   already realized the overnight loss — `loss ≈ 0`, halt never fires. Make the
   day-roll/breaker check run every bar (engine hook), not only on orders.
3. **Calendar-aware sessions.** Half-days (13:00 ET close) currently: (a) skip entries,
   (b) can strand an overnight position past an early close, (c) the 5m parquet files
   carry phantom 16:00-stamped bars built from after-hours prints (~2/yr, verified:
   2018-07-03, 2024-11-29, 2024-12-24…) that the backtest "fills MOC" on. Derive each
   session's true close from the data (or a calendar dep) and filter phantom bars at
   load; strategy decision times become offsets from the session close, not hardcoded.
4. **Move the decision bar 15:55 → 15:40** (Alpaca MOC submission cutoff is ~15:45 ET;
   the gate uses the *prior day's* close so nothing informational is lost). This is a
   STRATEGY CHANGE → re-run the full judgment suite with tags like `t1540-*`:
   `config.qqq.evcost.yaml` (is + oos), `config.qqq.wf.evcost.yaml` +
   `config.qqq.wf.yaml` (walkforward), via `scripts/run_backtest.py`. Then a
   **quant-reviewer agent pass** before trusting. Judge against the same locked bars
   (report both Sharpe conventions). If the 15:40 variant materially degrades, STOP and
   report to the user — do not tune around it.
5. **Wire the live paper path for auction orders.** `core/execution/paper.py`
   `submit_market` only does `TimeInForce.DAY`; add MOC (`cls`) / MOO (`opg`)
   submission. `core/execution/live_runner.py` must handle `FillTiming.NEXT_CLOSE` /
   `NEXT_OPEN` orders and the overnight schedule: poll from ~15:30, decide 15:40,
   submit MOC buy; next morning submit the MOO sell before ~9:25; **log every fill**
   (ts, side, qty, fill price, official auction print, diff in bps) to an append-only
   file — that log IS the paper-phase measurement. Create
   `strategies/overnight-long/config.qqq.paper.yaml` (QQQ gated, 15:40 decision,
   evidence costs for reference). Keep `scripts/run_paper.py`'s per-session "type
   'paper'" confirmation — hard rule.
6. **Pre-register the paper gate in SPEC.md before the first paper order** (workflow
   gate 6 requires N + tolerance defined up front). Locked: minimum 4 weeks / ~20
   fills for the first cost read; **auto-reject tripwire: measured real round-trip
   cost > 4–5 bps, or recurring odd-lot auction rejections → back to REJECT, no
   relitigation.** Profit judgment needs months and is NOT the week-1 goal.

## Rules that bind this work (CLAUDE.md)

- No parameter tuning; success bars are locked. No lookahead. Costs mandatory.
- Paper only; live never by default. API keys stay in `.env` (already present).
- Every run writes a provenanced `experiments/` entry. `uv run pytest` (33+ tests)
  and `uv run ruff check .` green before done.

## User's part (tell them when handing back)

- Monday ~15:25 ET: `uv run python scripts/run_paper.py
  strategies/overnight-long/config.qqq.paper.yaml`, type `paper` to confirm.
- Mornings: glance at the fill log. Friday: week-1 mechanics review.
- Expectation: ~$10k notional (~20 QQQ shares) on the $100k paper account → ± a few
  dollars/night. Week 1 measures fill quality vs the 2.9 bps hypothesis, not profit.
