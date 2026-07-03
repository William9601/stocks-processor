# overnight-drift — SPY OOS (2022–2024)

- sample: oos   |   instrument: SPY   |   synthetic data: False
- data: data/SPY_5m.parquet (5m RTH) + data/SPY_daily.parquet (200-SMA/ATR/gap-vol), Alpaca SIP
- trades: 592   |   net return: -13.1%   |   gross: -1.9%   |   sharpe: -2.47   |   max DD: -15.1%

## Verdict: REJECTED (both instruments, both windows)

Fails every locked success criterion. Paired runs: SPY IS `..1826-spy-is`
(net -12.9%, Sharpe -2.00), QQQ IS `..1827-qqq-is` (-12.5%, -1.76), QQQ OOS
`..1827-qqq-oos` (-12.7%, -1.96). Quant-reviewer validated: **not a bug** — no
lookahead in the MOC path, correct leg handoff, honest costs; the 15% kill
switch engaged (it limited the loss, did not cause it).

| criterion            | locked bar | SPY IS | SPY OOS | QQQ IS | QQQ OOS |
|----------------------|-----------|--------|---------|--------|---------|
| net Sharpe (OOS)     | >= 0.7    | -2.00  | -2.47   | -1.76  | -1.96   |
| net return           | > 0       | -12.9% | -13.1%  | -12.5% | -12.7%  |
| max drawdown         | <= 15%    | 15.1%  | 15.1%   | 15.1%  | 15.0%   |
| beat buy&hold Sharpe | yes       | no     | no      | no     | no      |

## Why (real absence of edge, not a cost-masking artifact)

Per-leg P&L decomposition (`long_pnl`=overnight, `short_pnl`=intraday):

| leg               | SPY IS   | SPY OOS  | QQQ IS   | QQQ OOS  |
|-------------------|----------|----------|----------|----------|
| overnight (long)  |  -$749   | -$2,484  |  -$367   |  -$939   |
| intraday (short)  | -$12,109 | -$10,606 | -$12,151 | -$11,755 |

Two independent conclusions, confirmed by a raw daily-bar decomposition computed
*outside* the engine (regime-gated, ~7 bps/leg auction cost):

1. **Overnight-long premium is real but ~fully eaten by costs.** Gross close→open
   drift is positive (SPY +3–5 bps/day, QQQ +6 bps/day, stronger in QQQ as the
   literature predicts) — but the conservative modeled auction cost (MOC 2 bps +
   MOO 3 bps + spread) is ~7 bps/round-trip, so net the leg is ~breakeven-to-
   slightly-negative. On the single most-liquid ETFs the edge does not clear the
   locked cost floor.
2. **The intraday-short leg has no gross edge and is the entire net loss.** Gross
   is ~0 on SPY and *negative* on QQQ (its intraday session drifted up over
   2018–2024), so shorting it bleeds gross, then costs compound it. Every window's
   loss is the short leg. Adding this leg (a design choice at spec time) actively
   hurt vs. a pure overnight hold.

Gross is marginally positive IS (SPY +2.6%, QQQ +0.2%) and negative OOS — no
persistent net edge to tune toward.

## Decision

Reject at spec-validation, per the SPEC's pre-locked adversarial note. Do NOT tune
the gate or costs to rescue it: the net-of-cost premium is ~0/negative OOS on the
cleanest instruments, and the short leg is structurally edgeless. Strategy status
-> retired.

## Observations for *future, separately-specified* ideas (each needs its own SPEC)

- **Overnight-long-only, no short leg.** The short leg is the whole loss; the
  overnight premium alone is near-breakeven under these costs. A pure long-overnight
  hold, with realistic (not deliberately-conservative) auction slippage on ultra-
  liquid ETFs, might clear a lower bar. Different hypothesis — re-pre-register.
- **Cost model dominates.** The 3/2 bps auction slippage was locked conservative;
  SPY/QQQ real MOC/MOO slippage is plausibly sub-bp. The strategy's fate hinges on
  that assumption — worth a dedicated execution-cost study before any retry.

## Core issues surfaced by the review (not affecting this reject; fix before paper)

- `core/risk/sizing.py`: the 2·R per-cycle daily-loss limit is effectively dead —
  `size()` only runs on bars where the strategy emits orders, so the day-start
  equity is captured too late to measure the day's loss. (15% DD kill switch is
  fine.)
- `strategies/overnight-drift/strategy.py`: decision bars hardcoded to 15:55/16:00
  — early-close/half-day sessions skip entry and can leave an intraday short
  uncovered past the close. ~1 day of impact on this data; a live-safety bug.
