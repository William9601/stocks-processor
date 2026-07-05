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

### 2. Opening range breakout (ORB), 5-min, QQQ — the day-trading candidate

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

## Recommendation

~~Resume **spx-swing** (sign-offs → pregate diagnostic → verdict).~~ Done — pregate
failed, funnel worked as designed. **ORB is next in line via strategy-designer**, with
the standard pregate-first pattern (gross follow-through of the 5-min opening range
direction, measured outside the engine, before any core intraday-stop machinery gets
built). Treat one candidate at a time — the funnel's value is cheap, honest rejections,
and the scarce resource is out-of-sample looks, not ideas.

Data-pipeline follow-up (independent of any strategy): the audits run for the splice
found Alpaca's `adjustment=all` series missing the 2016-03-18 and 2018-06-15 SPY
dividends and double-applying the 2022-09-19 QQQ dividend (~18 bps on one
overnight-long OOS night — immaterial to its verdict; WF file clean, Monday paper
unaffected). Consider making raw-prints + self-applied CRSP adjustment (as built in
`scripts/build_spy_eod_splice.py`) the house convention for all adjusted data.
