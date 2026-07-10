# Pre-registered research-screen criteria — cef-discount (closed-end fund discount reversion)

**Written 2026-07-10, BEFORE any evidence was read for this screen.** Same protocol as
the VRP (#8) and TSMOM (#9) screens: criteria and thresholds locked first; the verdict
is whatever the scorecard says. No criterion may be reweighted after evidence.

## Candidate

Buy US-listed closed-end funds trading at abnormally wide discounts to NAV; exit as the
discount mean-reverts (or at a fixed horizon). Long-only form preferred. Classic
references expected: Thompson (1978), Pontiff (1995, 1996 "costly arbitrage"),
Lee-Shleifer-Thaler (1991, investor sentiment).

## Why this candidate was chosen (boundary fit, argued before evidence)

- **Right-to-edge by construction:** CEFs have no creation/redemption mechanism, so the
  discount cannot be arbed directly; vehicles are small ($100M–1B), so institutional
  capital cannot scale in. This is the strongest a-priori answer in the searchable space
  to "why is this money still on the table for retail size."
- **Not the dead mean-reversion family:** the lab's 0-for-4 mean-reversion record
  (rsi-5050, spx-swing, keltner, turtle-soup) is price-history-only, short-horizon,
  liquid-index. This reverts toward an **observable fundamental anchor (NAV)** at
  multi-week/month horizons with a costly-arbitrage moat. Logged as a distinct family;
  if the evidence shows it behaves like price-only mean reversion, that distinction is
  void and the family base-rate applies.
- Low turnover (weeks–months) amortizes the cost bar; long-only avoids borrow;
  instruments are exchange-listed equities Alpaca can trade.

## Locked criteria (all six must PASS)

1. **Post-2015 persistence.** At least one independent test / dataset covering 2015 or
   later showing a discount-based CEF selection rule with positive net-of-cost
   performance. If the recent decade shows the effect statistically dead or reversed in
   US CEFs (the ToM failure mode), FAIL. Activist-fund compression of discounts counts
   against persistence if documented as regime-changing.
2. **Single canonical pre-registrable rule, no sweep.** The literature must converge on
   one signal form (e.g., absolute discount threshold OR discount z-score vs own
   history, one holding convention). If results hinge materially on threshold / z-window
   / universe filters / exit rule choices and published studies disagree (the ToM/VRP
   failure mode), FAIL.
3. **Cost bar clears with margin.** All-in retail round trip for liquid CEFs (spread +
   commission; CEF spreads expected materially wider than SPY) must be quantifiable and
   the documented edge per round trip ≥ 3× that cost at the strategy's natural turnover.
   Fund expense ratios and leverage costs count against the edge if the documented
   returns don't already net them.
4. **Mechanism intact + payer identified.** A structural payer must be identifiable
   (sentiment-driven retail sellers, tax-loss sellers, forced sellers) AND the
   costly-arbitrage moat must still be standing post-2015 — if activist arbitrage
   (e.g., Saba-style campaigns) has industrialized the trade, the moat is gone and this
   FAILS even if past returns look good.
5. **Tail haltable (grind, not gap).** Worst historical episode (expect: discount
   blow-outs in 2008 / March 2020) must be boundable by a daily-bar `halt_on_drawdown`
   — multi-day widening a halt can stop, not a single-session termination gap (the VRP
   failure mode). Embedded fund leverage counts against this.
6. **Data feasible and auditable.** Daily (or at worst weekly) historical NAVs for a
   liquid US CEF universe, ≥10 years including a crisis, obtainable at retail cost
   (free or cheap) in a form the lab can audit (the splice-audit discipline). No
   auditable NAV history → no honest pregate → FAIL. This criterion is decisive on its
   own: a strategy the lab cannot test does not get a spec.

## Downstream gates noted now (not part of this screen)

- Common-mode benchmark, locked before any OOS look: EDGE = discount-timed book minus
  **holding the same CEF universe unconditionally** (the TSMOM lesson — a wide-discount
  book must beat just owning cheap CEFs passively, or the timing is beta).
- IS/OOS split frozen at spec time; OOS must include a discount-blow-out stretch
  (no cherry-picking calm regimes).

## Verdict rule

Score each criterion PASS/FAIL with sources. Any FAIL on 2, 4, 5, or 6 is decisive
(they are structural). A FAIL on 1 or 3 may be argued only if the evidence is genuinely
mixed, and the default in a mixed case is FAIL (the CI-straddles-the-bar lesson:
unresolved leans fail).
