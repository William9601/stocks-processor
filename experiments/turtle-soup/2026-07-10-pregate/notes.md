# turtle-soup — pregate run notes (2026-07-10)

**Verdict: REJECT at spec-validation (pregate). 11th candidate death.**

Sequence, for the record: spec drafted → all 12 open questions resolved to recommended
defaults → spec APPROVED/FROZEN and committed (db05fb7) → data-verification cell →
`scripts/pregate_turtle_soup.py` written → run on IS only. The gate rule existed in
the frozen SPEC before the script did. OOS (2017-01→2024-12) and WF (2025→) were
hard-sliced out before any computation and were never read.

## Gate results (locked rule)

- IS mean gross per trade: **−12.404 bps** (t = −1.44) vs bar > 5.0 bps → **FAIL**
- EDGE(IS) vs matched same-instrument/direction/holding-clock drift baseline:
  **−12.781 bps** vs bar > 0 → **FAIL**
- Filled trades: 399 vs ≥ 200 → pass

Full numbers: `pregate_results.json` (locked worst-case ordering, the binding run) and
`pregate_results_optimistic_ceiling.json` (diagnostic only). Trade logs:
`trades_is.csv`, `trades_is_optimistic_ceiling.csv`.

## What killed it

1. **Stop-tail negative skew (the keltner mode, pre-named in the SPEC).** 246/399
   fills (62%) exit on the stop at −70/−103/−128 bps means by subtype; 153 (38%) reach
   the 4-session MOC at +111 mean. Median trade −37 bps, hit rate 0.313.
2. **No underlying signal.** Hold-day mark curve ignoring the stop is negative at
   every horizon 1–6 (−0.7 … −11.7 bps). No exit day inside the published 2–6 window
   would have been gross-positive even stopless — the failure is the setup, not the
   stop geometry, and not our day-4 choice.
3. **Ordering-robust both ways.** Optimistic ceiling = −13.1 bps (worse): dodging the
   same-bar stop mostly converts the loss into a larger overnight stop-gap
   (stop_gap 45 → 117 fills, −154 bps mean).

## Flow / diagnostics of note

- 860 setups scored, 852 orders armed, fill rate 0.468 → 399 trades over 9.75 IS yrs.
- Concurrency never binding: max 3 of 4 slots, 5 setups ever skipped for slots.
- Both sides negative (long −7.5 / short −17.5). Equities −24.9, bonds +5.0 (n=100,
  noise). Every year 2008–2013 negative. Worst trade −600 bps = −4.0 R (overnight
  gap; the OOS 3R bar would also have failed, moot).
- Median realized risk (entry→stop) 67 bps; median penetration depth 48 bps.

## Data-verification cell (pre-declared in SPEC)

- All 8 basket parquets carry full non-null OHLCV over the full range; common start
  2007-03-01 (UUP); sha256[:16] recorded in the results JSON. **PASS.**
- **Finding:** bars are midnight-ET date-stamped, not session-close stamped (the SPEC's
  "builder writes close-stamped" assumption was wrong). Harmless here (date indexing);
  would have required the fomc-mode re-stamp before the engine's daily-MOC path if the
  candidate had survived. Data files untouched (tsmom results are hashed against them).

## No-rescue clause

Binds as frozen: no parameter/variant/universe shopping, the same-day variant and the
book's re-entry rule stay out of scope, splits are not promotion paths. OOS/WF remain
unread. Post-mortem lives in `strategies/turtle-soup/SPEC.md`.
