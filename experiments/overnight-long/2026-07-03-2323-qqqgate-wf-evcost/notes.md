# overnight-long — MASTER VERDICT v2 (execution-cost study + walk-forward judgment)

**Verdict: BORDERLINE OOS, WALK-FORWARD-CARRIED → qualified paper candidate.**
NOT "clears the locked bar" — see the Sharpe-convention finding below. Supersedes the
v1 verdict in `../2026-07-03-2105-qqqgate-oos/notes.md` (REJECT at the assumed ~7 bps
cost). Method and decision rule for this re-judgment were pre-registered BEFORE
measurement in `experiments/execution-cost-study/2026-07-03-2319-spy-qqq-auction/`.

- run: QQQ gated, walk-forward 2025-01-02 → 2026-07-02, evidence-based costs
- data: `data/QQQ_5m_adj_wf.parquet` + `data/QQQ_daily_adj_wf.parquet` — fetched
  2026-07-03, **never used in any prior decision** (true walk-forward)
- this run: 318 trades | net +1.69% | gross +2.60% | max DD −1.0%
  | Sharpe 1.14 (engine convention) / **1.08 (corrected, see below)**

## What changed and why (no goalposts moved)

The v1 REJECT rested entirely on an *assumed* ~7 bps round-trip auction cost. The
execution-cost study measured the real cost of a small MOC/MOO auction order:
**SPY 2.03 bps, QQQ 2.90 bps round-trip.** Strategy parameters, windows, sizing, and
every success bar are byte-identical to the SPEC. Quant-reviewer reproduced every
number bit-for-bit, found no lookahead (WF SMA warm by 2024-10-17; strictly-prior
daily lookup; deterministic runs) and no instrument-shopping (SPY judged at its own
cheaper cost still fails).

## Judgment runs (all at `2026-07-03-2323-*`; engine-convention Sharpe)

| run                | trades | net    | gross  | Sharpe | max DD |
|--------------------|--------|--------|--------|--------|--------|
| QQQ gated evcost IS  | 855  | +3.68% | +6.15% | 0.84   | −2.0%  |
| QQQ gated evcost OOS | 498  | +1.54% | +2.95% | 0.715  | −1.6%  |
| QQQ gated WF evcost  | 318  | +1.69% | +2.60% | 1.14   | −1.0%  |
| QQQ gated WF locked-7bps | 318 | +0.37% | +2.53% | 0.22 | −1.2%  |
| SPY gated evcost IS  | 824  | +3.51% | +5.18% | 1.14   | −1.0%  |
| SPY gated evcost OOS | 530  | +0.60% | +1.64% | 0.34   | −1.8%  |
| SPY gated WF evcost  | 321  | +0.84% | +1.47% | 0.80   | −1.0%  |
| SPY gated WF locked-7bps | 321 | −0.71% | +1.45% | −0.76 | −1.4%  |

**SPY gated: REJECT stands** — OOS 0.34 < 0.7 and < buy-and-hold's 0.57, exactly as
the v1 cost-sensitivity table predicted (SPY OOS break-even was only 2.9 bps).

## MAJOR quant-review finding 1: the 0.715 OOS "pass" is a Sharpe-convention artifact

`core/backtest/metrics.py:_daily_equity` builds the equity curve from **trade days
only**; the 200-SMA gate keeps the book flat ~34% of OOS days, and those days vanish
from the denominator before √252 annualization. Its docstring assumption ("the
strategy is flat overnight") was written for intraday strategies and is false here.
Recomputed with flat sessions as zero returns over the true session calendar
(independently reproduced, matches the reviewer):

| window | engine (trade-days) | corrected (all 752/375/1008 sessions) | 0.7 bar |
|--------|--------------------|----------------------------------------|---------|
| IS     | 0.843              | 0.775                                   | ✓       |
| OOS    | 0.715              | **0.584**                               | **✗ FAIL** |
| WF     | 1.141              | **1.085**                               | ✓       |

Apples-to-apples the benchmark gate still passes OOS (0.584 vs B&H 0.503, thin), and
in WF the strategy slightly **loses** to B&H (1.085 vs 1.119) — with max DD −1.0% vs
B&H's −22.8% on ~10× the exposure. Mitigant: the same metrics code produced the
original REJECT, so the convention was not chosen to pass. But a 0.715-vs-0.7 verdict
that reads 0.584 under the textbook convention is **not a pass; it is borderline**.

## MAJOR quant-review finding 2: cost-vintage sensitivity brackets the OOS verdict

The p75 measurement pooled 2018–2026, including the WF judgment window (pre-registered
but, in hindsight, a protocol flaw). Engine-convention OOS Sharpe across defensible
cost vintages: **0.652 at pre-WF-only costs (3.175 bps) = FAIL; 0.715 at pooled
(2.90); 0.817 at period-matched 2022–24 costs (2.44 bps) = PASS.** The OOS result is
genuinely cost-ambiguous at the margin. The WF run is not: it passes at 2.9 bps AND
stays net-positive at the old locked 7 bps.

## Other review findings (recorded, non-verdict-changing)

- **Phantom half-day 16:00 bars:** the 5m files stamp bars through 16:00 on ~2
  early-close sessions/yr built from after-hours prints; the backtest "fills MOC"
  there at prints that cannot exist (~1% of trades). Excluding them *lowers* the
  measured cost p75, so direction is conservative. Confirms — and slightly worsens —
  the known calendar-awareness prerequisite.
- **Fill-error tails are stress-clustered, not one-off:** the largest close-site
  errors are March 2020 (279/226/69/68/66 bps) and 2025-04-09 (96 bps). A flat
  2.9 bps charge understates dispersion on exactly the high-gap nights (partially
  mitigated: the gate was off through much of March 2020). Worst-night accounting at
  p95-style fill error ≈ 1.13·R — still inside 2·R.
- **Economic materiality:** net edge ≈ 3.2 bps/night on ~$9.8k notional ≈ $3/night;
  the model credits idle cash (90%+) at zero while T-bills paid ~12% cumulative over
  the OOS window. Not a SPEC bar, but the absolute P&L is small against operational
  risk. Sizing up is Sharpe-neutral but possible.
- **Live `cls`/`opg` mechanics unmodeled:** Alpaca's MOC cutoff (~15:45–15:50 ET)
  precedes the 15:55 decision bar. The gate uses the *prior day's* close, so deciding
  earlier loses nothing informational — but the live port differs from the backtest
  clock and must be re-run once fixed. Odd-lot auction eligibility (~20 QQQ shares)
  is also unverified. The 2.9 bps figure is a **hypothesis until paper fills confirm it**.

## Decision (reviewer: TRUST-WITH-CAVEATS; paper candidacy: qualified YES)

**QQQ-gated overnight-long is a qualified paper candidate: borderline OOS
(0.584–0.715 depending on convention; cost-vintage range 0.65–0.82), carried by a
robust walk-forward pass on untouched data (1.08–1.14, net-positive even at 7 bps).**
Paper is cheap and is the only way to test the load-bearing 2.9 bps cost hypothesis.
Blocking prerequisites before paper:

1. Fix the dead sparse-order 2·R daily-loss limit (`core/risk/sizing.py`) — confirmed
   structurally dead for this strategy (day-start equity sampled after the morning
   exit realizes the overnight loss).
2. Market-calendar-aware session handling (half-days: skipped entries, stranded
   positions, phantom 16:00 bars in the data).
3. Resolve the MOC-cutoff vs 15:55 decision-bar sequencing and re-run.
4. Fix `core/backtest/metrics.py` to zero-fill flat sessions (or report both
   conventions); all future judgments quote the corrected number.
5. **Auto-reject tripwire in paper:** measured real fill cost > ~4–5 bps round-trip,
   or any pattern of odd-lot auction ineligibility → back to REJECT, no relitigation.

Paper promotion itself requires explicit user sign-off per CLAUDE.md.
