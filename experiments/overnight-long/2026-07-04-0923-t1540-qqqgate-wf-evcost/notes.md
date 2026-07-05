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

## Quant-review outcome (2026-07-04, post-suite)

Independent quant-reviewer pass over commits `6d4c718` + `4f5f2ef`:

- **(i) t1540 re-run results: TRUST-WITH-CAVEATS.** No lookahead found; zero-fill
  Sharpe correct and conservative; the calendar/MOC fixes remove genuinely
  fictitious fills. "Measurement clean."
- **(ii) paper execution path: DO-NOT-TRUST as first committed** — three blockers,
  all fixed the same day before any paper order: risk-breaker state now persists
  across the one-process-per-cycle lifetime (`paper-risk-state.QQQ.json`); crash
  recovery on the exit morning exits TODAY's open (was: skipped to the next
  session, holding an extra night); rejected/unfilled MOC/OPG orders are handled
  and logged, with a fallback market exit (was: uncaught TimeoutError). Plus:
  SIP feed is now required for the overnight paper mode (IEX would measure
  against non-official prints).
- **Reviewer caveat kept on the record (candidacy, not measurement):** the
  pre-registered OOS bar (≥0.7) failed under both conventions; the carry is a
  1.5-year walk-forward whose Sharpe standard error (~1.0 annualized) makes
  1.0749 statistically indistinguishable from the failed OOS 0.55 — the reviewer
  characterizes promoting on the WF window as goalpost-moving even if honestly
  documented. The user approved paper on exactly this "borderline OOS,
  WF-carried" basis; the paper gate in SPEC.md was rewritten after review to be
  honest that **Alpaca paper (simulator) fills can falsify but never confirm the
  2.90 bps cost hypothesis**, which therefore remains UNVALIDATED after paper
  and needs a quote-based study (or explicit user decision) before any further
  promotion.
- Isolation evidence committed: `2026-07-04-0940-t1540-isolation-study/`
  (15:40-shift neutrality reproducible; v2-anchor reproduction limits stated).
- Minor open items (accepted, on the record): the Sharpe denominator uses
  sessions present in the data, not the full XNYS calendar (parquet ends
  2024-12-30, so OOS counts 752 not 753 — 4th-decimal effect); the 200-SMA gate
  runs on back-adjusted closes (borderline gate days can differ live vs
  backtest); `_annualized_return` compounds the arithmetic mean (cosmetic).
- **Amendment (2026-07-04, post-review):** the read-only preflight
  (`scripts/preflight_paper.py`) found the account key has NO real-time SIP
  entitlement — the earlier "runner refuses IEX" fix would have failed Monday's
  decision poll outright. Per user decision, the runner was adapted to the free
  tier: decision bars on IEX real-time; official auction prints always SIP
  history fetched >15 min delayed, with a partial-day guard so a clamped daily
  bar can never report a mid-session price as the official close. Preflight also
  found the paper account at $10k (not the assumed $100k); user resets it to
  $100k in the Alpaca dashboard before Monday.
- **Amendment (2026-07-05, feed upgrade):** the user subscribed to Alpaca **Algo
  Trader Plus** (real-time SIP entitlement) on 2026-07-05, and the paper path was
  upgraded the same day (branch `sip-feed-upgrade`): decision bars now read **SIP**
  (`execution.feed: sip` in the paper config), and official auction prints are
  fetched **minutes after the auction** via a runtime entitlement probe — the
  free-tier handling (now-16min SIP clamp + slow retries) stays as an automatic
  fallback, and the partial-day close guard is kept on all feeds. **Provenance
  note for the week-1 fill analysis:** switching feeds between sessions is a small
  measurement change — fills logged before/after differ in decision-bar feed and
  print-fetch latency, though the official reference prints are SIP daily bars on
  both paths and paper fills come from the same Alpaca simulator regardless. As of
  this writing **no fills have been logged on either policy**. **User decision
  2026-07-05: merged to main BEFORE the first paper session (2026-07-06)** — the
  entire fill log therefore sits on the SIP policy from session 1; there is no
  free-tier-policy segment to account for in the week-1 analysis.
