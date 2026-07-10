# Research screen — insider-cluster — VERDICT: REJECTED (2026-07-10)

Criteria were locked in `prereg.md` **before** any evidence was read. Cost of screen:
~1 session, no spec, no code. 13th candidate death, 6th at the research screen. All
three risks stated in the prereg before evidence materialized; two are decisive.

## Scorecard: 2 PASS, 4 FAIL — #2 and #4 are structural and decisive

### #2 Single canonical rule — FAIL (decisive)

The modern literature's own headline conclusion is that there is no single rule. The
most recent broad test — Heckmann, Jacobs & Schwarz 2025
([SSRN 4537187](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4537187), 3.7M
transactions, 34 countries) — finds "**no single indicator dominated**; the signal came
from synthesizing role, trade size, clustering, R&D context, and historical
profitability together," and states outright that single-characteristic filters
(including cluster-alone) "leave substantial alpha on the table." Blonien, Crane &
Crotty 2023 ([SSRN 4633070](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4633070))
locate the signal at the **insider level** (tracking each insider's historical
accuracy), not the transaction level. The canonical-adjacent rule (Cohen-Malloy-Pomorski
2012 opportunistic-vs-routine,
[SSRN 1692517](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1692517), 82 bps/mo
VW) is estimated on 1986–2007 data. A pre-registrable "N insiders buying within W days"
cluster rule is exactly the single-characteristic filter the recent literature says is
dominated — freezing one is a sweep pretending otherwise (the ToM/VRP failure mode,
confirmed rather than avoided).

### #4 Mechanism intact but moat gone — FAIL (decisive)

The payer exists (counterparties of legally-informed insiders) and the informed subset
is persistent (Blonien et al.: ~30% of insiders, ~10% of purchases informed, stable
over time). But the harvestable-after-filing remainder is the part retail needs, and
the evidence says it has been latency-arbed away:

- Blonien et al.: information is "impounded into prices **more quickly in recent
  years**, consistent with faster discovery by the market."
- Ozlen & Batumoglu 2026 ("The Death of Insider Trading Alpha,"
  [SSRN 5966834](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5966834)): **70–80%
  of the apparent return lives between the transaction date and the public filing** —
  before any Form 4 follower can act. (SSRN page blocked fetch; figure per the paper's
  abstract as cited in [Johnsen's write-up](https://tommijohnsen.substack.com/p/most-of-the-insider-trading-alpha),
  whose own 5-day n=4 pilot is anecdote and weighted as such.)
- Jiang, Martin & Yin 2025: the SOX 2-day filing acceleration *increased insiders'*
  profits (coordination among insiders) — the speedup helped the informed side, not
  followers.

Prereg wording binds: the residual edge is latency-inaccessible at a daily-cadence
retail pipeline. "The mechanism exists" is not enough (the cef-discount #4 lesson).

### #1 Post-2015 persistence — FAIL (mixed → locked default)

The signal exists academically post-2015 — but not in the form the criterion requires.
Heckmann et al.'s ≥1%/mo alphas are **equal-weighted, strongest in small stocks, at
short holding periods, gross** — the classic cost-trap configuration (CMP's own EW
number was 180 bps/mo vs 82 VW). No independent 2015+ test of a *frozen
purchase/cluster rule net of realistic costs* was found, and the newest evidence
(above) says most of the measured return precedes public availability.
Unresolved-leaning-fail.

### #3 Cost bar — FAIL (mixed → locked default)

Where the edge lives (small caps, EW, short horizons with 6–12-month decay) is where
costs are worst (30–100+ bps spreads, ~monthly turnover). If ~70–80% of the gross
return precedes the filing, the harvestable residual of even 1%/mo is ~20–30 bps/mo —
inside the cost band, before slippage at our size. Cannot demonstrate the ≥3× margin.

### #5 Tail haltable — PASS

Long-only, diversified 20–50-name small-cap book: single-name gaps (earnings, halts)
diversify to portfolio-level grind; worst episodes are small-cap beta drawdowns a
daily `halt_on_drawdown` can bound.

### #6 Data feasible — PASS (and a reusable finding)

Both legs exist at retail cost: EDGAR Form 4 is free, machine-readable XML since
~2003–2004, includes filings of later-delisted companies; survivorship-free US price
history **including delisted stocks** is retail-priced at
[Norgate Data](https://norgatedata.com/) (~$630/yr Platinum; delisted + historical
index constituents; Python plugin) with [Sharadar](https://www.sharadar.com/) as an
alternative. **This unblocks single-name candidates generally** — the cef-discount
data-kill does not generalize to equities. Logged as infrastructure knowledge even
though this candidate dies.

## Why this kill is informative

The right-to-edge story inverted under examination: the informed party is the
*insider*; a Form 4 follower is last in a latency queue behind systematic funds with
real-time EDGAR ingestion, harvesting whatever survives a race it structurally loses.
And the modern literature abandoned the simple rule — the surviving signal is a fitted
multi-factor composite, which is un-pre-registrable by this lab's rules. New screen
heuristic: **for follower/mimicry strategies, ask where we sit in the disclosure
latency queue before anything else.**

## Revisit trigger (logged, not scheduled)

Only if an independent test appears of a *frozen, simple* purchase rule (not a fitted
composite) on 2015+ data, net of costs, measured **from the public filing timestamp**
— i.e., someone demonstrates post-filing harvestable alpha at daily cadence. Absent
that, the family stays dead.
