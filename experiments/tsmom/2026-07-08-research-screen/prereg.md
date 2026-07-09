# TSMOM (multi-asset time-series momentum / trend-following) — research screen

**Pre-registration. Criteria and pass/fail thresholds are LOCKED as of 2026-07-08,
before the decisive evidence is scored.** No spec, no code, no data infra until this
screen passes. Verdict appended below the lock line.

Candidate: diversified time-series momentum. Canonical rule under test: **sign of the
trailing 12-month excess return sets the position (long/short), sized inverse-vol,
rebalanced monthly**, across a multi-asset basket (equity indices, sovereign bonds,
commodities, FX). Reference: Moskowitz, Ooi & Pedersen (2012).

Mechanism (who pays, why it persists): behavioral under-/over-reaction + demand for
liquidity from hedgers/rebalancers who trade against, not with, trend; and a
risk-transfer story (trend earns its keep by being long convexity in crises). The
payoff is a synthetic long-straddle: positive skew, "crisis alpha."

## Why it reaches the screen (boundary the 9 deaths mapped)

The next candidate had to be screened not only for edge + cost but for (a) a single
canonical rule surviving without a sweep, and (b) a worst-day loss `halt_on_drawdown`
can actually stop. TSMOM is the first candidate whose defining property *inverts* the
tail flaw that killed VRP (#8): positive-skew convexity instead of an un-haltable short
tail.

## The four locked criteria (all four must PASS)

1. **Post-2011 persistence on a DIVERSIFIED basket.** Independent evidence must show
   positive net-of-cost performance for diversified trend over a window that *includes*
   the 2011–2019 "lost decade" — not a sample that starts at the 2022 revival.
   PASS = at least one credible independent test reports positive net Sharpe over a
   window containing 2011–2019; FAIL = the only positive results start post-2019 or
   exclude the lean years.

2. **Single canonical rule, no sweep.** The ~12-month lookback must be the *documented
   survivor*, not one knob on a lookback/vol-scaling/basket-choice sweep whose headline
   depends on the tuning. PASS = 12-month TSMOM is robust across lookbacks/sub-samples
   in the source literature (i.e. the rule is pre-registrable as-is); FAIL = published
   Sharpes hinge on which lookback / vol-scaling / basket is chosen (the ToM/VRP failure
   mode).

3. **Benchmark gate honestly restatable for a diversifier.** Equity-only trend is closet
   beta and fails "beat SPY drift" by construction. PASS = there is a legitimate,
   pre-registrable restatement — trend must add risk-adjusted return AND low/negative
   SPY correlation (crisis convexity) to a SPY book — that quant-review would bless as
   non-motivated. FAIL = the only way to make it clear the gate is to drop the gate.

4. **Worst-day loss is haltable (grind, not gap).** The worst realized drawdown must be
   the kind `halt_on_drawdown` (daily-bar realized MTM) can bound — a whipsaw grind, not
   an overnight gap-to-termination like XIV. PASS = diversified trend's drawdowns are
   drawn-out and vol-scaled, no single-day wipeout mechanism; FAIL = a plausible
   overnight/gap event can blow through a daily-bar halt.

## Decision rule

All four PASS → commit to the multi-asset data infra and a strategy-designer spec (with
the criterion-3 benchmark restatement written into the spec and locked before any OOS
look). Any FAIL → reject at the research screen, log the boundary, move on. One candidate
at a time; the scarce resource is OOS looks, not ideas.

<!-- ===================== LOCK LINE — evidence scored below this point ===================== -->

## Verdict 2026-07-08 — PASS (4/4). First candidate to clear the research screen.

Scored against the four criteria exactly as locked above. This authorizes the expensive
next step (multi-asset data infra + a strategy-designer spec); it does **not** mean the
strategy works. ORB and FOMC both PASSED their pregate and then DIED at the OOS engine
gate — the real out-of-sample looks are still ahead of TSMOM, not behind it.

**#1 Post-2011 persistence on a diversified basket — PASS (with a live caveat).**
The 2010s were genuinely weak: diversified trend "performed predictably poorly during
the 2010s in an environment of artificially reduced volatility" (a low-vol, whipsaw,
rising-cross-asset-correlation regime), saved mainly by 2014 and COVID. But the locked
threshold is "≥1 credible independent test reports positive net Sharpe over a window
containing 2011–2019," and that is met: Hurst et al.'s century study shows positive
returns in *every decade including the 2010s*, and the 28-futures OOS test 2005–2024 is
profitable. So it does not FAIL — but the caveat is material and live: the SG Trend Index
fell **~20.4% May-2024 → May-2025, its second-largest drawdown since 2000**. The decay
risk is not just history; a lean regime is happening now. Logged as the single most
likely downstream killer (a lean OOS window posting sub-bar Sharpe, the ORB/FOMC failure
mode). ([Hurst et al.](https://fairmodel.econ.yale.edu/ec439/hurst.pdf),
[Top Traders Unplugged perf reports](https://www.toptradersunplugged.com/trend-following-performance-report-june-2025/),
[Cambridge Associates — structurally broken?](https://www.cambridgeassociates.com/insight/does-trend-followings-recent-struggle-signal-that-the-strategy-is-structurally-broken/))

**#2 Single canonical rule, no sweep — PASS.** The strongest gate for TSMOM. The sign of
the trailing 12-month excess return is robust across sub-samples and lookbacks and
positive for every one of MOP's 58 contracts — a genuinely pre-registrable specification,
not a knob on a sweep. This is the exact property ToM (#5) and VRP (#8) lacked. Caveat
logged, not disqualifying: production CTAs blend multiple lookbacks + vol-scaling, and
[recent work](https://arxiv.org/html/2510.23150v2) argues trend-premia structure hides
redundancy — but the *canonical academic rule* stands alone as pre-registrable, which is
all this criterion asks. ([AQR/MOP](https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum))

**#3 Benchmark gate honestly restatable for a diversifier — PASS.** Equity-only trend is
closet beta and fails "beat SPY drift" by construction; the whole literature instead
measures diversified trend as a *diversifier* — low-to-negative equity correlation and
positive crisis convexity that improves a 60/40 / SPY book. That reframe is what the
strategy IS, not a post-hoc loosening, so quant-review can bless it as non-motivated.
**Governance condition carried into the spec:** the restated gate (adds risk-adjusted
return AND negative-crisis-correlation to a SPY book) must be written and LOCKED before
any OOS look — the overnight-long "conservative-convention rescue" lesson: never loosen a
gate after seeing the number. ([AQR Managed Futures](https://funds.aqr.com/Insights/Strategies/Managed-Futures),
[Return Stacked](https://www.returnstacked.com/managed-futures-trend-following/))

**#4 Worst-day loss is haltable (grind, not gap) — PASS (decisive, the inverse of VRP).**
Diversified trend drawdowns are drawn-out and vol-scaled: SG Trend max drawdown ~20.6%
since 2000, typical peak-to-trough 15–25% over 12–24-month recoveries, ~16 drawdowns
>10% at roughly 18–24-month spacing. There is no single-day wipeout mechanism — because
the payoff is *long* convexity (positive skew), gap events tend to be favorable, not
fatal. A daily-bar `halt_on_drawdown` can bound a slow 20% grind; contrast XIV's −96%
overnight in hours (#8). This is the cleanest pass and the reason TSMOM was worth the
screen. ([SG Trend drawdown data](https://www.toptradersunplugged.com/trend-following-performance-report-april-2025/),
[Man Group — is this time different](https://www.man.com/insights/is-this-time-different))

## Decision

All four PASS → per the locked decision rule, **commit to the multi-asset data infra and
a strategy-designer spec.** The two things most likely to kill it downstream, logged now
so the spec confronts them head-on:
1. **Lean-regime OOS Sharpe below bar** (criterion-1 caveat; the ORB/FOMC death mode).
   The pre-registered OOS window must include a lean stretch (2011–2019 and/or the
   2024–2025 drawdown), no cherry-picking the 2022 revival.
2. **"Diversification beta, not alpha."** Is TSMOM's return alpha, or just payment for
   holding a multi-asset basket? The spec's benchmark must isolate trend's contribution
   vs a static multi-asset buy-and-hold, not just vs SPY.

Data infra required (new for the lab — all prior work was SPY/QQQ/DIA): a diversified
liquid-ETF proxy basket — equities (SPY/EFA/EEM), bonds (IEF/TLT), commodities
(DBC/GLD), dollar (UUP) — daily, self-adjusted (the Alpaca `adjustment=all` dividend
bug applies), with the same audited-splice discipline used for the SPY EOD series.

