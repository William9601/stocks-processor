# Research screen — cef-discount — VERDICT: REJECTED (2026-07-10)

Criteria were locked in `prereg.md` **before** any evidence was read. Scorecard below.
Cost of screen: one session, no spec, no code. 12th candidate death, 5th at the
research screen (ToM, sector-momentum, VRP, and — for family reasons — PEAD before it).

## Scorecard: 3 PASS, 3 FAIL — two of the fails are structural and decisive

### #2 Single canonical rule — PASS

Unlike ToM (window definitions disagree) and VRP (sizing sweep), the literature
converges on the signal itself: **wider discount → higher expected return**, harvested
as a monthly sort on current discount, long the widest quintile, equal-weight
(Thompson 1978; Pontiff 1995). The strongest academic test — Patro, Piccotti & Wu
([SSRN 2468061](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2468061), 377 US
CEFs, CRSP prices + Bloomberg NAVs, Aug 1984–Dec 2011) — extends it parametrically
(per-fund rolling regressions on premium history) and reports L/S 17.3–18.2%/yr,
5-factor alpha 17.4%, Sharpe 1.86, long-leg-minus-market 9.8%/yr Sharpe 0.795,
turnover only ~2.9×/yr. Practitioner variants (z-score windows, discount percentile,
RSI-of-discount) are refinements of the same sign, not competing signals. The
freezable baseline rule exists.

### #3 Cost bar — PASS (conditional on #1)

Turnover ~2.9×/yr against a documented 9.8–17.3%/yr edge; even at pessimistic CEF
spreads (50–100 bps RT on smaller funds) cost drag is ~1.5–3%/yr — clears 3× with
margin *at the pre-2011 edge magnitude*. Inherits criterion #1's doubt about whether
that magnitude still exists post-compression.

### #5 Tail haltable — PASS

The blow-outs are violent but multi-day: universe average discount went 8.6% → 21.6%
between late Feb and Mar 18 2020 (second-widest ever; 2008 peak 27.4%) and settled
back to 8.6% by late April
([FA-mag](https://www.fa-mag.com/news/hunkering-down-with-closed-end-funds-55847.html),
[Harvard Law corp-gov](https://corpgov.law.harvard.edu/2021/01/03/shareholder-activism-at-closed-end-funds-in-the-wake-of-covid-19/)).
No single-session termination events (contrast XIV); embedded fund leverage amplifies
but does not gap-terminate. A daily-bar `halt_on_drawdown` can bound this. Grind, not
gap.

### #1 Post-2015 persistence — FAIL (mixed → locked default = FAIL)

The strongest test ends **December 2011**. No rigorous independent post-2015
net-of-cost test of a frozen discount rule was found; what exists is practitioner-grade
(e.g., a 2019 Seeking Alpha z-score study that outperforms an equal-weight CEF
benchmark — while demonstrating parameter sensitivity). Meanwhile the prereg's
compression clause binds: activist harvesting compressed average discounts from
~10–13% (2015–2018) to ~6–9% (2022–2025)
([Saba 5-engine analysis](https://navnoorbawa.substack.com/p/boaz-weinsteins-5-engine-strategy))
— documented, regime-changing shrinkage of the harvestable spread. Indirect evidence
the trade *worked* at scale (Saba's $3.66B, 329-position CEF book) is also evidence it
was crowded. Locked verdict rule: unresolved-leaning-fail.

### #4 Mechanism + moat — FAIL (decisive, by the locked wording)

The payer is intact (sentiment/tax-loss/indiscriminate retail selling — re-proven by
the 2022 rate-shock widening). But the prereg says: *"if activist arbitrage has
industrialized the trade, the moat is gone and this FAILS even if past returns look
good."* It was industrialized — Saba alone ran 329 CEF positions worth $3.66B and
compressed the universe's discounts for a decade. The 2026-06-11 Supreme Court ruling
limiting activist campaigns
([Skadden](https://www.skadden.com/insights/publications/2025/04/court-upholds-legality-of-poison-pills),
[Elsberg](https://www.elsberglaw.com/news/supreme-court-narrows-activist-toolkit-against-closed-end-funds),
[Free Markets Report](https://freemarketsreport.substack.com/p/the-supreme-court-just-handed-closed))
may re-widen discounts 100–300 bps over 12–24 months — but that (a) is adverse P&L for
anyone holding wide-discount CEFs through the transition, (b) removes the *catalyst*
(tenders/open-endings) that historically forced convergence, and (c) creates a regime
four weeks old with zero data to pre-register against. Betting on the new regime is
speculation, not a documented mechanism.

### #6 Data feasible + auditable — FAIL (decisive, and the sharpest kill)

An honest pregate needs ≥10 years of daily/weekly NAVs for the **full** universe
including dead funds. What exists at retail:

- Academic sources are CRSP + Bloomberg — not available to this lab.
- [CEFData.com](https://cefdata.com/data-page) / Nasdaq Data Link
  [CEFUR](https://data.nasdaq.com/databases/CEFUR) have the history (1990/2012→) but
  are paid institutional products.
- [CEF Connect](https://www.cefconnect.com/) is free but serves *current* fund pages —
  and critically, **live funds only**. Any scraped universe is survivor-only, which
  biases a reversion backtest upward by construction (terminated/liquidated funds
  vanish from the sample). That is a lookahead-class flaw the lab's own rules forbid.
- NAV tickers (X-prefix) exist as quote symbols on some feeds, but free historical
  coverage is unverified and unauditable, and Alpaca does not carry them.

Locked wording: "No auditable NAV history → no honest pregate → FAIL. This criterion
is decisive on its own."

## Why this kill is informative (new failure mode)

The first eleven deaths were "edge gone," "cost eats it," "un-registrable sweep,"
"un-haltable tail," or "timing is beta." cef-discount dies on two axes the funnel had
never hit: **(a) the lab cannot buy or build an audit-grade dataset for the anomaly at
retail cost** (first data-feasibility kill — the criterion added in the 2026-07-10
criteria audit bit on its first use), and **(b) the mechanism's recent history is
contaminated by an activist regime that a 4-week-old Supreme Court ruling just ended**
— there is no stable regime to pre-register against in either direction.

## Revisit trigger (logged, not scheduled)

Re-screen no earlier than ~2027-H2 if BOTH: (1) post-SCOTUS discount behavior has ≥12
months of data (did discounts re-widen and does reversion still occur without the
activist catalyst?), and (2) an auditable NAV history source at retail cost exists
(e.g., a confirmed-cheap CEFData tier including dead funds). Criteria #2/#3/#5 carry
over as PASS; re-score #1/#4/#6 only.
