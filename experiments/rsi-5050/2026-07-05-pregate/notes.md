# rsi-5050 — pre-gating gross-edge diagnostic (spec validation)

- **Date**: 2026-07-05
- **Script**: `scripts/pregate_rsi5050.py` (outside the engine, per SPEC.md)
- **Data**: `data/DIA_5m.parquet`, `data/DIA_15m.parquet` — Alpaca historical SIP,
  raw (unadjusted), RTH close-stamped, 2017-12-01..2026-07-02 (fetched 2026-07-05;
  DIA minute history confirmed available from ≥ 2018, spec assumption verified)
- **Window**: IN-SAMPLE ONLY, 2018-01-01..2021-12-31. OOS (2022-2024) and
  walk-forward (2025→) were never read by the diagnostic.
- **Gate (locked in SPEC.md before the script was written)**: mean gross
  continuation (stop-entry trigger → RSI-recross exit, both sides, band-passing
  crosses only) must exceed the ~3.5 bps modeled round-trip cost, else
  reject-at-spec-validation with no tuning.

## Results

| | 5-min baseline | 15-min co-equal variant |
|---|---|---|
| Band-passing, time-gated signals | 1,112 | 39 |
| Filled | 767 (~192/yr) | 28 (~7/yr) |
| **Mean gross continuation** | **+0.30 bps** (t = 0.64) | **−2.86 bps** (t = −2.17) |
| Median | −3.55 bps | −3.64 bps |
| Hit rate | 27.1% | 25.0% |
| Long / short mean | +0.20 / +0.40 bps | −3.23 / −2.50 bps |
| Cost bar to clear | 3.5 bps | 3.5 bps |
| **Verdict** | **FAIL** | **FAIL** |

## Reading

- **5-min (the conclusive result, n = 767):** the gross edge is ~0.3 bps — a
  tenth of the cost bar and statistically indistinguishable from zero. Net of
  the modeled 3–4 bps round trip, every trade loses in expectation. This is a
  clean, well-powered negative: the signal as specified carries no tradeable
  continuation on DIA 2018–2021.
- **15-min (inconclusive-negative, n = 28):** the pre-registered band
  (4.5–6.8 bps, anchored at 5-min scale) almost never passes at 15-min — ATR(5)
  on 15-min bars typically sits above the upper bound (48 of 2,058 crosses
  passed). The few trades that occur are negative gross. The variant cannot
  rescue the strategy.
- **Exit-type split confirms the whipsaw mechanism:** recross exits (87% of
  trades) average −3.2 bps — the signature chop-straddling-the-midline failure
  the spec predicted. The positive bucket is entirely EOD exits (trend days
  that never recrossed, +23.5 bps, 13% of trades) — too rare to carry the book.
- **Honest post-hoc observation, NOT a tuning invitation:** the before-11:00
  bucket (n = 36) shows +4.2 bps (t = 1.9). This is a subgroup found *after*
  looking at results; under the spec's no-fishing rule it cannot be used to
  revive rsi-5050. If a morning-breakout hypothesis is ever pursued, it needs
  its own spec, its own mechanism argument, and validation on data this run
  has not consumed.

## Decision (per pre-registered gate)

**rsi-5050 is REJECTED at spec validation.** Both the 5-min baseline and the
15-min variant fail the gross-edge gate. Per SPEC.md this outcome forbids
threshold sweeps, band re-anchoring, or exit-rule changes on this data. Spec
status set to `retired`. Consistent with the provenance note in the spec: the
mechanical rules as written carry no edge — any edge in the user's remembered
discretionary experience lived in the untranscribed overlay (trade selection,
timing), not in these rules.

Reproducibility: full config + git commit recorded in `results_5min.json` /
`results_15min.json` in this directory.
