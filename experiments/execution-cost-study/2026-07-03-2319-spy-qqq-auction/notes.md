# Execution-cost study — real MOC/MOO auction costs for SPY/QQQ

**Status: method pre-registered before any measurement was run.** This section was
written first; results are appended below it afterwards and the decision rule is not
edited after the fact.

- git commit: 2f6b68725d8cbae5cf3820ae66a498d777aa9cae (working tree: overnight-long implemented, uncommitted)
- motivation: `experiments/overnight-long/2026-07-03-2105-qqqgate-oos/notes.md` —
  overnight-long is gross-positive in all 8 runs and REJECTED purely on a
  *conservative assumed* ~7 bps round-trip auction cost (QQQ-gated break-even ≈ 6.5 bps
  IS and OOS; clears the locked Sharpe ≥ 0.7 bar at ≤ 3 bps). This study replaces the
  assumption with evidence. It does NOT touch strategy parameters or success criteria.

## Why an MOC/MOO order's cost structure is different from a market order

A market-on-close / market-on-open order (Alpaca `cls`/`opg` TIF, $0 commission)
executes **in the exchange auction at the single official auction print** — it does not
cross the bid/ask book. So the realistic cost components are:

1. **Fill-reference error** — the backtest fills MOC at the last 5-min bar's `close`
   and MOO at the first 5-min bar's `open`. A real auction order fills at the
   *official* close/open (the daily bar's close/open). The measurable cost is the
   distribution of |bar-reference − official auction print|, per symbol, per fill site.
   This error is symmetric noise, not systematically adverse; charging it as an
   always-adverse cost is deliberately conservative.
2. **Spread** — zero for an auction fill (no book crossing). We still measure the NBBO
   half-spread in the last 10 s before 16:00 and first 10 s after 09:30 as the
   *fallback bound*: what a marketable limit order would pay if it missed the auction
   cutoff. Reported as context, not charged in the evidence-based cost.
3. **Regulatory fees (sell side only)** — SEC Section 31 (~$27.80/$1M ≈ 0.28 bps) +
   FINRA TAF ($0.000166/share, ≈ 0.004 bps at QQQ prices). Budgeted at **0.3 bps per
   round-trip**, charged on the open (sell) side.
4. **Auction impact** — our book is ~$10k notional (10% of $100k equity) against
   closing auctions that trade $2–10B+ in SPY/QQQ; participation < 0.001%. Treated as
   0, documented not measured.

## Pre-registered measurement method

- **Data:** existing dividend+split-adjusted files (Alpaca SIP): `{SPY,QQQ}_5m_adj.parquet`
  vs `{SPY,QQQ}_daily_adj.parquet` (2018-01 → 2024-12), and the same comparison on the
  fresh walk-forward files (2025-01 → 2026-07) once fetched. Sessions aligned on ET date;
  sessions missing from either file, or half-days without a 16:00-stamped bar, are dropped
  and counted.
- **Close-site error (bps):** `1e4 * |last_5m_bar.close − daily.close| / daily.close`
- **Open-site error (bps):** `1e4 * |first_5m_bar.open − daily.open| / daily.open`
- **Spread check:** ~24 sample days stratified across 2018–2026, NBBO quotes
  15:59:50–16:00:00 and 09:30:00–09:30:10 (Alpaca SIP historical quotes), median
  half-spread in bps.
- Script: `scripts/measure_auction_costs.py` (committed, reproducible).

## Pre-registered decision rule (locked NOW, before results)

- **Evidence-based per-fill cost** = p75 of the |error| distribution at that fill site,
  per symbol, pooled 2018–2026. p75 (not mean) of an |symmetric error| charged
  always-adverse is the conservative choice.
- **Config mapping:** `half_spread_bps: 0.0` (auction fills), `close_slippage_bps: p75_close`,
  `slippage_bps: p75_open + 0.3` (fees ride the sell side), `commission_per_unit: 0.0`,
  `stop_slippage_bps` unchanged (irrelevant — no resting stops).
- **Judgment:** re-run SPY-gated and QQQ-gated IS + OOS at the evidence-based cost, and
  run the untouched walk-forward window (2025-01-02 → 2026-07-02) at BOTH the original
  locked ~7 bps cost and the evidence-based cost. A config **passes** iff, at the
  evidence-based cost, it clears the *original pre-locked* overnight-long bar — OOS net
  Sharpe ≥ 0.7 with positive net return — **and** the walk-forward run confirms
  (net Sharpe ≥ 0.7, net > 0) at the evidence-based cost. Anything less: overnight-long
  stays rejected and we stop iterating on it.
- No strategy parameter changes of any kind. Same seeds/windows as the original runs.

---

## Results (appended after the run; see metrics.json)

2,135 sessions per symbol, 2018-01-02 → 2026-07-02 (half-days dropped at the close
site: 1 SPY / 4 QQQ). All 24 quote windows returned data.

| component (bps)                    | SPY    | QQQ    |
|------------------------------------|--------|--------|
| close-site abs error p50 / p75     | 0.80 / 1.51 | 1.12 / 2.31 |
| open-site abs error p50 / p75      | 0.00 / 0.22 | 0.00 / 0.29 |
| NBBO half-spread 15:59:50–16:00 (median) | 0.13 | 0.17 |
| NBBO half-spread 09:30–09:30:10 (median) | 0.18 | 0.30 |
| regulatory fees (sell side)        | 0.3    | 0.3    |
| **evidence-based round-trip (p75 rule)** | **2.03** | **2.90** |

Signed mean errors are ≈0 (−0.24 to −0.02 bps): the bar-reference error is symmetric
noise as expected, so charging p75 always-adverse remains conservative. The open site
is near-exact (p50 = 0: the first 5-min bar's open usually IS the opening auction
print); the close site carries almost all of the error (the official closing print can
land outside the last bar's aggregation). Tail check (CORRECTED post-review — the
original text here called the SPY 279 bps max "one late-print outlier"; that was
wrong): the largest close-site errors are **stress-clustered** — 2020-03-12/18/09/16/24
at 279/226/69/68/66 bps and 2025-04-09 at 96 bps. Fill-reference error is
regime-heteroskedastic; a flat p75 charge understates dispersion on exactly the
high-gap nights (partially mitigated for the gated strategy: the 200-SMA gate was off
through much of March 2020).

**Vs the assumption:** the locked model charged ~7 bps round-trip; measured reality
for a small auction order is **2.0 (SPY) / 2.9 (QQQ) bps** — inside the ≤3 bps region
where QQQ-gated cleared the locked Sharpe bar in both IS and OOS in the sensitivity
table. Judgment runs: `experiments/overnight-long/2026-07-03-2323-*` (master verdict
v2 in `qqqgate-wf-evcost/`).

## Post-review addenda (quant-reviewer: TRUST-WITH-CAVEATS)

- **Protocol flaw (accepted; material at the margin):** the p75 measurement pooled
  2018–2026, which includes the walk-forward judgment window. Settled vintage table
  (both fill sites re-measured, independently verified):

  | vintage                    | QQQ RT bps | SPY RT bps | QQQ OOS Sharpe (engine conv.) |
  |----------------------------|------------|------------|-------------------------------|
  | pooled 2018–2026 (used)    | 2.899      | 2.030      | 0.715 |
  | pre-WF only 2018–2024      | 3.175      | 2.065      | ~0.652 (fails 0.7) |
  | OOS-period-matched 2022–24 | 2.442      | 1.627      | ~0.817 (passes) |

  The OOS verdict is cost-vintage-ambiguous at the margin; the WF verdict is not
  (passes at 2.9 and stays net-positive at 7 bps). Next cost study must exclude the
  judgment window by construction. Note the pre-WF number is inflated by 2018–21
  COVID-era close-site noise that belongs to the IS window — period-matching is
  arguably the most defensible charge, but none of the three was pre-registered as
  primary beyond the pooled rule.
- **Tail note:** p75-always-adverse is conservative in expectation (signed bias is
  ~0.1–0.24 bps *in the strategy's favor*; true expected cost ≈ 0.5–0.6 bps RT) but
  under-represents close-site error on high-gap stress nights (see corrected tail
  check above) — carried into the risk notes, not the cost model.
- **Phantom half-day 16:00 bars:** on ~2 early-close sessions/yr the 5m files carry a
  16:00-stamped bar built from after-hours prints; these leaked into the close-site
  sample. Excluding them *lowers* p75 (QQQ 2.314 → 2.294), so the published number is
  conservative. They also let the backtest "fill MOC" at nonexistent prints (~1% of
  trades) — folded into the calendar-awareness paper prerequisite.
- **Live-mechanics gap found:** Alpaca's `cls` cutoff (~15:45–15:50 ET) precedes the
  strategy's 15:55 decision bar, and ~20-share QQQ odd-lot auction eligibility is
  unverified — a small auction order fills at the official print only if submitted in
  time and accepted. Blocking prerequisite for paper; the measured 2.9 bps is a
  hypothesis until paper fills confirm it (auto-reject tripwire: > ~4–5 bps measured
  in paper). See master verdict v2.
