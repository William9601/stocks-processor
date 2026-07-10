# Strategy candidate shortlist — research pass 2026-07-05

Question: mine our own historical data for patterns, or research documented edges and
validate them here? Decision: **documented edges first** — a prior mechanism ("why does
this exist and who pays for it") is the best available predictor of out-of-sample
survival, and the lab's own history bears it out: both novel formulations tested so far
(intraday-momentum's SPY translation, rsi-5050) died at validation, while the one
strategy in paper (overnight-long) came from a documented anomaly. Pure data mining is
deferred until walk-forward machinery is cheap enough to make mined patterns falsifiable
at scale.

## What the lab has already answered (do not re-test)

| Effect | Strategy | Verdict |
|---|---|---|
| Overnight drift, long leg | overnight-long | **PAPER** (QQQ gated, WF-carried) |
| Overnight drift, both legs | overnight-drift | REJECTED — intraday-short leg has no gross edge; auction costs ate the rest |
| Market intraday momentum (Gao et al. 2018) | intraday-momentum | REJECTED — effect absent in SPY 2018–2024, negative even gross |
| RSI(21) midline breakout (user's method) | rsi-5050 | REJECTED at pregate — +0.30 bps gross vs 3.5 bps cost bar |
| Short-term index mean reversion (RSI(2)) | spx-swing | REJECTED at pregate 2026-07-05 — OOS 2018–2024 edge vs SPY drift −14.6 bps/trade (IS 2005–2017 had it: +30 bps) |
| Volatility risk premium (short VIX carry) | (research screen #8) | REJECTED at research stage 2026-07-07 — edge real + cheap, but not pre-registrable without a sizing sweep, and the short-vol tail is un-haltable by our infra |

External confirmation of the overnight-drift rejection: NightShares launched ETFs on
exactly that decomposition in 2022 and closed them within a year — transaction costs
from twice-daily turnover, the same failure our backtest predicted
([Elm Wealth](https://elmwealth.com/night-shift/)).

## Candidates, ranked

### 1. spx-swing — short-term index mean reversion — **RESUMED AND REJECTED 2026-07-05**

Outcome (same day this shortlist was written): spec approved and frozen, splice built
(see the Alpaca missing-dividend findings in
`experiments/spx-swing/2026-07-05-pregate/splice_report.json`), pregate run — the IS
era (2005–2017) showed the documented edge (+44.5 bps net/trade, t=3.03), the OOS era
(2018–2024) showed it gone (+5.5 bps net, t=0.21; **−14.6 bps vs unconditional SPY
drift**). The external decay evidence below was correct and then some. Rejected at the
pre-registered gate, no tuning, no engine code. The original case for ranking it #1 —
cheapest test — held: total cost was one session. **ORB (below) is now the front of
the queue.** Original entry kept for the record:

### ~~1.~~ spx-swing — short-term index mean reversion (RESUME; spec already drafted)

- **Effect:** negative 1–5-day autocorrelation in S&P 500 since ~late 1990s; buy
  2-day-oversold pullbacks above the 200-SMA, sell strength. Popularized as RSI(2)
  (Connors). Mechanism: liquidity provision against mechanical sellers (vol-targeting,
  stops, margin) — flows that persist because they don't maximize expected return.
- **External evidence (2026 view):** strong pre-2010; decayed but still positive on
  index ETFs after — one long-run backtest shows ~19.8%/yr vs 17.7% benchmark and
  Sharpe 1.03 vs 0.89 since 2010, but **underperformance 2021–2025** (7.1%/yr vs 13.4%)
  ([QuantifiedStrategies](https://www.quantifiedstrategies.com/rsi-2-strategy/),
  [Quantitativo](https://www.quantitativo.com/p/trading-the-mean-reversion-curve)).
  Win rates drop below 60% in crash regimes.
- **Why ranked #1 anyway:** turnover is ~15–25 round trips/yr, so total cost drag is
  ~0.12–0.20%/yr — a decayed thin edge can survive costs here, unlike every intraday
  candidate. And the marginal cost of testing is near zero: `strategies/spx-swing/SPEC.md`
  is a complete draft with pre-registered parameters, a pre-scoring reject gate, and
  free-tier-compatible daily-bar design. Its adversarial note already assumes exactly
  the decay the research found.
- **Honest tension:** the user parked this spec wanting *more trades per day*. This is
  the opposite — ~20% time in market, 10–20 signals/yr. It is a good bet, not an
  exciting one.
- **Next step:** answer the 5 pending sign-offs in the spec (pivotal: pre-2016 EOD data
  source — the Alpaca-only fallback likely fails the ≥60-OOS-trade bar by construction),
  then run the pre-scoring diagnostic before any engine code.

### 2. Opening range breakout (ORB), 5-min, QQQ — **REJECTED at the OOS engine gate 2026-07-05**

Outcome: spec approved and frozen (`strategies/orb/SPEC.md`, 6 baselines signed off);
pregate **passed** — the lab's first: IS mean gross +4.67 bps/trade (t=2.22) vs the
2.0 bps bar, all five years positive (`experiments/orb/2026-07-05-pregate/`). The
core intrabar-stop extension was built, the engine reproduced the pregate to rounding
(1,251/1,251 trades), and the one pre-registered OOS look (2023–2024,
post-publication) **failed 5 of 9 frozen bars**: net Sharpe 0.153 vs ≥1.0, QQQ B&H at
2.002 over the same window, long side net-negative, −2.03% at 1.5× costs, −81% decay
vs IS. OOS gross (+1.90 bps/trade) fell below the cost bar on its own — the
published-then-gone pattern, third confirmation in this lab. Quant-reviewer: no
blockers, rejection trustworthy. Post-mortem in the SPEC; WF never read. What
survives: the payoff-shape hypothesis was right (the level wasn't), correlation vs
the overnight-long book 0.008, and the intrabar-stop core machinery is now validated
infrastructure. Original entry kept for the record:

### ~~2.~~ Opening range breakout (ORB), 5-min, QQQ — the day-trading candidate

- **Effect:** direction of the first 5 minutes predicts intraday follow-through; enter
  at bar 2 in that direction, stop at the opening bar's opposite extreme, ~10R target
  or flat at close. Zarattini & Aziz (2023) backtest QQQ 2016–2023
  ([paper via CXO](https://www.cxoadvisory.com/technical-trading/day-trading-with-an-opening-range-breakout-strategy/),
  [QuantifiedStrategies](https://www.quantifiedstrategies.com/opening-range-breakout/),
  [QuantConnect replication](https://www.quantconnect.com/research/18444/opening-range-breakout-for-stocks-in-play/)).
- **Caveats:** the 1,484% headline is **leverage-flattered** (assumes 3x-style sizing);
  the edge lives in a low hit-rate / high-R payoff, so drawdown sequences are brutal;
  independent replications are mixed on cost sensitivity; and the lab's base-rate
  warning applies — the last published intraday effect we tested (MIM) was absent in
  our own data.
- **Fit:** this IS the "more trades per day" direction (one trade/day, both sides), and
  the new Algo Trader Plus real-time SIP entitlement makes it feasible live. Build cost
  is the catch: core has no intraday stop/target management (only next-open/next-close
  fills) — a real core extension, spec'd and reviewed, before backtest #1.
- **Next step if chosen:** strategy-designer spec with a pregate on gross follow-through
  (same pattern that killed rsi-5050 for 3 hours of work instead of 3 weeks).

### 3. Overnight-long extensions — vol-regime overlay (LATER, not now)

- **Effect:** scaling exposure inversely with volatility raises Sharpe
  (Moreira & Muir 2017, [Volatility-Managed Portfolios](https://amoreira2.github.io/alan-moreira.github.io/VolPortfolios_published.pdf);
  [Man Group on vol targeting](https://www.man.com/insights/the-impact-of-volatility-targeting)).
  Could gate/scale the QQQ overnight book by VIX or realized vol instead of (or on top
  of) the 200-SMA.
- **Why parked:** every out-of-sample look spends data we can't get back, and the paper
  book's job right now (week 1 from 2026-07-06) is validating fill mechanics. Revisit
  after ~4 weeks of paper fills and the quote-based cost study.

### 4. Post-earnings announcement drift — REJECTED at research stage

Documented since 1968, but profitability for non-latency traders decayed sharply
post-2016 as after-hours price discovery improved; residual drift is truncated within
the announcement window ([Quantpedia](https://quantpedia.com/strategies/post-earnings-announcement-effect),
[review](https://www.sciencedirect.com/science/article/pii/S2214635020303750)).
Would also require a single-name universe and an earnings-calendar data source. Not
worth a spec.

### 5. Turn-of-the-month (ToM), US index ETFs — REJECTED at research stage 2026-07-06

Chosen 2026-07-06 as the next candidate (month-end pension/401k contribution and
rebalancing flows — a counterparty that pays deliberately, ~12 events/yr, daily bars,
near-zero cost drag). Killed at the research screen, before any spec, on all three
pre-set criteria:

- **Post-2010 effect size is not there.** The most recent broad test (36 ETFs,
  through Feb 2025) finds the classical Lakonishok-Smidt window returns only "a few
  basis points" above other days in US equity ETFs, **statistically insignificant**,
  and concludes the effect "largely disappeared over the past decade." QQQ's ToM
  effect, very strong in the early 2000s, "gradually diminished to zero"; some US
  sector ETFs now show a *reversed* (negative) ToM window
  ([QuantSeeker, Feb 2025](https://www.quantseeker.com/p/turn-of-the-month-strategies-do-they)).
- **Decay and migration are old news, not new noise.** Documented as early as 2011:
  after ETF introduction the effect migrated toward the first day of the month
  ([FPA journal](https://www.financialplanningassociation.org/article/journal/APR11-turn-month-anomaly-age-etfs-reexamination-return-enhancement-strategies));
  a 1991–2008 S&P futures study found "from several days that bring above-average
  returns, only one day remains"
  ([summary](https://www.intalcon.com/magazine/tom-effect-excess-returns-at-the-turn-of-the-month)).
  QuantSeeker's rolling-difference charts show a consistent downtrend over the last
  decade; residual strength is in international/EM markets, not US indexes.
- **Published window definitions do not agree.** Fosback (1975) −1/+4, Lakonishok &
  Smidt (1988) and [McConnell & Xu (2008)](https://www.chesler.us/resources/academia/turn_of_the_month_stock_returns.pdf)
  −1/+3, practitioner variants −4/+3 and −3/+3
  ([Quantpedia](https://quantpedia.com/strategies/turn-of-the-month-in-equity-indexes)),
  migration studies day +1 only. There is no single window to pre-register without an
  implicit sweep — the exact failure mode the ORB duration-sweep rule exists to block.

The classic evidence (12 bps/day on the DJIA 1897–1986; persistence through 2005 in
McConnell & Xu) is real but pre-decay. And the benchmark gate settles it arithmetically:
SPY's unconditional drift since 2010 is ~5 bps/day, so an insignificant few-bps ToM
premium is beta plus a calendar story by construction. Fourth instance of the
published-then-gone pattern (after intraday-momentum, spx-swing, ORB) — and consistent
with the mechanism still existing while being front-run away: the flows didn't stop,
the price impact moved and shrank. Cost of the screen: under an hour, no spec, no code.

### 6. Pre-FOMC announcement drift, SPY — REJECTED at the OOS engine gate 2026-07-06

- **Effect:** large positive US equity returns in the ~24h before scheduled FOMC
  announcements. [Lucca & Moench (2015)](https://www.newyorkfed.org/research/staff_reports/sr512.html):
  +49 bps per event on average 1994–2011, ~80% of the annual equity premium earned on
  ~8 days/yr. Mechanism candidates: compensation for bearing announcement risk while
  uncertainty resolves into the release (Hu-Pan-Wang-Zhu 2019) — a deliberate-payer
  story, like ToM's, but with a fixed, scheduled anchor event.
- **The adversarial fact, on the record before any spec:**
  [Kurov, Wolfe & Gilbert (Finance Research Letters 2021)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3134546)
  extend the sample to Dec 2019 and find the drift "essentially disappeared after
  2015" — mean pre-FOMC return Jan 2016–Dec 2019 ≈ **9.2 bps, insignificant** —
  attributing it to reduced uncertainty in the ZLB era. Ben Dor & Rosa (2019)
  dispute, finding no change. [QuantSeeker (2025)](https://www.quantseeker.com/p/trading-the-fed-the-pre-fomc-drift)
  (SPY EOD close-to-close windows, 1993–2024) finds the FOMC-vs-other-days
  difference strongly significant over the full sample, confirms the flat
  2016–2019 stretch, and shows renewed performance 2020–2024 (after-cost Sharpe
  ~0.5–0.6 trading ~5% of days). The consistent read: **uncertainty-state-dependent,
  not monotonically decayed** — it faded in the ZLB calm and returned with policy
  uncertainty. That is a falsifiable claim a pregate can test, not mush.
- **Window definitions:** onset differs across studies (LM: 2pm day prior → 2:15pm
  announcement; [Boguth-Grégoire-Martineau](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3134546):
  onset at prior-day open, press-conference meetings only; practitioner EOD variants:
  prior close → announcement-day close). Unlike ToM, the anchor is a fixed scheduled
  event, and the lab's daily-bar infrastructure forces the implementable window
  anyway: MOC buy the day before → MOC sell announcement day via existing
  `FillTiming.NEXT_CLOSE`, **no core extension**. Freeze the exact window from the
  literature at spec time; no sweeps.
- **Honest problems for the spec:** ~8 events/yr — thinner than ToM's 12; power
  requires long history. Correction (2026-07-06, caught at spec drafting): the
  audited splice `data/SPY_daily_adj_spliced.parquet` as built covers
  **2002-09-03 → 2026-07-02** (`experiments/spx-swing/2026-07-05-pregate/splice_report.json`),
  not 1994 as this entry first claimed — extending it to 1993-06 with the same
  audit is a blocking data task in the spec, with a pre-declared fallback IS of
  2003–2015 (~104 events) if the extension fails audit. The pre-registered OOS era
  must contain the 2016–2019 dead zone (no cherry-picking the revival). Benchmark gate vs same-length
  unconditional drift mandatory. Overlap with the overnight-long paper book is
  material (long SPY over FOMC nights). Needs a historical FOMC meeting calendar
  (public, Fed website) as a new data input — signal is calendar-driven, no lookahead
  risk if scheduled dates are used as announced.
- **Progress 2026-07-06:** spec approved and frozen (`strategies/fomc-drift/SPEC.md`),
  both blocking data tasks done (splice extended to 1993-06; committed audited
  `fomc_calendar.csv`, 263 scheduled meetings), and the **pregate PASSED** — the lab's
  second pass after ORB. IS 1994–2015 (n=176, OOS/WF unread): `EDGE(IS) = 30.35 bps`,
  t ≈ 3.4, hit 59.7%, clearing both the 2.0 bps cost bar and the 20 bps reproduction
  bar (~2/3 of the LM ~45 bps headline). Honest caveat carried forward: the IS edge is
  crisis-weighted (2008 +145, 2009 +116 bps; several calm years negative) — exactly the
  pre-registered uncertainty-state-dependence, and the OOS front-loads the 2016–2019
  dead zone. Full write-up `experiments/fomc-drift/2026-07-06-pregate/notes.md`.
- **Verdict 2026-07-06 — REJECTED at the OOS engine gate.** Implemented against core,
  engine IS cross-check EXACT (176/176 events, max diff 0.00000 bps), then the one
  pre-registered OOS look. OOS 2016–2024 (n=71): `EDGE(OOS) = 1.87 bps` gross (net
  −0.13), zero-filled Sharpe 0.109 vs the ≥0.7 bar — four frozen bars fail (#1/#2/#4/#8).
  The uncertainty-state-dependence was *confirmed* (dead zone 2016–2019 EDGE −15.9 /
  revival 2020–2024 EDGE +16.4) but the two cancel; the unconditional book earns the
  ~zero blend and the LOCKED no-rescue clause forbids gating to harvest only the revival.
  Sixth candidate death; failure is at the gross/edge level, not execution (quant-reviewer:
  REJECT trustworthy). Verdict + scorecard in `strategies/fomc-drift/SPEC.md` and
  `experiments/fomc-drift/2026-07-06-2011-oos/notes.md`. Infra that survives: daily-bar
  MOC now works on the shared core (engine `expire_pending(NEXT_CLOSE)` reorder +
  `scripts/build_spy_daily_moc.py` session-close re-stamp), and the ORB reviewer
  follow-ups (`risk_halted`, `max_drawdown_mtm`, per-run `data_sha256`) are now paid.

### 7. Sector-ETF momentum rotation — REJECTED at research stage 2026-07-06

Screened same day as ToM and FOMC drift; killed on the recent-decade evidence.
Traditional sector momentum diminished as ETFs raised sector efficiency and
cross-sector correlation — [Quantpedia](https://quantpedia.com/strategies/sector-momentum-rotational-system)'s
3-long/3-short 12-month variant now shows negative returns and high drawdowns, and
[CXO Advisory](https://www.cxoadvisory.com/momentum-investing/simple-sector-etf-momentum-strategy-performance/)
finds simple sector-ETF momentum "does not add value to an equally weighted
benchmark," having become a drag in the later sample. Surviving published variants
are long-only holding 4+ of ~10 sectors — closet beta that fails the mandatory
unconditional-drift benchmark gate by construction. The formulation space (3/6/12-month
lookback, skip-month, top-K, rebalance frequency — every publication differs) is a
pre-registration minefield, and the strategy would have maximum overlap with the
overnight-long paper book (always long equities). Not worth a spec.

### 8. Volatility risk premium (short VIX term-structure carry) — REJECTED at research stage 2026-07-07

Chosen 2026-07-07 as the next candidate — the one anomaly family the funnel's derived
constraints all seemed to allow: a *structural* deliberate payer (equity hedgers
overpay for index insurance), multi-day holding that amortizes the cost bar, and an
instrument set (VIX futures / SVXY-VIXY) we hadn't touched. Killed at the research
screen, before any spec, on the four criteria pre-registered **before** the evidence was
read:

1. **Post-2018 persistence** — the term-structure-conditional form must show positive
   net-of-cost performance in independent tests that include 2018 and after.
2. **Single pre-registrable rule, no sweep** — one canonical signal must recur across
   the literature, not results that hinge on which contracts / threshold / sizing.
3. **Cost bar clears with margin** — all-in cost (spread + expense ratio + roll)
   quantifiable, with positive net Sharpe in an independent recent test.
4. **Mechanism intact + tail survivable** — the hedging-overpayment payer still exists
   *and* the drawdown is survivable under our `halt_on_drawdown` infra.

Scorecard: **2 pass, 2 fail — and the two fails are decisive.**

- **#4 mechanism — STRONG PASS.** Every source agrees the payer is structural and
  intact: VIX futures are in contango ~80% of the time, generating ~3–7%/month roll
  yield from "equity hedging imbalances," not a price pattern that gets arbed away
  ([Simplify](https://www.simplify.us/blog/volatility-premium-harvesting-reimagined),
  [Quantpedia VRP](https://quantpedia.com/strategies/volatility-risk-premium-effect)).
  This is the strongest part of the thesis and the reason VRP outranked everything else
  on the shortlist.
- **#3 cost bar — PASS, and it does *not* kill the idea (unlike overnight-long).** SVXY
  bid/ask ~2 bps, expense ratio ~0.95%/yr (~8 bps/month) — trivial against 3–7%/month
  roll yield at monthly-roll turnover; an independent test (2008–May 2025, 5 bps/trade)
  reports Sharpe ~1 at 16.3%/yr with ~15% equity correlation
  ([InvestSnips / ProShares figures](https://investsnips.com/vix-short-term-futures-etf/)).
  So for once cost is not the assassin.
- **#2 single rule / no sweep — FAIL (decisive).** There is no canonical rule to
  pre-register. Contract choice (front-month vs constant-maturity vs Simon-Campasano
  "nearest with ≥10 days"), threshold (roll > 0.10 pts vs contango ratio vs
  SPY-realized-minus-implied), holding (5-day vs monthly roll), hedged (E-mini overlay)
  vs unhedged, **and exposure sizing (50% / 25% / 12.5%, where Simplify names "the sweet
  spot ~25%" — a chosen point on a three-way sweep)** are all live design axes, and the
  results depend on them. This is exactly the failure that killed turn-of-month (#5):
  "no single window to pre-register without an implicit sweep." The Simon-Campasano
  term-structure trade specifically shows OOS "slightly negative … alpha deteriorating"
  ([Quantpedia term structure](https://quantpedia.com/strategies/exploiting-term-structure-of-vix-futures)),
  so the one fully-specified published rule already fails post-sample — the survivors
  are the swept ones.
- **#4b tail survivable — FAIL (decisive, and specific to our infra).** The premium is
  *by construction* payment for catastrophic tail risk: the Financial Analysts Journal's
  post-mortem is literally titled "Volmageddon and the Failure of Short Volatility
  Products"
  ([FAJ 2021](https://www.tandfonline.com/doi/abs/10.1080/0015198X.2021.1913040)). XIV
  lost >96% and was terminated in hours on 2018-02-05 — an **overnight** VIX gap
  (17→37) the position could not exit through. Our `halt_on_drawdown` fires on realized
  MTM drawdown on *daily bars*; it structurally cannot bound an overnight
  termination-event gap. The tail here is not merely large, it is **un-haltable by the
  risk infrastructure we have**. Post-2018 survival exists only in reduced-exposure
  (−25%) + options-tail-hedged form — two overlays that are themselves the sweep of #2,
  and COVID-2020 was a second near-death with the premium only "normalizing in 2023"
  ([Quantpedia VRP](https://quantpedia.com/strategies/volatility-risk-premium-effect)).

**Why this rejection is different from the prior nine — and therefore useful.** The
first nine died of "edge gone" (intraday-momentum, ORB, ToM, FOMC, spx-swing) or "cost
eats it" (overnight-long, overnight-drift). VRP dies of neither: the edge is real,
structural, and *cheap to trade*. It dies because (a) it is inseparable from a
sizing/overlay sweep we cannot honestly pre-register, and (b) its defining tail is one
our risk system cannot bound. That is a cleaner kill — and it maps the boundary of what
this lab can hold: not "is there an edge" but "can we pre-register it and can our risk
infra survive its worst day."

**One adjacent idea, parked (not spec'd now).** The *long*-vol mirror — holding a small
VIXY sleeve as a **tail-hedge overlay** on an equity book — flips #4b from an
un-haltable short tail into a bounded long-premium bleed, and would pair naturally with
the shelved overnight-long QQQ book (long equities overnight, small long-vol hedge). But
it is an overlay, not a standalone alpha (it *costs* the 60–80%/yr contango decay), it is
not what we screened, and the overnight-long book is itself shelved on cost. Funnel
discipline is one candidate at a time; log it and move on. Cost of this screen: under two
hours, no spec, no code.

### 9. Multi-asset time-series momentum (trend-following) — **PASSED the research screen 2026-07-08**

Chosen 2026-07-08 as the next candidate after the VRP kill emptied the funnel — the
best structural fit the boundary mapping allows, and the first candidate whose defining
property *inverts* the tail flaw that killed VRP. Canonical rule: sign of the trailing
**12-month excess return** sets a long/short position, inverse-vol sized, monthly
rebalanced, across a diversified basket (equity indices, sovereign bonds, commodities,
FX) — Moskowitz-Ooi-Pedersen (2012). Four criteria pre-registered and LOCKED before
scoring (`experiments/tsmom/2026-07-08-research-screen/prereg.md`):

- **#1 Post-2011 persistence — PASS (live caveat).** The 2010s were weak (low-vol,
  whipsaw, rising cross-asset correlation), but Hurst et al.'s century study is positive
  every decade including the 2010s and the 28-futures 2005–2024 OOS test is profitable,
  meeting the locked threshold. Caveat is material and current: SG Trend Index **−20.4%
  May-2024→May-2025, its 2nd-largest drawdown since 2000**. Logged as the most likely
  downstream killer (lean-regime OOS Sharpe below bar — the ORB/FOMC death mode).
- **#2 Single canonical rule, no sweep — PASS.** The 12-month sign is robust across
  lookbacks/sub-samples and positive for all 58 MOP contracts — genuinely
  pre-registrable, the exact property ToM (#5) and VRP (#8) lacked.
- **#3 Benchmark gate restatable for a diversifier — PASS.** "Beat SPY drift" kills
  equity-only trend as closet beta by construction; the legitimate reframe (adds
  risk-adjusted return AND negative-crisis-correlation to a SPY book) is what the
  strategy *is*, not a post-hoc loosening. Governance condition: lock the restated gate
  before any OOS look (the overnight-long rescue lesson).
- **#4 Worst-day loss haltable (grind, not gap) — PASS (decisive, inverts VRP).** SG
  Trend max DD ~20.6%, drawdowns 15–25% over 12–24-month recoveries — slow, vol-scaled,
  no single-day wipeout because the payoff is *long* convexity. A daily-bar
  `halt_on_drawdown` can bound it; contrast XIV −96% overnight in hours.

**All four PASS → authorized for multi-asset data infra + a strategy-designer spec.**
First candidate to clear the research screen (ToM, sector-momentum, VRP all failed it;
ORB and FOMC passed only the later pregate, then died at the OOS engine gate — so TSMOM's
real OOS looks are still ahead, not behind). Two logged downstream risks the spec must
confront: (1) lean-regime OOS Sharpe below bar — the pre-registered OOS window must
include a lean stretch, no cherry-picking 2022; (2) "diversification beta, not alpha" —
the benchmark must isolate trend's contribution vs a static multi-asset buy-and-hold, not
just vs SPY. New data infra: a diversified liquid-ETF proxy basket (SPY/EFA/EEM, IEF/TLT,
DBC/GLD, UUP), daily, self-adjusted with the audited-splice discipline (the Alpaca
`adjustment=all` dividend bug applies).

**Progress 2026-07-08:** (1) basket data BUILT + audited (`scripts/build_tsmom_basket.py`,
common start 2007-03, all audits pass, EEM/EFA split×dividend landmine solved
empirically; `experiments/tsmom/2026-07-08-basket-build/`). (2) **SPEC approved +
criteria FROZEN** (`strategies/tsmom/SPEC.md`): long/short 12-month TSMOM, inverse-vol
(60d) sizing to a 10% portfolio vol target, monthly MOC rebalance, 3× gross cap, 20%
kill switch. The screen's criterion-3 benchmark restatement is locked as the binding
gate — the benchmark is the **static always-long basket** (same instruments/sizing), and
`EDGE = TSMOM Sharpe − STATIC Sharpe` must be > 0 or it is diversification beta not
trend alpha. IS 2008-03→2016-12 / OOS 2017-01→2024-12 (lean-inclusive) / WF 2025→ sealed.
Costs 4.0 bps RT + 50 bps/yr borrow (1.5× companion locked). **Next: `scripts/pregate_tsmom.py`,
IS-only** — REJECT at spec validation if `EDGE(IS) ≤ 0`, IS Sharpe < 0.3, or the timing
removes crisis convexity. No engine code / no OOS look until the pregate passes.

**Verdict 2026-07-08 — REJECTED at the pregate / spec-validation (10th candidate death).**
The IS-only pregate (`experiments/tsmom/2026-07-08-pregate/`, IS 2008-04→2016-12, OOS/WF
hard-sliced out) simulated the long/short book and the STATIC always-long same-basket
benchmark through identical machinery. **Two of three frozen gates fail:** EDGE(IS) =
TSMOM 0.258 − STATIC 0.650 = **−0.392 Sharpe** (timing loses to holding the basket), and
TSMOM IS Sharpe 0.258 < 0.30. The convexity gate PASSED (worst-SPY-quartile +0.17% vs
STATIC −0.94% — the timing did add crisis protection), but that alone didn't pay for the
whipsaw. The kill is in **gross return, not costs**: TSMOM gross Sharpe 0.305 is already
< half STATIC's; borrow+turnover is ~0.5pp of the 4.2pp/yr return gap (TSMOM 2.86%/yr vs
STATIC 7.03%/yr). Per-year is textbook lost-decade trend: crisis alpha (2008 +5.9%, 2013
+21%) overwhelmed by whipsaw (2009 −8.5%, 2014 −6.5%, 2016 −12%), max DD −19%. **This is
exactly the "diversification beta not trend alpha" failure the benchmark restatement
(screen criterion #3) was built to catch** — the book is a genuine diversifier
(corr-to-SPY −0.04) but the momentum *timing* subtracts risk-adjusted return over just
holding the risk-balanced basket. No-peek/no-rescue held: OOS (2017-24, incl. the 2022
revival that might score better) stays sealed; re-slicing the frozen IS window is
forbidden. The VRP-grade useful kill: real mechanism, haltable tail, convexity present,
cost not the assassin — dies on the honest common-mode benchmark, at spec-validation,
one session, no engine code / no OOS look spent. **Infra that survives:** the audited
multi-asset basket builder (`scripts/build_tsmom_basket.py`, 8 self-adjusted ETFs, the
lab's first multi-asset universe) + committed `strategies/tsmom/rf_13w.csv`.

### 10. Closed-end fund discount reversion (cef-discount) — REJECTED at research stage 2026-07-10

Chosen 2026-07-10 after the criteria audit added a "right to the edge" screen question —
CEFs answer it by construction (no creation/redemption arb, vehicles too small for
institutional scale). Criteria pre-registered before evidence
(`experiments/cef-discount/2026-07-10-research-screen/prereg.md`); scorecard **3 PASS /
3 FAIL, two fails structural**:

- **PASS #2 canonical rule** — monthly sort on current discount, long widest quintile
  (Thompson 1978 / Pontiff 1995); best academic test Patro-Piccotti-Wu (SSRN 2468061):
  377 CEFs 1984–2011, L/S 17.3%/yr, 5-factor alpha 17.4%, turnover ~2.9×/yr. Unlike
  ToM/VRP, variants agree on the signal.
- **PASS #3 cost bar** (at documented magnitude) and **PASS #5 haltable tail** (2020
  blow-out 8.6%→21.6% was a multi-week grind that recovered by April; no termination
  gaps).
- **FAIL #1 persistence** — strongest test ends Dec 2011; no rigorous post-2015 frozen
  rule test found; activist harvesting compressed discounts ~10–13% → ~6–9%
  (regime-changing per the locked clause); unresolved-leaning-fail.
- **FAIL #4 mechanism/moat (decisive)** — the trade was industrialized (Saba: 329 CEF
  positions, $3.66B) and the 2026-06-11 Supreme Court ruling limiting CEF activism just
  ended that regime — removing the convergence *catalyst* and leaving a 4-week-old
  regime with no data to pre-register against, in either direction.
- **FAIL #6 data (decisive)** — no audit-grade NAV history at retail cost: academic
  sources are CRSP+Bloomberg, CEFData/Nasdaq-CEFUR are paid, and free CEF Connect
  covers live funds only → any buildable universe is survivor-biased by construction,
  which inflates a reversion backtest. First data-feasibility kill in the funnel; the
  criterion added by the 2026-07-10 criteria audit bit on first use.

Revisit trigger logged in the screen notes: ≥12 months of post-SCOTUS discount data
AND a confirmed auditable NAV source (including dead funds). Cost of screen: one
session, no spec, no code.

### 11. Insider cluster buying (insider-cluster) — REJECTED at research stage 2026-07-10

Next-on-deck after cef-discount; first single-name, event/information candidate.
Criteria pre-registered before evidence
(`experiments/insider-cluster/2026-07-10-research-screen/prereg.md`) — all three
prereg-stated risks materialized. Scorecard **2 PASS / 4 FAIL, #2 and #4 decisive**:

- **FAIL #2 canonical rule (decisive)** — the modern literature itself abandoned the
  simple rule: Heckmann-Jacobs-Schwarz 2025 (SSRN 4537187; 3.7M transactions) find "no
  single indicator dominated" — the surviving signal is a fitted composite of role,
  size, clustering, R&D context, and per-insider historical accuracy
  (Blonien-Crane-Crotty 2023: signal lives at the *insider* level). A frozen "N
  insiders in W days" cluster rule is the dominated single-characteristic filter the
  literature explicitly warns against. CMP-2012 opportunistic/routine is 1986–2007 data.
- **FAIL #4 moat (decisive)** — the harvestable-after-filing residual is latency-arbed:
  Ozlen-Batumoglu 2026 (SSRN 5966834) find **70–80% of the return occurs between
  transaction and public filing**; Blonien et al. find impounding "more quickly in
  recent years"; Jiang-Martin-Yin 2025 find the SOX 2-day speedup *increased insiders'*
  profits via coordination — the follower's queue position got worse, not better.
- **FAIL #1 persistence + FAIL #3 costs (both mixed → locked default)** — post-2015
  alphas exist only equal-weighted/small-cap/short-horizon/gross (the cost-trap
  configuration); no frozen-rule net-of-cost 2015+ test found; the post-filing residual
  (~20–30 bps/mo of a 1%/mo EW alpha) sits inside small-cap spread costs.
- **PASS #5 tail** (diversified long small-cap book = haltable grind) and **PASS #6
  data — a reusable finding:** EDGAR Form 4 is free/bulk/2003+ incl. dead companies,
  and survivorship-free US prices *with delisted stocks* are retail-priced (Norgate
  ~$630/yr, Sharadar alternative). **Single-name universes are now known-feasible for
  the lab**; the cef-discount data-kill does not generalize to equities.

New screen heuristic from this kill: for any follower/mimicry candidate (insiders,
13F cloning, congressional trades), first ask **where we sit in the disclosure latency
queue** — if the return accrues before or at the filing, daily-cadence retail is
structurally last. Revisit only if someone demonstrates post-filing harvestable alpha
for a frozen simple rule, net of costs, timed from the filing timestamp.

## Recommendation

~~Resume **spx-swing** (sign-offs → pregate diagnostic → verdict).~~ Done — pregate
failed, funnel worked as designed. ~~**ORB is next in line via strategy-designer**~~
Done — pregate passed (the lab's first), then rejected at the OOS engine gate
2026-07-05. ~~Turn-of-month next~~ — rejected at the research screen 2026-07-06 (see
#5). Both runner-ups screened the same day: sector-ETF momentum rejected (#7),
**pre-FOMC announcement drift passed (#6)** — implemented, then rejected at the OOS
engine gate 2026-07-06. **Volatility risk premium (#8) was next and is rejected at the
research screen 2026-07-07** — the funnel is empty again. VRP is the useful kind of
kill: not "edge gone" and not "cost eats it" (the first nine failure modes) but "real,
cheap edge we cannot pre-register without a sizing sweep, with a tail our risk infra
cannot bound." That maps a boundary — the next candidate should be screened not only for
edge and cost but for **(a) a single canonical rule that survives without a sweep and
(b) a worst-day loss our `halt_on_drawdown` can actually stop.** Treat one candidate at
a time — the funnel's value is cheap, honest rejections, and the scarce resource is
out-of-sample looks, not ideas.

**Update 2026-07-08 — that boundary is exactly what multi-asset TSMOM (#9) was screened
against, and it PASSED all four criteria (first research-screen pass in the funnel).**
It is the inverse of VRP: single canonical rule (12-month sign), positive-skew/haltable
tail, cost-survivable low turnover — weak only on the standalone-return/benchmark axis,
which reframes honestly as a diversifier gate. Next actions: build the diversified
liquid-ETF basket (self-adjusted, audited splice) and a strategy-designer spec with the
benchmark restatement and a lean-inclusive OOS window locked ex-ante. The real OOS looks
— where ORB and FOMC died — are still ahead.

**Update 2026-07-10 — TSMOM (#9) was rejected at the pregate (timing is diversification
beta, not trend alpha), turtle-soup rejected at pregate the same week, and cef-discount
(#10) rejected at the research screen** — first kill on data-feasibility + regime-change
grounds rather than edge/cost. Funnel is empty. Next-on-deck families, unscreened:
insider cluster buying (free EDGAR Form 4 data, capacity-constrained small-caps; known
risk = cluster-definition sweep) and spinoff forced-selling (structural payer = index
funds that must sell; known risks = event-data sourcing and mixed post-2010 evidence).
Both should be pre-registered against the full six-criterion screen including data
feasibility before any evidence is read.

**Update 2026-07-10 (later) — insider-cluster (#11) REJECTED at the research screen**
(composite-not-rule + disclosure-latency queue; see entry above). Funnel empty again.
Remaining next-on-deck: **spinoff forced-selling** — now more testable than when first
logged, since #11's screen established that survivorship-free single-name data is
retail-feasible (Norgate). Its screen must confront: (a) event-list sourcing at retail
cost, (b) mixed post-2010 evidence, (c) the latency-queue question (spinoff selling
pressure is spread over weeks, not a filing-timestamp race — argue it, don't assume it).

Data-pipeline follow-up (independent of any strategy): the audits run for the splice
found Alpaca's `adjustment=all` series missing the 2016-03-18 and 2018-06-15 SPY
dividends and double-applying the 2022-09-19 QQQ dividend (~18 bps on one
overnight-long OOS night — immaterial to its verdict; WF file clean, Monday paper
unaffected). Consider making raw-prints + self-applied CRSP adjustment (as built in
`scripts/build_spy_eod_splice.py`) the house convention for all adjusted data.
