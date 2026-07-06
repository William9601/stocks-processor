# fomc-drift — pregate (IS only) — 2026-07-06

**Verdict: PASS.** The documented pre-FOMC drift reproduces in-sample. `EDGE(IS) =
30.35 bps/event` (t ≈ 3.4) clears both frozen gates — the 2.0 bps cost bar and the
20 bps reproduction bar. Second pregate pass in the lab's history (after ORB).
Proceed to implementation → engine IS cross-check → the ONE pre-registered OOS look.

## What ran

Two blocking data tasks then the pregate, all outside the backtest engine, all on
the **IS window only (1994-01-01 → 2015-12-31)**. OOS (2016–2024) and WF (2025→) were
**not read** — `scripts/pregate_fomc.py` hard-slices the bars at 2015-12-31 before any
computation, so nothing post-IS can leak into this number.

1. **Splice extension** (`scripts/build_spy_eod_splice.py --yahoo-start 1993-06-01`):
   the audited self-adjusted SPY daily series, previously 2002-09-03→, rebuilt back to
   1993-06-01 (8,329 sessions → 2026-07-02). Byte-identical to the spx-swing splice
   over all 5,996 shared sessions (max daily-return divergence 0.000000 bps). The new
   1993–2002 segment's CRSP arithmetic agrees with Yahoo's own adjusted series to max
   0.014 bps. Dividend cadence is a clean ~4/yr every year (2004 shows 5 — the verified
   MSFT-driven special distribution, ex-date 2004-11-15). The report's locked
   level-check still "fails" at max 10.8 bps — this is the **pre-existing spx-swing
   deviation** on 2016-02-29 inside the old overlap region (user-accepted on the record
   for spx-swing: Yahoo reference-print quality, mean 0.89 bps), unchanged by and
   unrelated to the extension.
2. **FOMC calendar** (`scripts/build_fomc_calendar.py` → committed
   `strategies/fomc-drift/fomc_calendar.csv`): transcribed from the Fed's own
   per-year historical pages (1994–2020) and the current calendar page (2021–2026).
   Audit PASS — 263 scheduled meetings, 8/year every full year (2020 = 7 held + 1
   cancelled, the superseded Mar 17–18 meeting carried as `type=cancelled` per the
   spec's point-in-time rule), zero T−1 mapping errors across 259 mapped meetings,
   monotone with no overlaps. The 10 non-Tue/Wed T's are all legitimate: two-day
   meetings ending Thursday (late-June and mid-September clusters) and election-week
   November meetings pushed to Wed–Thu (2018, 2020, 2024). Conference calls (39),
   the one 2020 emergency session, and notation votes (5) are recorded but never
   traded.

## Result (IS 1994–2015, n = 176 scheduled events; gross, self-adjusted)

| | bps |
|---|---|
| `FOMC(IS)` mean event return close(T−1)→close(T) | **33.50** |
| `BASE(IS)` mean non-event day close-to-close (n=5,513) | 3.15 |
| **`EDGE(IS)` = FOMC − BASE** | **30.35** |
| SE per event | 8.93 |
| t (event vs 0) / t (edge) | 3.75 / 3.4 |
| net per event (− 2.0 cost) | 31.5 |
| hit rate (gross > 0) | 59.7% |

Against the documented ~45 bps (Lucca-Moench, 1994–2011) with SE ≈ 9: our IS edge is
~two-thirds the headline, comfortably above the half-strength (20 bps) reproduction
bar. Consistent with our IS extending to 2015 (into the era Kurov flags as the onset
of decay) and with self-adjustment removing spurious ex-div pops.

## Diagnostics (pre-registered DIAGNOSTIC-ONLY — never gates, never a promotion path)

- **Decomposition:** overnight close(T−1)→open(T) = +11.9 bps; announcement-day
  open(T)→close(T) = +21.7 bps. The majority of the captured return is the
  announcement-day session, not the pure overnight leg — our window holds both by
  construction, so this is captured, but it means the strategy is materially exposed
  to the 14:00 reaction (the hawkish-surprise failure mode in the spec).
- **Boguth missed-onset** close(T−2)→close(T−1) = +16.1 bps: there is real drift the
  day *before* our entry that we do not capture. This is the migration/front-running
  risk the spec flagged. It is **not** a license to move the entry to T−2 — recorded
  and watched only.
- **Press-conference split** (pre-2019): PC meetings (n=20, all 2011–2015) +61.9 bps
  vs non-PC (n=156) +29.9 bps. Directionally matches Boguth et al., tiny sample.
- **Concentration / regime-dependence (the honest caveat for the OOS):** the IS edge
  is heavily crisis-weighted — 2008 +145.7, 2009 +115.8, 2007 +61.1, 2012 +63.1 bps —
  while several calm years are negative (1994 −8.4, 1997 −17.0, 2001 −24.3, 2005 −4.3,
  2013 +6.1). Median event +29.9, 10%-trimmed mean +31.9 (so it is not one-outlier
  driven), but the year-level pattern is exactly the uncertainty-state-dependence the
  spec pre-registered as the falsifiable hypothesis. The OOS deliberately front-loads
  the 2016–2019 calm/ZLB dead zone before the 2020+ revival — the blend across both is
  the test, with no per-era rescue. Worst IS event 2011-09-21 (Operation Twist) −294.6
  bps; best 2008-12-16 (ZIRP) +470.7 bps.

## Reproducibility

- Bars `data/SPY_daily_adj_spliced.parquet`, calendar
  `strategies/fomc-drift/fomc_calendar.csv` — sha256 (16) recorded in
  `pregate_results.json` (`bars_sha256_16`, `calendar_sha256_16`).
- Frozen params: IS 1994-01-01 → 2015-12-31, cost RT 2.0 bps, cost bar 2.0, repro bar
  20.0. Git commit recorded in each JSON.
- Per-event IS table: `pregate_events_is.csv`. Splice audit: `splice_report.json`.
  Calendar audit: `fomc_calendar_audit.json`.

## Next (per the SPEC funnel)

Implement `strategies/fomc-drift/` against the core interfaces — daily-bar MOC entries
and exits via existing `FillTiming.NEXT_CLOSE` (no core extension). Engine IS run must
reproduce this pregate to rounding (the ORB cross-check pattern). Then the **one**
pre-registered OOS look (2016–2024) plus its 1.5×-cost (3.0 bps) companion, then
quant-reviewer, then verdict against the frozen bars. **This is where the scarce
out-of-sample look gets spent — a natural gate to confirm with the user first.**
