# Execution-cost study #2 — quote-grounded validation, judgment-window-clean

**Status: method pre-registered before any measurement was run.** This section
was written and committed FIRST; results are appended below afterwards and the
decision rule is not edited after the fact. (Same discipline as study #1,
`../2026-07-03-2319-spy-qqq-auction/notes.md`.)

- parent git commit: 4f1043c (tree: overnight-long implemented; paper session 1
  artifacts `experiments/overnight-long/paper-fills.QQQ.jsonl` present)
- author: locked 2026-07-07 09:14 CEST

## Why this study exists (two independent triggers)

1. **Paper validation is impossible.** Study #1 closed with: *"the measured 2.9 bps
   is a hypothesis until paper fills confirm it."* Paper session 1 (2026-07-06)
   proved it cannot: Alpaca **paper does not execute the closing/opening auction** —
   the QQQ MOC (13 sh, `tif=cls`, submitted 15:40 ET) came back `expired`/`qty:0`
   at the 16:00 close (official SIP print 722.82 retrieved fine). Confirmed against
   multiple current Alpaca forum reports. So the paper gate can never CONFIRM the
   cost; a quote-grounded offline estimate is the only remaining non-live evidence.
2. **Study #1 had a logged protocol flaw.** Its p75 fill-reference cost was pooled
   **2018–2026, which includes the walk-forward judgment window**. The quant-reviewer
   wrote: *"Next cost study must exclude the judgment window by construction."* The
   OOS verdict is cost-vintage-ambiguous (QQQ OOS Sharpe 0.65 @ pre-WF 3.18 bps vs
   0.82 @ period-matched 2.44 bps). This study fixes that by construction.

This study does **not** touch strategy parameters or success criteria. It only
re-estimates cost more honestly and adds an independent quote-based cross-check.

## Windows (from config.qqq.paper.yaml — fixed, not chosen here)

- **IS** 2018-01-01 → 2021-12-31 · **OOS** 2022-01-01 → 2024-12-31 · **WF** 2025-01-01 → present

## Pre-registered measurement method

### Measurement B — vintage-clean fill-reference cost (fixes study #1's flaw)
Same primitive as study #1 (`|5-min-bar reference − official auction print|` in bps,
close site = last 16:00-stamped bar close vs daily close; open site = first
09:35-stamped bar open vs daily open), from the committed adjusted parquets. **New:
computed and reported SEPARATELY per vintage (IS / OOS / WF).** Half-day 16:00 bars
excluded (calendar-aware), counted.

### Measurement A — quote-grounded auction premium (the new, truly quote-based leg)
Direct execution cost of the auction print vs the best pre-auction fair-value proxy
(NBBO mid), from Alpaca **SIP** historical quotes. Replaces study #1's 12-day
"context only" spread check.
- **Close (MOC buy):** `pre_close_mid` = median NBBO mid over 15:59:50–16:00:00.
  `close_premium_bps = 1e4 · (official_close_print − pre_close_mid) / pre_close_mid`
  (positive = bought above pre-auction mid = adverse to us).
- **Open (MOO sell):** `pre_open_mid` = median NBBO mid over 09:29:50–09:30:00
  (pre-open book; if <3 valid quotes, fall back to 09:30:00–09:30:10 and TAG it).
  `open_premium_bps = 1e4 · (pre_open_mid − official_open_print) / pre_open_mid`
  (positive = sold below pre-auction mid = adverse to us).
- **Official prints:** daily-bar close/open from the adjusted daily parquet (the same
  official auction prints a real `cls`/`opg` order fills at).
- **Sample (pre-registered, seeded):** `numpy` seed **20260707**. Random stratified:
  **40 sessions per vintage** (IS/OOS/WF) drawn uniformly within vintage, PLUS a
  **high-gap stratum** = 30 sessions from the top decile of |overnight gap|
  (`|Open(d+1)/Close(d) − 1|`) pooled, reported separately (the heteroskedastic tail
  study #1 flagged). Quote windows that return no data are counted, not backfilled.

### Fees
Regulatory (SEC §31 + FINRA TAF) **0.3 bps round-trip, sell-side**, unchanged from #1.

## Pre-registered decision rule (LOCKED NOW, before results)

1. **Per-site charged cost:**
   - Measurement B: `abs p75` of the fill-reference |error| at that site, **measured
     on IS + OOS data only (WF excluded from cost estimation entirely)**. The cost
     applied to the OOS judgment is the **IS-only** p75 (primary); pooled IS+OOS
     reported as a secondary sensitivity, never applied to OOS as primary.
   - Measurement A: `abs p75` of the signed premium at that site, same sample.
2. **Charged cost = the MORE CONSERVATIVE (higher) of A and B, per site.** We cannot
   cherry-pick the lower number to rescue the strategy. Signed means reported to
   expose any systematic bias, but the charge is the conservative one.
3. **Config mapping:** `half_spread_bps: 0.0`, `close_slippage_bps = charged_close`,
   `slippage_bps = charged_open + 0.3`, `commission_per_unit: 0.0`.
4. **Judgment (strategy bar UNCHANGED — no new, easier bar):** re-run QQQ-gated
   overnight-long at the charged cost. It **PASSES** iff **OOS net Sharpe ≥ 0.7 with
   positive net return AND the walk-forward run confirms (net Sharpe ≥ 0.7, net > 0)**
   at the charged cost. Same params, seeds, windows as the original runs.
5. **Anti-goalpost clause:** no strategy-parameter changes of any kind. If it does not
   clear its *original* OOS + WF bar at the charged cost, overnight-long **stays
   rejected and is PULLED FROM PAPER**, and we stop iterating on it. A lower measured
   cost that still fails the bar does not rescue it; a higher one that fails confirms
   the rejection.
6. Note recorded for the future: even a PASS here is an offline cost *estimate*, not
   proof of live fill. Live validation would require a tiny real-money test (separate,
   explicit hard-rule sign-off) — see memory `core-paper-safety-gaps`.

---

## Results (appended after the run; see metrics.json)

Run 2026-07-07, `scripts/measure_auction_costs_v2.py`, QQQ. Quote sample: 120 random
(40/vintage) + 28 high-gap, 0 fetch failures, 0 pre-open fallbacks.

### Measurement B — fill-reference cost per vintage (QQQ, abs p75 bps)
| site | IS 2018–21 | OOS 2022–24 | WF 2025+ |
|------|-----------|-------------|----------|
| close | **3.07** | 1.91 | 1.44 |
| open  | 0.54 | 0.23 | 0.18 |

IS-only (the no-lookahead cost applied OOS) = **3.07 / 0.54** → higher than study #1's
contaminated pooled 2.31/0.29, exactly as the reviewer predicted (2020 close-site noise
sits in IS). Study #1's flaw confirmed and corrected.

### Measurement A — quote-grounded auction premium (RAW print vs pre-auction NBBO mid)
| site | signed mean | signed p50 | **abs p75** | abs p90 |
|------|-------------|-----------|-------------|---------|
| close | +0.16 | −0.06 | **3.57** | 5.47 |
| open  | −0.01 | 0.00 | **1.17** | 1.81 |

**Signed means ≈ 0 → the auction print is UNBIASED vs the pre-auction mid** (no systematic
adverse selection). The dispersion is real but symmetric. High-gap stratum (tail check,
not charged): close abs p75 3.40, open 1.28 — not much worse than random, i.e. the
dispersion is not a gap-day artifact.

### Charged cost (locked rule: max of A,B per site; B = IS-only)
close = max(3.07, 3.57) = **3.57** (A) · open = max(0.54, 1.17) = **1.17** (A) · +0.3 fees
→ **round-trip 5.04 bps.** Config: `config.qqq.evcost2.yaml` / `config.qqq.wf.evcost2.yaml`.

### Judgment at the charged cost (strategy params UNCHANGED)
| window | Sharpe | net return | bar ≥0.7 |
|--------|--------|-----------|----------|
| OOS 2022–24 | **0.166** | +0.43% | **FAIL** |
| WF 2025+    | **0.643** | +1.00% | **FAIL** |

`experiments/overnight-long/2026-07-07-0927-study2-charged` (OOS),
`.../2026-07-07-0928-study2-charged-wf` (WF).

## VERDICT (per the locked rule): FAIL — overnight-long PULLED FROM PAPER

It clears neither the OOS nor the WF ≥0.7 bar at the charged cost. Per the pre-registered
anti-goalpost clause, overnight-long is pulled from paper and offline iteration stops.

## Honest caveat — the verdict is CONVENTION-DRIVEN, not economics-driven (recorded, does NOT overturn the lock)

The charge is `abs p75` of the print-vs-mid deviation, applied always-adverse. But
measurement A showed the print is **unbiased** (signed mean +0.16/−0.01 bps): over a
*repeated* strategy, half those deviations are favorable and the realized expected cost is
the **signed mean ≈ 0.45 bps RT**, not `abs p75`. Sensitivity at 0.45 bps (NOT the verdict):
OOS Sharpe **1.01** (net +2.70%), WF **1.55** (net +2.44%) — a strong pass on both.

So the entire rejection rides on a conservative one-shot convention (inherited from study
#1) that is defensible for the fill-reference *modeling error* but is the WRONG cost model
for a repeated trade against an unbiased auction print. **Pre-registration lesson for any
future study: for the quote-premium leg, charge the signed mean (repeated-trade expected
cost), not `abs p75`.** This is logged, and — per the anti-goalpost clause — is NOT applied
retroactively to rescue this verdict.

**Consequence:** the offline evidence is genuinely split (conservative convention → reject;
expected cost → strong pass) and paper cannot fill the auction to break the tie. The ONLY
clean resolver left is a **tiny real-money live test** (separate, explicit hard-rule
sign-off; see memory `core-paper-safety-gaps`). This study does not, by itself, kill the
economic thesis — it kills the *paper/offline* path to validating it.
