# keltner-reversal — pre-scoring gross-edge diagnostic (spec validation)

- **Date**: 2026-07-07
- **Script**: `scripts/pregate_keltner.py` (outside the engine, per SPEC.md PREGATE)
- **Data**: `data/DIA_3m.parquet` (sha256 `709341918b…4632cc`) signal, +
  `data/DIA_15m.parquet` (sha256 `c4c5c3b9…f2344`) HTF trend. Alpaca SIP, raw,
  RTH, close-stamped, 2017-12-01..2026-07-06. Aggregation-audited clean (3m→15m
  OHLC exact, 3m→daily 0 violations).
- **Window**: IN-SAMPLE ONLY, 2018-01-01..2022-12-31 (1,259 sessions). OOS
  (2023-2024) and WF (2025→) hard-sliced out — **never read**.
- **Gate (LOCKED in SPEC.md before the script was written)**: REJECT at spec
  validation if IS mean gross per trade ≤ 2.5 bps (the locked cost bar), **or**
  if it does not beat the matched trend-direction baseline.

## Verdict: **REJECT at spec validation** — 8th candidate death

The setup is **gross-negative before a single basis point of cost**, and it
underperforms simply being long DIA in the trend for the same clock time.

| Metric | Result | Bar | |
|---|---|---|---|
| IS mean gross / trade | **−0.839 bps** | > 2.5 bps | **FAIL** |
| Edge vs matched baseline | **−2.744 bps** (strat −0.839 vs baseline +1.905) | > 0 | **FAIL** |
| t-stat (all) | −1.90 | — | negative |
| Long side | −1.026 bps (n=439, t=−2.07) | — | fails |
| Short side | −0.427 bps (n=199, t=−0.48) | — | fails |

n = 638 filled trades (127.6/yr), fill rate 54.3% (538 of 1,176 signals expired
unfilled in 3 bars). **Every IS year negative** except 2022 (+0.17 bps): 2018
−1.27, 2019 −0.49, 2020 −1.58, 2021 −0.82.

## Why it failed — the payoff geometry is real but the tails eat it

The mechanics behaved exactly as the hypothesis described, and still lost:

- **Targets hit often and pay little; stops are rare-ish and pay a lot** — the
  classic negative-skew mean-reversion signature. Exit split: target 59.9% at
  **+5.41 bps** (86.9% hit), stop 36.8% at **−10.52 bps**, time 3.3% at −6.15.
  Blend: 0.599·5.41 − 0.368·10.52 − 0.033·6.15 = **−0.84 bps**. The median trade
  is *positive* (+0.67 bps) — but the mean, which is what pays the bills, is
  dragged under water by the stop tail. R:R looked favorable on paper; realized,
  the stop distance (median 8.9 bps) plus gap-through on the stops (worst trade
  −1.46R) overwhelms the small +5 bps midline reversion.
- **The reversal adds negative value.** The matched baseline — trend-direction
  open-to-open over the identical fill→exit bars — earned **+1.905 bps**. Just
  holding DIA in the 15-min-uptrend direction for the same ~1-bar clock time beat
  the reversal setup by 2.7 bps. The "fade the stab, ride back to the midline"
  structure is worse than doing nothing clever.
- **Median hold = 1 bar (3 min).** The midline is close and resolves fast; there
  is no room for the reversion to pay more than costs would take.

## The reject is robust — not an artifact of the worst-case ordering

The one modeling choice with latitude (the LOCKED intrabar **stop-before-target**
ordering) was stress-tested by re-running the exit under the *optimistic*
ordering (target-before-stop), the theoretical ceiling:

| Exit ordering | mean gross | vs 2.5 bps bar |
|---|---|---|
| **LOCKED worst-case** (stop first) | **−0.839 bps** | fail (scored) |
| Optimistic ceiling (target first) | −0.703 bps | fail |

Only 0.14 bps separates them — most stop-hitting bars are genuine losers that
never touch the target, so the ordering assumption barely moves the number. Even
the impossible best case is 3.2 bps under the bar and still negative. There is no
version of the fill accounting that rescues this. Failure is at the **signal
level**, exactly like `intraday-momentum` and `spx-swing`.

## Diagnostics (never gates)

- **Aggressive opposite-band exit** (diagnostic-only): mean −0.878 bps (t=−0.90),
  target reached only 24.6% of the time — worse skew, no rescue there either.
- ToD: midday +0.33 (n=275, only bucket ~flat), open −1.98, close −1.63 — no
  time-of-day pocket clears the bar (and slicing to one would be a forbidden
  sweep).
- Realized risk median 0.089% (notional cap binds 98% of trades — tiny 3-min
  stop distances, as predicted in the SPEC).

## Implementation note (flagged for the record)

The frozen spec is internally under-determined on one point: it says "reset
indicators each session" but the HTF trend uses EMA(13) on 15-min bars with only
a "≥3 completed 15-min bars" warm-up — an EMA(13) cannot both reset each session
and be valid after 3 bars. Resolved by the only coherent reading: the **3-min
band indicators (E, A) reset per session** (the Open Q3b rationale is about
keeping the overnight gap out of the intraday ATR bands), while the **15-min
trend EMA is a continuous cross-session series** (a slow trend context, not a
band). This affects only the direction *filter*, never the edge measurement, and
no parameter was swept. Given the reject is gross-negative on **both** sides and
robust to the exit ordering, this choice is not load-bearing on the verdict.

## What survives

Nothing new to build — the pregate did its job for one session and no engine or
strategy code was written. `scripts/pregate_keltner.py` and the audited
`data/DIA_3m.parquet` (first 3-min DIA in the lab) are the only artifacts. The
intended reuse (orb's intrabar-stop core) was never needed. Per the LOCKED
no-rescue clause: no parameter/HTF/instrument shopping, no OOS look — the OOS and
WF windows remain sealed.
