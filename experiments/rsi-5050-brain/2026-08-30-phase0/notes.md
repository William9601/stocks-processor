# rsi-5050-brain — Phase 0 separability audit (2026-08-30)

**Verdict: REJECT at spec validation (Phase 0). 14th candidate death.**

Sequence, for the record: `strategies/rsi-5050-brain/SPEC.md` drafted → 4 open
questions resolved → **spec APPROVED/FROZEN** with the feature list and the gate
written down → `scripts/phase0_rsi5050_brain.py` written → run on IS only. The gate
rule and all 17 features existed in the frozen SPEC before the script did. OOS
(2022-2024) and WF (2025→) were hard-sliced out and **were never read**.

- **Script**: `scripts/phase0_rsi5050_brain.py` (loads `scripts/pregate_rsi5050.py`
  by path so indicator math and every locked parameter are shared code, not retyped)
- **Data**: `data/DIA_5m.parquet` + `SPY_5m` / `QQQ_5m` + `fomc_calendar.csv`;
  sha256 of each recorded in `results.json`
- **Window**: IN-SAMPLE ONLY, 2018-01-01..2021-12-31

## Data-verification cell — PASS

The rebuilt per-trade log reproduces the inherited pregate exactly:

| | got | expect |
|---|---|---|
| n | 767 | 767 |
| mean gross | +0.304 bps | +0.304 bps |
| EOD / recross | 101 / 666 | 101 / 666 |

So the mechanical layer was not perturbed and everything below is a statement about
the hypothesis, not about a bug.

## Gate results (locked rule)

| Locked bar | Value | Verdict |
|---|---|---|
| CV mean gross of selected ≥ **2.0 bps** | **+0.007 bps** | **FAIL** |
| Selected trades ≥ 150 | 301 | pass |

Out-of-fold, 5 chronological folds, threshold from the training fold only:

| fold | n_test | selected | retention | mean bps | EOD precision |
|---|---|---|---|---|---|
| 1 | 154 | 85 | 0.55 | −0.664 | 0.224 |
| 2 | 154 | 46 | 0.30 | +0.494 | 0.239 |
| 3 | 153 | 49 | 0.32 | +0.011 | 0.204 |
| 4 | 153 | 59 | 0.39 | +0.688 | 0.186 |
| 5 | 153 | 62 | 0.41 | −0.083 | 0.177 |

**No fold reached even +0.7 bps against a 2.0 bps bar**, and two are negative. The
pooled selected set (+0.007 bps) is *worse than the set it rejected* (+0.495 bps).

## What killed it — precision and payoff are decoupled by construction

The striking part is that the classifier **did** lift EOD precision: 0.1317 →
**0.2060 (1.56×)**, against the 1.91× needed for break-even. Six features cleared
Benjamini–Hochberg at q=0.10, so there is real, statistically detectable structure
predicting the EOD label. It simply does not convert into money, and the diagnostic
shows exactly why:

```
corr(minutes_since_open, hold_bars) = −0.971      (near-deterministic)
corr(hold_bars, EOD return)         = +0.568
```

| tod bucket | n | EOD share | EOD mean | EOD median hold |
|---|---|---|---|---|
| close | 274 | 0.234 | **+16.43 bps** | 12 bars |
| midday | 457 | 0.081 | **+35.72 bps** | 30 bars |
| open | 36 | 0.000 | — | — |

**The EOD label is contaminated by time-of-day.** A signal late in the session has
fewer bars left in which RSI can recross, so it is mechanically more likely to be
*labelled* EOD — while having less time to run and therefore paying roughly half.
The two top univariate features are `f07_minutes_since_open` (corr +0.254) and
`tod_close` (+0.225): the model found the artifact, not a trend-day signal.

**This is a flaw in this spec's own mixture framing, and it is the finding.** The
Hypothesis section treated exit type as a proxy for "trend session vs chop session".
It is not a clean proxy — it is partly a clock. Maximising EOD precision is therefore
not the same objective as maximising return, and the locked gate (which scored bps,
correctly) caught the difference.

Beyond that artifact, nothing separated the population in the return dimension:
`f12_spy_align` (p=0.99), `f13_qqq_align` (p=0.89), `f04_rsi_jump` (p=0.75),
`f11_overnight_gap_bps` (p=0.58), `f08_ret_since_open_bps` (p=0.57) — the
cross-sectional, macro, and signal-geometry features the discretionary overlay was
supposed to be made of are all indistinguishable from noise.

## No-rescue clause

Binds as frozen. **No LLM arm is built.** No feature additions, no threshold
relaxation, no tree models, no retention sweep, no re-labelling of the target, no
instrument or bar-size variant. Per SPEC.md Phase 0: status → retired. OOS and WF
remain unread and are returned to the pool unspent.

## Robustness check added 2026-08-30 (phantom half-day bars)

A later audit found that this script — like all seven `scripts/pregate_*.py` — reads
parquet directly and so includes bars stamped after a half-day's official 13:00 close
(`experiments/data-audits/2026-08-30-phantom-half-day-bars/`). Re-run with
`--filter-sessions` (231 phantom bars dropped, 765 trades):

| | as recorded | filtered | bar |
|---|---|---|---|
| CV mean gross of selected | +0.007 bps | +0.411 bps | ≥ 2.0 |
| selected trades | 301 | 294 | ≥ 150 |
| EOD precision | 0.2060 (1.56x) | 0.2211 (1.69x) | needs 1.92x |
| **verdict** | **FAIL** | **FAIL** | |

**The rejection is unchanged**, and so is its cause: `f07_minutes_since_open` remains
the strongest univariate feature (corr +0.255). Recorded as a robustness check, not a
re-run of the gate — the gate was scored once, on the run above.

## Pre-registered deviations (recorded before any result was computed)

1. **f15 VIX unavailable offline** (no VIX vendor in the repo, no `yfinance` dep).
   Substituted `f15a/f15b` = SPY 20-day realised volatility (annualised %, prior-day)
   from `SPY_5m` daily closes. Both landed at p=0.51 / p=0.58, so the substitution is
   very unlikely to have changed the verdict — but it is a substitution, and a true
   VIX series would be required before anyone re-opens this.
2. **Folds are chronological blocks, not random** — adjacent sessions share regime and
   random folds would leak. Fixed before the first run.
3. **p-values use a normal approximation** (n=767; the t/normal difference is immaterial).

## Observation for a *future, separately-specified* idea

Not a pivot of this one, and not evidence — it is a post-hoc reading of an IS window
that has now been consumed for this formulation.

The midday EOD trades (n=37, +35.72 bps, 30-bar median hold) are the population the
brain hypothesis was actually reaching for: long-lived trend sessions, entered away
from the close. They are 4.8% of all trades. Any future attempt should (a) define the
target as *forward return over a fixed horizon*, never as exit type, which this run
shows is a clock in disguise, and (b) do so on data this run has not consumed. The
2018-2021 IS window is now spent for the mixture-separability question on DIA 5-min.
