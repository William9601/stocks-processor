# overnight-long — MASTER VERDICT v1 (superseded)

> **Superseded 2026-07-03 by verdict v2** after the execution-cost study this verdict
> called for was run: measured costs (QQQ 2.9 bps vs the assumed 7) flip QQQ-gated to a
> PASS on the same locked bars, confirmed on 2025–2026 walk-forward (Sharpe 1.14). See
> `../2026-07-03-2323-qqqgate-wf-evcost/notes.md` and
> `experiments/execution-cost-study/2026-07-03-2319-spy-qqq-auction/`.
> The analysis below is kept unchanged for the record.

- sample: oos | instrument: QQQ | gate: 200-SMA risk-on | synthetic: False
- data: data/QQQ_5m_adj.parquet + data/QQQ_daily_adj.parquet (Alpaca SIP, **dividend+split adjusted**)
- trades: 498 | net return: -0.5% | gross: +2.9% | sharpe: -0.21 | max DD: -2.0%

## Verdict: REJECT on locked criteria — but gross-profitable & cost-gated (NOT dead)

Fundamentally different outcome from the two retired siblings (MIM, overnight-drift),
which had no edge even gross. Here the overnight premium is **real and gross-positive
in all 8 runs**, drawdown is small (2–5%), and the entire gap between gross-positive
and net-negative is the auction-cost assumption. Quant-reviewer validated the gross
premium is **causal and reproduced outside the engine to the basis point** — no
lookahead, correct dividend adjustment, correct gate causality.

### All 8 runs (net return / gross / net Sharpe / max DD)

| run              | IS net | IS gross | IS Sharpe | OOS net | OOS gross | OOS Sharpe | OOS DD |
|------------------|--------|----------|-----------|---------|-----------|------------|--------|
| SPY gated        | -0.6%  | +5.0%    | -0.21     | -2.0%   | +1.6%     | -1.19      | -2.7%  |
| QQQ gated        | +0.2%  | +6.0%    | +0.04     | -0.5%   | +2.9%     | -0.21      | -2.0%  |
| SPY ungated      | -1.0%  | +5.8%    | -0.20     | -3.7%   | +1.3%     | -1.25      | -4.5%  |
| QQQ ungated      | +0.1%  | +7.0%    | +0.03     | -3.5%   | +1.4%     | -0.90      | -5.0%  |

On the locked bar (OOS net Sharpe ≥ 0.7, net > 0): **all fail**. The gate helps OOS
(QQQ gated -0.21 vs ungated -0.90; SPY gated -1.19 vs -1.25) — the 200-SMA filter
avoids bad overnight regimes, as designed.

### The decision-relevant finding: it's a cost story, and QQQ clears the bar cheaply

Break-even auction cost and net Sharpe vs round-trip cost (gated, from the raw
daily-bar decomposition; backtest assumes ~7 bps):

| run       | gross bps/day | break-even cost | Sharpe @7bp | @5bp  | @3bp  | @1bp  |
|-----------|---------------|-----------------|-------------|-------|-------|-------|
| SPY IS    | +6.99         | 7.0 bps         | -0.00       | +0.56 | +1.11 | +1.67 |
| SPY OOS   | +2.90         | 2.9 bps         | -1.28       | -0.66 | -0.03 | +0.59 |
| QQQ IS    | +6.60         | 6.6 bps         | -0.08       | +0.32 | +0.73 | +1.13 |
| QQQ OOS   | +6.47         | 6.5 bps         | -0.12       | +0.33 | +0.78 | +1.23 |

**QQQ-gated is consistent IS *and* OOS (~6.5 bps break-even both windows) and clears
the ≥0.7 bar in BOTH windows at ≤3 bps round-trip.** SPY is weaker and decayed OOS
(break-even only 2.9 bps). Real MOC/MOO slippage on these mega-liquid ETFs is
plausibly ≤2–3 bps round-trip, so QQQ-gated's viability is a *measurable execution
question*, not a dead end.

## Important sizing nuance (per quant-review)

The book runs at **~10% notional**, because the `gap_floor = 5%` always dominates
`3·σ_overnight` (overnight σ ≈ 0.4–0.6%). Notional ≈ R/G·equity = 0.5%/5% = 10%.
So the small % net returns and 2–5% drawdowns are **honest under-investment**, not a
bug — **Sharpe, not % return, is the metric that matters here** (leverage-scaling is
Sharpe-invariant). The 5% gap-floor is the SPEC's deliberate un-stoppable-tail budget;
sizing up is possible but trades Sharpe-neutrally for more overnight gap risk.

## Decision

REJECT at the locked (conservative) cost — we do NOT lower the locked cost to claim a
pass. But this is the **first strategy in the lab worth advancing**: the honest,
non-goalpost-moving next step is a **separately-specified execution-cost study** to
measure real SPY/QQQ MOC/MOO auction slippage. If it comes in ≤ ~3 bps round-trip,
QQQ-gated overnight-long clears the pre-locked bar IS and OOS and becomes a paper
candidate. Status: `implemented` (built, tested, evaluated) — NOT promoted to paper.

## Prerequisites before any paper promotion (per quant-review)

- Fix the sparse-order dead `2·R` daily-loss limit (`core/risk/sizing.py`).
- Fix hardcoded 15:55/16:00 decision bars → market-calendar-aware (half-days).
- The execution-cost study result must clear the pre-locked bar with an evidence-based
  cost — not a softened assumption.
