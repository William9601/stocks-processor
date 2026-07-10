# Pre-registered research-screen criteria — insider-cluster (insider cluster buying)

**Written 2026-07-10, BEFORE any evidence was read for this screen.** Same protocol as
the VRP (#8), TSMOM (#9), and cef-discount (#10) screens: criteria and thresholds
locked first; the verdict is whatever the scorecard says. No criterion may be
reweighted after evidence.

## Candidate

Buy US stocks after multiple insiders (officers/directors) purchase their own
company's shares in the open market within a short window ("cluster buys"), reported
on SEC Form 4. Long-only. Expected classic references: Lakonishok & Lee (2001), Jeng,
Metrick & Zeckhauser (2003), Cohen, Malloy & Pomorski (2012, "Decoding Inside
Information" — opportunistic vs routine).

## Why this candidate was chosen (boundary fit, argued before evidence)

- **Right-to-edge candidate story:** insiders are legally-informed traders; the signal
  is strongest in small caps where institutional capital cannot deploy meaningful size
  — capacity constraint as moat. Retail-scale capital can hold 20–50 small-cap names.
- **New family for the lab:** first single-name, event/information-driven candidate.
  No in-house base rate applies (not price-only mean reversion, not calendar, not
  carry, not trend).
- **Data is public and free at the source:** SEC EDGAR Form 4 filings, machine-readable
  XML since ~2003–2004, including filings by companies that later delisted.
- Multi-week/month holding amortizes the cost bar; long-only avoids borrow.

## Known risks stated before evidence (what would kill it)

1. The cluster definition is a suspected sweep (criterion 2): number of insiders,
   window length, role filters, dollar-size filters, holding period all plausibly vary
   across studies.
2. Single-name small-cap backtests need **delisted-company price histories** or the
   universe is survivor-biased — the exact flaw that killed cef-discount's data
   criterion. Alpaca serves live tickers; a dead-company price source at retail cost
   is the open question (criterion 6).
3. Signal may be arbed post-2012 publication and post-2002 SOX two-business-day
   filing acceleration (criterion 1/4): quant funds ingest EDGAR in real time.

## Locked criteria (all six must PASS)

1. **Post-2015 persistence.** At least one independent test / dataset covering 2015+
   showing an insider-*purchase*-based selection rule with positive performance after
   realistic costs. If recent tests show the effect dead, reversed, or confined to a
   latency race retail cannot win, FAIL. Mixed/unresolved defaults to FAIL.
2. **Single canonical pre-registrable rule, no sweep.** The literature must converge
   on one signal form (cluster definition, window, role filter, holding period). If
   published results hinge materially on these choices and studies disagree (the
   ToM/VRP failure mode), FAIL.
3. **Cost bar clears with margin.** Small-cap all-in retail round trip (spread +
   impact at our size) quantified; documented edge per round trip ≥ 3× cost at the
   strategy's natural turnover. If the edge concentrates in illiquid names our
   fills can't reach at quoted spreads, FAIL.
4. **Mechanism intact + payer identified + moat standing.** The payer must be
   identifiable (counterparties trading against legally-informed insiders) and the
   post-publication moat must be argued from evidence: if systematic funds have
   industrialized Form 4 ingestion such that the residual edge is latency- or
   capacity-inaccessible to retail, FAIL (the cef-discount #4 lesson: "the mechanism
   exists" is not enough — the *harvestable* remainder for us must exist).
5. **Tail haltable (grind, not gap).** A diversified long small-cap book's worst
   episodes must be boundable by a daily-bar `halt_on_drawdown`. Single-name overnight
   gaps (earnings, fraud halts) must be diversified to portfolio-level grind; if the
   documented edge requires concentration (<~15 names) such that one halt/gap
   dominates, FAIL.
6. **Data feasible and auditable.** BOTH legs at retail cost: (a) Form 4 history
   ≥10 years, bulk-downloadable and auditable (EDGAR expected to satisfy this —
   verify), and (b) **point-in-time single-name price history including delisted
   companies** for the small-cap universe (survivorship-free), free or cheaply
   licensed, in a form the lab can audit. Either leg missing → no honest pregate →
   FAIL. Decisive on its own.

## Downstream gates noted now (not part of this screen)

- Common-mode benchmark, locked before any OOS look: EDGE = cluster-buy book minus a
  **size/liquidity-matched random-entry baseline on the same universe and holding
  clock** (not SPY) — insider small-cap books must beat holding comparable small caps,
  or the "edge" is the size factor.
- IS/OOS split frozen at spec time; OOS must include a post-2012-publication stretch.

## Verdict rule

Score each criterion PASS/FAIL with sources. Any FAIL on 2, 4, 5, or 6 is decisive.
A FAIL on 1 or 3 may be argued only if the evidence is genuinely mixed, and the
default in a mixed case is FAIL (unresolved-leaning-fail).
