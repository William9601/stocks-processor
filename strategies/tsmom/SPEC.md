# Strategy: tsmom

- **Status**: **REJECTED at the pregate / spec-validation (2026-07-08)** — see Verdict
  at the end of this file. Research screen PASSED (4/4); basket data built + audited;
  spec approved + criteria FROZEN; then the IS-only pregate showed the 12-month timing
  does **not** beat holding the same diversified basket in-sample (EDGE(IS) = −0.39
  Sharpe). Binding gate binds; no tuning; OOS/WF stay unread. 10th candidate death.
- **Created**: 2026-07-08
- **One-liner**: Diversified time-series momentum — go long instruments whose trailing
  12-month excess return is positive and short those whose is negative, inverse-vol
  sized to a portfolio vol target, rebalanced monthly, across an 8-ETF basket spanning
  equities, bonds, commodities, and the dollar.

> **Provenance.** Moskowitz, Ooi & Pedersen (2012, *Journal of Financial Economics*,
> "Time Series Momentum"): the sign of a security's own trailing ~12-month excess
> return positively predicts its next-month return, positive for **every one** of 58
> futures/forwards across equity indices, bonds, commodities and currencies over
> >25 years — robust across lookbacks and sub-samples. Hurst, Ooi & Pedersen (2017,
> "A Century of Evidence on Trend-Following Investing"): a diversified trend program
> is **positive in every decade since 1880**, strongest in the worst equity/bond
> environments. The adversarial record, on file before this spec (`docs/strategy-candidates.md`
> #9): diversified trend had a weak "lost decade" 2009–2019 (low-vol, whipsaw, rising
> cross-asset correlation), rescued mainly by 2014 and COVID, then strong 2021–2023 on
> inflation/rate/USD trends; and the SG Trend Index fell **−20.4% May-2024 → May-2025**,
> its 2nd-largest drawdown since 2000 — a lean regime is live right now. **The
> falsifiable working hypothesis this spec tests: diversified 12-month TSMOM adds
> risk-adjusted return AND crisis convexity over simply holding the same basket, and
> does so through a pre-registered OOS window that includes lean years — not just the
> 2022 revival.**

## Hypothesis

**Effect.** Across liquid, diversified futures/ETF markets, an instrument's own
trailing ~12-month return predicts the sign of its next-period return. Trading that
sign — long winners, short losers — long/short and inverse-vol sized, produces a
positively-skewed "crisis-alpha" return stream lowly correlated to equities.

**Mechanism — who is on the other side and why do they keep paying?**

- **Under-reaction then delayed over-reaction.** Investors under-react to gradual
  information diffusion (anchoring, disposition effect — selling winners too early,
  holding losers), so trends persist for months before over-shooting and reversing at
  >12-month horizons (MOP document exactly this partial reversal). The counterparty is
  the slow-to-update crowd and the disposition-biased holder.
- **Non-price-maximizing flows trend-followers lean against.** Hedgers, central-bank
  FX intervention, rebalancers, and vol-target/risk-parity de-grossers transact on
  mandate, not expected return — a structural payer class, the same species that
  underwrites the (shelved) overnight book's premium.
- **The premium is compensation for a real cost: whipsaw.** Trend earns a
  long-straddle-like convex payoff (positive skew, wins big in sustained crises) and
  pays for it with a steady bleed of small losses in range-bound, mean-reverting,
  low-vol regimes. That bleed *is* the risk premium, and it is why the strategy had a
  lost decade and is in drawdown now. This is the honest core of the trade, not a bug.

**Why this is the inverse of the last candidate (VRP, #8).** VRP was short an
un-haltable overnight tail (XIV −96% in hours). TSMOM is *long* convexity: its
drawdowns are slow, vol-scaled grinds (SG Trend max DD ~20.6% over 12–24-month
recoveries), so `halt_on_drawdown` on daily-bar realized MTM can actually bound the
worst case — the property that passed criterion #4 of the screen.

**Diversification is the whole thesis — and the whole risk of self-deception.** Trend
on equities alone is closet beta (it would fail the house benchmark gate by
construction, exactly as sector-momentum #7 did). The edge lives in being *multi-asset*
and *timed*. That creates the spec's central discipline: the benchmark is **not** SPY,
it is a **static always-long version of this same basket** (same instruments, same
inverse-vol sizing, same vol target, never short). If the 12-month timing signal does
not beat *holding the diversified basket*, then any return is diversification beta, not
trend alpha, and the verdict is REJECT. This restatement of the house "beat SPY drift"
gate is locked here, before any data is scored — loosening a benchmark after seeing the
number is exactly the motivated reasoning that quant-review rejected on the overnight-long
rescue.

**Adversarial notes — read before falling in love:**

1. **The lab base rate is nine rejections; "published-then-gone" is confirmed in-house.**
   TSMOM is one of the most-cited anomaly papers of its decade and is the basis of a
   multi-hundred-billion-dollar managed-futures industry — i.e., maximally crowded and
   maximally post-publication. The OOS is entirely post-2012-publication on purpose.
2. **The decay is refereed and live.** The 2009–2019 lost decade is documented; the SG
   Trend Index is in a −20% drawdown as of mid-2025. If the OOS blend (which includes
   lean years by construction) cannot clear the frozen bars, the strategy fails — that
   is the design, not a flaw.
3. **"Diversification beta, not alpha" is the most likely quiet failure.** A vol-scaled
   long/short multi-asset book can post a decent standalone Sharpe purely from holding
   uncorrelated assets, with the timing adding nothing. The static-basket benchmark
   gate (#2 below) exists precisely to catch this; it is the binding economic test.
4. **Costs from turnover are real but not the assassin.** Monthly rebalance of 8
   inverse-vol positions turns over maybe ~200–400%/yr; at ~1–3 bps ETF spreads that is
   tens of bps/yr, comfortably inside a vol-targeted return — unlike the intraday and
   overnight candidates, cost is not expected to be the gate here (it must still be
   modeled and survived at 1.5×).
5. **ETF proxies dilute the documented futures effect.** MOP trade 58 futures; we trade
   8 ETFs. Fewer instruments = less diversification = noisier, and ETF financing/expense
   drags differ from futures roll. Accepted: the lab's infra is cash ETFs on daily bars;
   no futures machinery will be built for this spec. The benchmark uses the *same* ETFs,
   so the proxy dilution is common-mode and cancels in the edge comparison.

## Universe & timeframe

- **Instruments (LOCKED): the 8-ETF diversified basket** — equities SPY / EFA / EEM,
  bonds IEF / TLT, commodities DBC / GLD, dollar UUP. Four asset classes; all liquid,
  all cash-settled, all self-adjusted and audited
  (`experiments/tsmom/2026-07-08-basket-build/`). This exact set is pre-registered —
  **no adding/dropping instruments to fish for a pass, no swapping DBC→USO or TLT→AGG as
  a promotion path.** If the basket fails, the strategy is rejected, not re-composed.
- **Bar size / data resolution**: daily total-return bars (self-adjusted; UTC `ts`
  index via `core.data.feed.load_bars`). No intraday data, no quotes.
- **Trading session**: US regular session; the only transacted prints are **closing
  auctions (MOC)** on rebalance days — reuses the daily-bar MOC path built for
  fomc-drift (`FillTiming.NEXT_CLOSE`; `scripts/build_spy_daily_moc.py` session-close
  re-stamp). **No core extension is expected** (flagged to verify at implementation).
- **Holding period**: positions held ~1 month between rebalances; both long and short;
  overnight and cross-session exposure by construction (this is not a day-trading
  strategy — it is the lab's first multi-week holding book, chosen deliberately for its
  crisis-convexity and cost-amortization properties).

## Signals

**Everything below is pre-registered from MOP's canonical specification. There will be
no lookback sweep, no vol-target sweep, no rebalance-frequency sweep, no long-only
variant as a promotion path — ever. The 12-month lookback is chosen because it is the
documented survivor across sub-samples, not because it tested best here (it has not
been tested here).**

**Definitions (per instrument `i`, evaluated at each monthly rebalance date `t`, using
only completed daily bars strictly before the rebalance decision):**

- **Signal `s_i(t) = sign( r_i(t−252 … t) − rf )`** — the sign of the trailing
  **252-trading-day** (≈12-month) total return in excess of the risk-free rate.
  `+1` → long, `−1` → short. (Excess-of-cash so the sign reflects real outperformance,
  not just nominal drift; `rf` from a short-rate series, see Data.) A flat/zero reading
  (exactly 0, measure-zero) defaults to flat.
- **Ex-ante volatility `σ_i(t)`** — annualized realized volatility of instrument `i`'s
  daily returns over the trailing **60 trading days** (causal, completed bars only).
- **Position weight** `w_i(t) = s_i(t) · (σ_target_inst / σ_i(t))`, i.e. each position
  scaled to a constant per-instrument risk contribution (inverse-vol), MOP-style.
- **Portfolio vol targeting**: scale the whole book by `k(t) = σ_target_port / σ̂_p(t)`
  where `σ̂_p(t)` is the ex-ante portfolio vol (from the weighted positions and the
  trailing 60-day covariance, or a simpler sum-of-risks proxy — the exact estimator is
  pre-registered at sign-off, not tuned). **Gross leverage cap: 3× equity** (managed-
  futures norm; flagged for sign-off). Net long/short exposure is whatever the signals
  imply — not neutralized (this is time-series, not cross-sectional, momentum).

**Entry / exit / rebalance:**

- **Rebalance frequency (recommended, flagged): monthly**, last trading day of each
  month, via **MOC** on that session's close. Monthly is MOP's canonical holding period
  and keeps turnover/costs low; a daily or weekly rebalance would be a different
  (un-pre-registered) strategy.
- On each rebalance date: recompute all `s_i`, `σ_i`, weights, and `k`; trade the
  **difference** from current holdings to target (only the delta crosses the spread).
- **Exit (profit): none. Exit (stop): none per-position.** A position is held to the
  next rebalance regardless of P&L; risk is controlled by inverse-vol sizing, the
  portfolio vol target, and the drawdown kill switch — never by an intra-month stop
  (consistent with the daily-bar book having no intrabar print to stop on).
- **Signal at `t` uses only data strictly before `t`.** No `.shift(-1)`, no same-bar
  fill: the rebalance decision is made from completed bars and filled at the *next*
  qualifying close via `NEXT_CLOSE` (quant-review to confirm zero lookahead, as for every
  prior strategy).

**Diagnostic-only columns (pre-registered now so they cannot appear post hoc; never
gates, never verdict numbers, never promotion paths):** per-instrument and per-class
contribution to return and risk; long-leg vs short-leg P&L separately; gross vs net
exposure over time; realized vs target vol; turnover per rebalance; per-year returns;
rolling 12-month correlation to SPY; return in the worst-SPY-quartile months (the
convexity check); max drawdown and its duration.

## Risk

- **Portfolio vol target `σ_target_port` (recommended, flagged): 10% annualized.**
  Modest for a diversified trend book (managed-futures run 10–20%); 10% keeps the
  standalone drawdown inside the kill switch and makes the strategy a sleeve, not a
  swing-for-the-fences book.
- **Per-instrument target `σ_target_inst` (recommended, flagged): 10%/√8 ≈ 3.5%**, i.e.
  equal-risk-budget across the 8 instruments before portfolio scaling. (Exact value is a
  normalization; the portfolio target `k` is what binds.)
- **Gross leverage cap: 3× equity** (flagged). Inverse-vol sizing on low-vol instruments
  (IEF, UUP) can demand large notionals; the cap bounds it. Bonds/EM/commodity ETFs are
  all shortable and marginable.
- **Max concurrent positions**: up to 8 (one per instrument), long or short.
- **Per-trade / per-position stop**: none (see Signals).
- **Daily loss limit**: house `RiskManager.on_bar()` 2·(daily σ budget) → halt-and-review,
  anchored to prior session close.
- **Max drawdown kill switch (recommended, flagged): 20%** peak-to-trough equity. This
  is *wider* than the house 15% and much wider than fomc's 5% — deliberately, because a
  ~20% drawdown is *normal operation* for diversified trend (SG Trend max ~20.6%), not
  anomalous. The screen's criterion #4 is precisely that this drawdown is a slow grind
  `halt_on_drawdown` can bound; the kill switch is the realization of that property.
  Setting it too tight would halt the book in its ordinary whipsaw and guarantee failure.
- **Reporting (LOCKED)**: net and gross return, Sharpe, Sortino, max DD and duration,
  realized vol vs target, per-class and per-instrument attribution, long/short attribution,
  turnover and cost drag per rebalance, rolling correlation to SPY, worst-SPY-quartile
  return, and every number computed **both** for TSMOM and for the static-basket
  benchmark on the identical window.

## Data requirements

- **The 8-ETF total-return basket, 2007-03 → present — already built and audited.**
  Files `data/tsmom/<TICKER>_daily_adj.parquet` (gitignored); builder
  `scripts/build_tsmom_basket.py`; audit `experiments/tsmom/2026-07-08-basket-build/basket_report.json`
  (self-adjust vs Yahoo AdjClose ≤ 0.02 bps/day all 8; cross-vendor median < 2 bps).
  Common start **2007-03-01** (UUP inception binds). **Never** use Alpaca
  `adjustment=all` unaudited (house dividend-bug finding).
- **Risk-free / short-rate series (new input, small):** a daily short rate for the
  excess-return sign and any cash drag — 13-week T-bill (^IRX) or the Fed funds rate,
  committed as a small CSV with its source. Signal robustness to `rf` is a diagnostic
  (the sign rarely flips on `rf` at a 12-month horizon), not a tuned parameter.
- **Reproducibility (house rule 5)**: every run records vendor, data range, adjustment
  method, per-file `data_sha256`, `rf` source/version, seed, git commit.

## Cost assumptions

Costs are mandatory (house rule 3), modeled in `core/backtest/costs.py`. Rebalance
trades are ETF closing-auction MOC fills.

- **Commission**: $0/share (Alpaca).
- **Half-spread (recommended, flagged): 1.5 bps/side** — conservative for these ETFs
  (SPY ~0.2 bps, but EEM/DBC/UUP wider; 1.5 bps covers the basket).
- **MOC auction slippage: 0.5 bps/side.**
- **Short financing / borrow (LOCKED): 50 bps/yr** charged on average short notional.
  These 8 ETFs are general-collateral / easy-to-borrow, so 50 bps/yr is conservative
  (typical GC borrow is single-digit to low-tens of bps); charged, not assumed zero.
- **LOCKED cost bar**: full round-trip **4.0 bps** per unit of turnover (1.5+0.5 per
  side ×2), plus **50 bps/yr borrow** on shorts. **Pre-registered 1.5× companion (6.0 bps
  + 75 bps/yr borrow)** the OOS must survive.
- **Expected annual drag**: turnover ~200–400%/yr × 4.0 bps ≈ **8–16 bps/yr** plus
  borrow — not the binding gate; the binding gate is the diversifier edge.

## Success criteria (locked before first backtest)

**PENDING sign-off — not yet frozen.** Once signed off, every parameter (basket,
12-month rule, sizing, vol target, rebalance, costs, windows) is pre-registered and
**nothing is ever swept**.

### Benchmark-gate arithmetic — the diversifier restatement (the crux)

The benchmark is the **static basket**: the identical 8 instruments, identical
inverse-vol sizing and identical portfolio vol target, but **always long, never short,
signal ≡ +1** (i.e. buy-and-hold the diversified risk-balanced basket). Define, for an
era `E`:

- `TSMOM(E)`, `STATIC(E)` = net annualized Sharpe of the timed book and the static
  basket over `E`.
- **Diversifier edge** `EDGE(E) = TSMOM(E) − STATIC(E)` (Sharpe units).

A timed trend book that does not beat *holding the same basket* is diversification beta
plus a momentum story — the arithmetic that killed spx-swing (vs SPY drift) and
sector-momentum (closet beta), applied here with the honest, common-mode benchmark.

### PREGATE — pre-scoring diagnostic (run FIRST, outside the engine, IS only)

Standalone script (`scripts/pregate_tsmom.py`, following the prior pregates), on the IS
window only; **OOS and WF stay unread.** Computes the TSMOM and STATIC net-Sharpe,
`EDGE(IS)`, the worst-SPY-quartile return for both, turnover, and the diagnostics.

**Gate rule (LOCKED before the script is written) — REJECT at spec validation if:**

- `EDGE(IS) ≤ 0` — the timing does not beat holding the basket in-sample (dead on
  arrival, like a gross-negative pregate), **or**
- TSMOM IS net Sharpe `< 0.3` — even in-sample the book does not clear a minimal
  standalone bar (flagged; the reproduction-bar analogue), **or**
- TSMOM IS worst-SPY-quartile return `< STATIC` — the timing removes rather than adds
  crisis convexity, contradicting the entire thesis.

On PASS: implement against core, engine IS run reproduces the pregate to rounding (the
orb/fomc cross-check pattern), then the **one** pre-registered OOS look + its 1.5×-cost
companion. On FAIL: reject, no tuning, post-mortem in this file.

### Backtest bars (engine, net of the locked 4.0 bps + borrow; OOS window below)

| # | Frozen bar |
|---|---|
| 1 | **OOS net Sharpe ≥ 0.5** annualized (honest for decayed diversified trend; MOP-era was ~0.7–1.0, recent SG Trend ~0.3–0.5 net — 0.5 sits at the low end of "the edge is still there") |
| 2 | **Diversifier gate**: `EDGE(OOS) > 0` — TSMOM net Sharpe beats the static basket over the identical OOS window; **and** OOS worst-SPY-quartile-month return ≥ static basket's (convexity preserved) |
| 3 | **Still a diversifier**: OOS return correlation to SPY **≤ 0.30** (a trend book that has quietly become long-equity beta fails, even if Sharpe passes) |
| 4 | **Cost survival**: net-positive Sharpe **and** `EDGE(OOS) > 0` still hold at **1.5× costs (6.0 bps + 1.5× borrow)** |
| 5 | **Haltable tail confirmed**: max OOS drawdown ≤ **25%** and its worst *single-day* loss ≤ **8%** (verifies the grind-not-gap property the screen assumed; a breach means the tail is not what criterion #4 claimed) |
| 6 | **IS→OOS decay guard**: OOS net Sharpe not more than 50% below IS (house convention) |
| 7 | **Minimum sample**: OOS spans ≥ **60 months** with the full basket (true by construction for the window below) |

**No-rescue clause (LOCKED):** per-era and per-class splits (lean 2017–2019 vs 2020–2024
revival; equity vs bond vs commodity vs FX legs) are mandatory **diagnostics and never
gates in either direction.** A full-OOS fail cannot be rescued by a strong 2020–2024
sub-era or a strong commodity leg; the book trades all instruments unconditionally and
is judged on the blend. No dropping the worst leg, no regime filter, no lookback change
between IS and OOS.

### Windows (pre-registered — recommended, flagged)

- **In-sample: 2008-03 → 2016-12** (~9 yrs; first valid signals ~2008-03 after the
  12-month warm-up on the 2007-03 basket). Contains the 2008 crisis (trend's canonical
  win) and the first half of the lost decade.
- **Out-of-sample: 2017-01 → 2024-12** (~8 yrs). Contains the **lean 2017–2019 tail of
  the lost decade** (no cherry-picking the revival), 2020 COVID, the 2022 revival, and
  the **2024 drawdown** — the lean-inclusive OOS the screen requires.
- **Walk-forward: 2025-01 → present, unread until the OOS verdict.** Captures the tail
  of the SG-Trend −20% drawdown — the live caveat; WF is the number that would count for
  any paper decision.

## Known failure modes

- **Range-bound / low-vol / choppy regimes (the documented quiet failure).** Whipsaw:
  the signal flips repeatedly and each flip pays the spread while trends fail to
  develop. This is the lost decade and the current drawdown. *Bounding:* monthly (not
  daily) rebalance limits flip frequency; vol targeting shrinks size when moves are
  small; the 20% kill switch backstops a pathological run.
- **Sharp reversals after strong trends (the signature acute loss).** V-shaped
  bottoms/tops (2009-03, COVID-03/04, 2020 rebound) whipsaw a trend book badly — it is
  positioned for continuation exactly when the market reverses. Positive skew means these
  are frequent small-to-medium losses, not a wipeout. *Bounding:* vol targeting, kill
  switch, and the honest expectation that these months are negative by design.
- **Diversification collapse (the correlation-goes-to-1 risk).** In a broad
  risk-off/margin event, cross-asset correlations spike and the "diversified" basket
  becomes one bet — bonds can sell off *with* equities (2022, 2013 taper). *Bounding:*
  the short legs help (trend was short bonds in 2022), but the failure is real and is
  why the OOS includes 2022; and the diversifier gate is measured, not assumed.
- **"Diversification beta, not alpha."** Covered above — the static-basket benchmark
  gate is the direct test.
- **ETF-proxy / financing drift.** ETF expense ratios, tracking error, and short-borrow
  costs differ from the futures the effect was documented on. *Bounding:* modeled borrow,
  1.5× cost companion, and the common-mode benchmark (same ETFs) that cancels level
  effects.
- **Overfitting the vol-targeting machinery.** The covariance/vol estimator, the
  leverage cap, and the target level are all places tuning could sneak in. *Bounding:*
  all pre-registered at sign-off; the estimator is the simple 60-day causal one, chosen
  before scoring, never swept.

## Sign-offs (RESOLVED 2026-07-08 — criteria frozen from this point)

Put to the user before any data was scored; resolved as follows. Immovable now —
nothing below is ever swept.

1. **Direction — SIGNED OFF: LONG/SHORT** (canonical MOP; the diversifier thesis
   requires the short leg — short bonds 2022, short EEM 2008 = the crisis alpha). Borrow
   modeled per Costs.
2. **Lookback — SIGNED OFF: 12 months (252 trading days)**, sign of trailing excess
   return. Documented cross-sample survivor; **no 1/3/12-month blend, no sweep.**
3. **Rebalance — SIGNED OFF: monthly** (last trading day, MOC).
4. **Sizing — SIGNED OFF: inverse-vol (60-day causal) per instrument + 10% portfolio vol
   target + 3× gross leverage cap.** Estimator and target frozen; never tuned.
5. **Benchmark — SIGNED OFF: the STATIC-BASKET diversifier gate** (same instruments,
   always long, same sizing) as the binding economic test, replacing "beat SPY drift."
   Governance-critical, locked before any OOS look.
6. **Costs — SIGNED OFF: 1.5 bps/side spread + 0.5 bps/side slippage (4.0 bps RT) + 50
   bps/yr short borrow**; 1.5× companion (6.0 bps + 75 bps/yr borrow) the OOS must survive.
7. **Windows — SIGNED OFF: IS 2008-03→2016-12 / OOS 2017-01→2024-12 (lean-inclusive) / WF
   2025-01→ unread until the OOS verdict.**
8. **Success bars — SIGNED OFF as a set** (OOS Sharpe ≥ 0.5; EDGE(OOS) > 0 + convexity
   preserved; corr-to-SPY ≤ 0.30; cost survival at 1.5×; max DD ≤ 25% / worst day ≤ 8%;
   decay ≤ 50%; ≥ 60 OOS months; no-rescue clause on era/leg splits).
9. **Kill switch — SIGNED OFF: 20%** peak-to-trough equity (wider than house 15% by
   design — a 20% grind is normal trend behavior and the criterion-#4 haltable-tail
   property).

**Next step per the funnel:** write `scripts/pregate_tsmom.py` (IS-only: TSMOM vs
static-basket net Sharpe, `EDGE(IS)`, worst-SPY-quartile convexity, turnover) → verdict
at the pregate before any engine code or OOS look. Expected per the lab's base rate: a
real chance of rejection at the diversifier gate (EDGE(IS) ≤ 0) — the cheap, honest kill
this funnel is built to deliver.

## Verdict — REJECTED at the pregate / spec-validation (2026-07-08)

The frozen IS-only pregate (`scripts/pregate_tsmom.py`,
`experiments/tsmom/2026-07-08-pregate/`) ran exactly as pre-registered: it simulated the
long/short 12-month book and the STATIC always-long same-basket benchmark through
identical inverse-vol / vol-target / cost machinery, scored on **IS 2008-04 → 2016-12
only** (OOS and WF hard-sliced out before any computation).

**Scorecard (net of 4.0 bps RT + 50 bps/yr borrow; n = 105 months):** two of three
frozen gates fail.

| Gate | Result | |
|---|---|---|
| `EDGE(IS) > 0` (TSMOM Sharpe beats STATIC) | TSMOM 0.258 − STATIC 0.650 = **−0.392** | **FAIL** |
| TSMOM IS net Sharpe ≥ 0.30 | **0.258** | **FAIL** |
| TSMOM worst-SPY-quartile ≥ STATIC | +0.17% vs −0.94% | pass |

**Why it failed — "diversification beta, not alpha," confirmed.** Over the pre-registered
in-sample decade, simply *holding* the risk-balanced 8-asset basket (STATIC, Sharpe 0.65,
7.03%/yr) beat *timing* it with 12-month momentum (TSMOM, Sharpe 0.258, 2.86%/yr). The
gap is in **gross return, not costs**: TSMOM's gross Sharpe (0.305) is already less than
half STATIC's, and borrow+turnover is only ~0.5pp/yr of the 4.2pp/yr return gap — the
timing itself underperformed. The per-year path is textbook lost-decade trend: crisis
alpha (2008 +5.9%, 2013 +21%) overwhelmed by whipsaw (2009 −8.5%, 2014 −6.5%, 2016
−12%), max DD −19% (the ~20% grind the screen predicted). The **one thing the timing
added was convexity** — it protected in the worst SPY months (+0.17% vs −0.94%), passing
that gate — but convexity alone did not pay for the whipsaw drag.

**The benchmark restatement did its job.** This is the exact failure criterion #3 of the
research screen was built to catch, and the reason "beat SPY drift" was replaced with
"beat the static basket": a vol-scaled multi-asset long/short book posts a plausible
standalone Sharpe (0.26, corr-to-SPY −0.04 — a genuine diversifier) purely from holding
uncorrelated assets, while the momentum timing subtracts risk-adjusted return. Against
SPY this might have looked passable; against the honest common-mode benchmark it does not.

**Discipline held (stated, not as a rescue).** The IS window is the documented 2009–2019
"lost decade," and the sealed OOS (2017–2024) contains the 2022 revival that might well
score better — but the frozen gate is IS-fail → REJECT, and the no-peek / no-rescue
clauses forbid reading OOS, re-slicing the window, dropping the worst leg, or gating the
signal. That discipline is what the funnel is for; re-litigating a frozen gate after
seeing the number is the motivated reasoning quant-review rejected on overnight-long.

**Tenth candidate death — the VRP-grade useful kind.** Not "no edge / no data": the
mechanism is real, the tail is haltable, the convexity showed up, cost is not the
assassin. It dies because, over the pre-registered in-sample window, the timing is
diversification beta rather than trend alpha — a clean, cheap kill at spec-validation
before any engine code or the single OOS look was spent. Cost of the kill: one session.

**What survives as infrastructure:** the audited multi-asset basket builder
(`scripts/build_tsmom_basket.py`, 8 ETFs, self-adjusted, split×dividend-correct) and the
committed 13-week rf series (`strategies/tsmom/rf_13w.csv`) — the lab's first multi-asset
daily universe, reusable by any future cross-asset candidate. The user chose to record
the death on my own verification (kill is in gross return, machinery common-mode) without
a separate quant-reviewer pass.
