# overnight-long — MASTER VERDICT v3: 15:40 decision bar + calendar/metrics fixes (2026-07-04)

**Verdict: the paper candidacy STANDS.** The 15:40 decision-bar move (required by
Alpaca's ~15:45 MOC submission cutoff) does not degrade the strategy; the small
declines vs the v2 numbers are caused by the *bug fixes themselves* (honest
corrections, not the strategy change) and the walk-forward that carries the
candidacy is intact.

## What changed since verdict v2 (`2026-07-03-2323-qqqgate-wf-evcost`)

All four blocking fixes from SPEC "Result v2" are in (commit `6d4c718`):

1. **Zero-filled Sharpe is now the headline** (`sharpe`); the old trade-days-only
   convention is `sharpe_trade_days`. v2 anchors reproduced exactly before any
   behavior change: OOS 0.715→0.5843 (752 sessions), WF 1.141→1.0845 (375),
   IS 0.843→0.7747 (1008).
2. **2·R daily-loss lock is live** (every-bar risk hook, day anchored at prior
   session's closing equity). It never fires in any of these windows (worst
   night ≈1.1·R < 2·R), so it changes no numbers — it just actually works now.
3. **Calendar-aware sessions**: phantom post-13:00 half-day bars filtered
   (2018-07-03, 2024-11-29, 2024-12-24 verified in the parquet); MOC fills only
   on the session-final bar; half-days now trade (decision 12:40, fill 13:00)
   instead of being skipped. Trade counts +2-3 per window.
4. **Decision bar 15:55 → 15:40** (`decision_offset_minutes: 20`). The regime
   gate uses the *prior day's completed close*, so nothing informational is lost.

## Results (this suite, all 4 runs at 15:40)

| run | sharpe (zero-fill) | sharpe_trade_days | net | maxDD | trades |
|---|---|---|---|---|---|
| evcost IS 2018-2021 | **0.7749** | 0.8420 | +3.67% | −2.01% | 858 |
| evcost OOS 2022-2024 | **0.5516** | 0.6734 | +1.45% | −1.56% | 500 |
| evcost WF 2025-01→2026-07 | **1.0749** | 1.1306 | +1.68% | −1.03% | 318 |
| locked-7bps WF | **0.2279** | 0.2108 | +0.35% | −1.19% | 318 |

## Attribution: the 15:40 move is a wash; the fixes moved OOS

Isolation runs (same code, `decision_offset_minutes` 5 ≈ old 15:55 vs 20):

- offset 5 vs 20 differs by ≤0.004 Sharpe in every window, direction mixed
  (15:40 slightly *better* in 3 of 4). **The strategy change itself is neutral**,
  as the causal argument predicts (gate on prior close; same MOC fill print).
- The deltas vs v2 anchors are from the calendar fixes: OOS zero-fill
  0.5843 → 0.5516 (trade-days 0.7150 → 0.6734), IS ~flat (0.7747 → 0.7749),
  WF-evcost 1.0845 → 1.0749, WF-locked 0.2233 → 0.2108 (still net-positive).
  Removing ~2/yr phantom MOC fills and trading half-days is a *correction of
  fictitious fills*, not tuning; the slightly lower OOS is the truer number.

## Judgment against the locked bars (unchanged bars, both conventions reported)

- OOS net Sharpe ≥ 0.7: **0.5516 zero-filled — below the bar** (0.6734 under the
  old convention). This was already the honest v2 reading ("borderline, not a
  pass"); it is now slightly weaker. OOS expectancy stays positive (+1.45% net,
  500 cycles), DD −1.56%, B&H OOS gate still passes (QQQ B&H OOS ≈ 0.50).
- **Walk-forward 2025-01→2026-07 carries the candidacy, as in v2: 1.0749
  zero-filled / 1.1306 trade-days, net +1.68%, DD −1.03%, and still
  net-positive (+0.35%) at the old locked 7 bps costs.**
- No parameters were tuned; the only strategy change (decision offset) was
  forced by a broker constraint and shown neutral.

**Disposition: qualified paper candidate, QQQ gated only — proceed to paper per
the pre-registered gate in SPEC.md (4 weeks / ~20 fills; auto-reject if measured
round-trip cost > 4-5 bps or recurring odd-lot auction rejections).**
