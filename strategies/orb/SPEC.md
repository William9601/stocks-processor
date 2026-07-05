# Strategy: orb

- **Status**: approved — user signed off all 6 open baselines 2026-07-05 (see Decisions
  record at the bottom); success criteria FROZEN as of that sign-off, before the
  pregate ran. **PREGATE PASSED 2026-07-05** (first pass in the lab): IS 2018–2022
  mean gross +4.67 bps/trade (n=1,251, t=2.22) vs the locked 2.0 bps cost bar and the
  +1.19 bps unconditional drift; both sides positive, every year positive, payoff
  shape as hypothesized (24% hit rate, EoD winners +102 bps). OOS/WF unread. Next:
  core intrabar-stop extension, then engine backtest. Results:
  `experiments/orb/2026-07-05-pregate/`.
- **Created**: 2026-07-05
- **One-liner**: 5-minute opening range breakout on QQQ (Zarattini & Aziz 2023) — trade in the direction of the first 5-minute bar from the open of the second bar, stop at the opening bar's opposite extreme, flat by the close; both directions; pregate on gross follow-through before any core intraday-stop machinery is built.

> **Provenance.** Zarattini & Aziz (2023), "Can Day Trading Really Be Profitable?"
> (SSRN 4416622): 5-min ORB on QQQ, 2016-01 → 2023-02. Their rules: if the first
> 5-minute bar is directional, enter at the start of the second bar in that direction;
> stop at the opposite extreme of the first bar; profit target 10R; liquidate at the
> close otherwise. Their headline — $25k → $192,806 (675%, "annualized alpha 33%"), and
> 1,484% via TQQQ — is produced with risk-1%-of-capital sizing under a **4x leverage
> cap / 3x leveraged ETF**, **$0.0005/share commission, zero bid-ask spread, zero
> slippage**. The leverage and the friction-free fills are presentation, not edge; this
> spec tests the unlevered edge under house costs. Their 2024 follow-up (SSRN 4729284,
> "A Profitable Day Trading Strategy For The U.S. Equity Market") reports 5 minutes as
> the **best-performing of all range durations tested** — which is a selection-bias red
> flag, not a feature. Accordingly this spec **pre-registers the 5-minute range only;
> no duration sweeps, ever** (see Adversarial note #3).

## Hypothesis

**Effect.** The direction of the first 5 minutes of the US session predicts the sign of
the rest-of-day move often enough — or with enough right-tail asymmetry on the days it
is right — that entering at the second bar's open in that direction, with a stop at the
opening bar's opposite extreme and forced liquidation at the close, has positive gross
expectancy. The claimed payoff shape is low hit rate with occasional multi-R trend-day
winners, not frequent small wins.

**Mechanism — who is on the other side and why do they keep paying?**

- **Institutional parent-order flow.** Large orders triggered by overnight news are
  executed across the whole session via VWAP/TWAP schedules. The opening auction and
  first bar reveal the *direction* of that day's imbalance; the schedule then keeps
  pushing the same way for hours. The schedules pay because they are minimizing
  benchmark slippage, not maximizing expected return on the day.
- **Trend-day feedback.** On genuine trend days, option dealers hedging short gamma and
  intraday stop-outs of counter-trend positions add flow in the move's direction. The
  10R-style right tail lives on exactly these days.
- **The counterparties**: opening-move faders and intraday mean-reversion traders who
  fade a move that turns out to be information-driven, plus the mechanical flows above.

**The honest weakness of the mechanism:** it predicts the effect concentrates in
high-volatility, news-heavy regimes (2018 Q4, 2020, 2022 — most of the paper's sample)
and thins out in quiet tape. It does not explain why so simple and so public a signal
on the second-most-liquid ETF in the world would remain unarbitraged after an April
2023 paper with millions of reads. Our OOS and WF windows are almost entirely
**post-publication** — that is the sharpest available test, and it is deliberate.

**Diversification vs the existing book — stated, not hand-waved.** The paper book
(`overnight-long`, QQQ, in paper from 2026-07-06) holds close→open; orb holds
open→close and **never overnight** — zero overlap in holding hours, genuinely
complementary in time-of-day, and the same capital can in principle serve both books.
But on risk-on trend days both books are long QQQ beta within the same 24 hours, so
equity-curve correlation is not zero. **Reporting must include the daily-return
correlation vs the overnight-long book over the identical dates, and the long/short
split of orb's P&L** (a long-side-only edge is a beta artifact, not the hypothesis).

**Adversarial note — read before falling in love:**

1. **The base rate in this lab is poor and must be priced in.** Every validation run
   this month ended in rejection: `intraday-momentum` (published intraday SPY effect,
   Gao et al. — **absent in our own 2018–2024 SIP data, negative even gross**),
   `rsi-5050` (+0.30 bps gross vs a 3.5 bps cost bar), `spx-swing` (published daily
   effect — present in-sample 2005–2017, **gone OOS 2018–2024**). The one strategy in
   paper came from overnight drift. The closest in-house evidence — a *different*
   published morning-predicts-afternoon effect on an index ETF — was simply not there.
   The expected outcome for orb is **reject at the pregate**, and the spec is built so
   that outcome costs one session, not one core extension.
2. **The headline is leverage- and friction-flattered.** 675%/1,484% comes from ~4x /
   3x sizing with zero spread and zero slippage. The unlevered arithmetic (Cost
   assumptions) says the published per-trade edge (~0.1–0.2R gross ≈ 3.5–4.5 bps of
   notional) nets to roughly +5–7%/yr at ≤1x notional — a net Sharpe in the ~0.8–1.1
   range **only if the effect in our data is at least as strong as published**. There
   is no cushion.
3. **Duration-selection bias is documented by the authors themselves.** The 2024
   follow-up tested multiple opening-range durations and reports 5-min as best. A
   best-of-sweep parameter carried into a "validation" is pre-fit. Defense: 5 minutes
   is pre-registered here as the *only* duration; if it fails, the strategy is
   rejected — no 15/30/60-min rescue runs.
4. **Independent evidence is mixed at best.** The QuantConnect replication of the 2024
   paper found parameter sensitivity, a ~17% win rate, commission drag concerns, and
   collapse in other periods; a 2026 systematic falsification study on MNQ futures
   (arXiv 2605.04004) tested ORB variants and **all failed statistical significance**;
   CXO flags the zero-friction fill assumptions. The paper's own sample (2016–2023) is
   unusually rich in trend days.

## Universe & timeframe

- **Instruments (LOCKED): QQQ only.** Single pre-registered instrument, both
  directions. No basket, no TQQQ/SQQQ, no fallback — if QQQ fails, the strategy is
  rejected, not re-run on SPY/IWM to fish for a pass. Short side: QQQ is trivially
  easy-to-borrow; intraday shorts carry no overnight borrow fee because the book is
  always flat by the close.
- **Bar size / data resolution**: 5-minute RTH bars (SIP consolidated tape). The
  opening range is exactly the **09:30:00–09:35:00 ET bar** — pre-registered, never
  swept (see Adversarial note #3).
- **Trading session**: US regular session, 09:30–16:00 ET; all timestamps ET; RTH bars
  only. Early closes (13:00 ET) handled via the exchange calendar, never hardcoded.
- **Holding period**: **intraday only, one trade per day maximum, flat by close, no
  exceptions.** Entry no earlier than 09:35; forced flat at the open of the session's
  final 5-minute bar.

## Signals

**No lookahead.** The signal is computed from the **completed** 09:30–09:35 bar and
acts at the 09:35 open — next-bar-open, matching the core engine's `NEXT_OPEN` fill.
Nothing about bar 2 or later is used in the entry decision. Live path: real-time SIP
(Algo Trader Plus) makes the 09:35:00 computation + market order feasible; the
seconds of submission latency vs the backtest's 09:35 open print are a measured paper
divergence, not a backtest assumption.

### Definitions (per session; bar 1 = the 09:30–09:35 ET bar)

- `O1, H1, L1, C1` = OHLC of bar 1. `O2` = open of bar 2 (09:35–09:40).
- **Direction**: long if `C1 > O1`; short if `C1 < O1`; **no trade** if `C1 == O1`
  (doji) or `H1 == L1` (zero range). At penny resolution on a ~$500+ ETF these skips
  are rare (~1–3% of days).

### Entry

- At 09:35, **market order** in the bar-1 direction; backtest fill = `O2` plus modeled
  slippage against the trade.
- **Stop level (fixed at entry, never trailed)**: `L1` for longs, `H1` for shorts.
- **Sanity skip (LOCKED)**: if the entry print is already at or through the stop
  (long: `O2 ≤ L1`; short: `O2 ≥ H1`), skip the day — never enter a position that is
  born stopped out.
- **Stop distance** `D = |entry fill − stop level|` (bar-1 range plus any adverse
  bar-1-close→bar-2-open drift). Used for sizing and all R accounting.

### Exit (time — the primary exit, LOCKED baseline)

- Forced flat via **market order at the open of the session's final 5-minute bar**
  (15:55 ET on full days; close −5 min on early closes). No profit target in the
  scored baseline.
- **Why EoD-only and not the paper's 10R target**: (a) a 10R target on QQQ is ~3–5% of
  price intraday — it essentially never fills, so the paper's variant already behaves
  as ride-to-close on all but a handful of days; (b) EoD-only has **zero additional
  parameters** to defend; (c) it removes the intrabar target-vs-stop ordering
  ambiguity entirely. The **10R-target variant is pre-registered as a diagnostic-only
  column** in the pregate output (worst-case ordering: stop before target when both
  are in range of the same bar). It is never the scored baseline and never the verdict
  number.

### Exit (stop) — exact intrabar semantics (LOCKED)

The core engine currently supports only next-open/next-close fills; intrabar stops are
the required extension (see Implementation scope). Semantics two implementations must
agree on:

- The stop is live from the entry bar (bar 2) onward, **including bar 2 itself**.
- **Touch**: first bar with `Low ≤ stop` (long) / `High ≥ stop` (short) → fill at the
  **stop price** minus (long) / plus (short) stop slippage.
- **Gap-through**: if that bar *opens* beyond the stop (long: `Open < stop`), fill at
  the **bar open** (never the stop price) with stop slippage — gap-throughs fill where
  the market is, not where we wished.
- **Worst-case ordering (LOCKED)**: whenever a bar's range spans both the stop and any
  better outcome (the diagnostic 10R target, or the EoD bar itself), assume the stop
  fills first and take the full loss. Optimistic intrabar path assumptions are how
  breakout backtests lie.
- Live: a broker-side stop order rests from the moment of the entry fill.

### Session rules

- One entry evaluation per day (09:35), one position maximum, no re-entry after a
  stop-out, no pyramiding, no scaling.
- Early-close days trade normally with the forced-flat time shifted (12:55 ET).
- Expected activity: ~250 trading days/yr minus doji/zero-range/sanity skips →
  **~240–248 trades/yr**, roughly balanced long/short.

### Implementation scope (gated behind the pregate)

Backtesting this strategy requires a **core extension: intrabar stop-order fills** in
`core/backtest` (touch/gap-through/worst-case semantics exactly as above), plus
broker-side stop handling in `core/execution`. This is real engine work and is
**explicitly gated behind a pregate PASS** — if the gross follow-through isn't there in
the raw data, no engine code gets written (the rsi-5050 pattern: 3 hours, not 3 weeks).

## Risk

- **Baseline risk unit: `R = 0.5%` of equity per trade** (house standard), stop-distance
  sizing: `shares = floor( min( (R · equity) / D, equity / price ) )` — **no leverage,
  notional capped at 100% of equity.**
- **Honest consequence of the cap (LOCKED framing):** the typical stop distance `D` is
  ~30–50 bps of price (first-bar range), so risking 0.5% of equity wants **1.0–1.7×
  equity in notional — the no-leverage cap binds on most trades**, truncating realized
  per-trade risk to ~0.3–0.5% of equity (i.e., realized R < 0.5% whenever `D` < 50
  bps). This is exactly where the paper's 4x leverage lived. Accepted; the
  **realized-R distribution is mandatory reporting**, and all R-multiples in this spec
  refer to realized risk. No leverage will be added to rescue a thin result.
- **Max concurrent positions**: 1 (single instrument, one direction, one trade/day).
- **Per-trade stop**: the intrabar stop above; broker-side from the moment of fill.
  If computed `shares = 0`, skip the day.
- **Daily loss limit**: **2R** anchored at the prior session's closing equity, per the
  house core `RiskManager.on_bar()` (fixed 2026-07-04). With one trade/day risking
  ≤1R, this backstop binds only on gap-through overshoot — kept anyway as the house
  invariant.
- **Max drawdown kill switch: 10%** peak-to-trough equity (tighter than the house 15%
  because an intraday flat-by-close book has no overnight-gap excuse; same rationale
  as rsi-5050; flagged for sign-off). Note: at a ~25–35% hit rate, 10–15 consecutive
  stop-outs are a *normal* annual event (~0.7^15 × 245 ≈ 1/yr), costing ~4–6% of
  equity at realized-R sizing — the kill switch is set above normal-streak territory
  by design, and hitting it means the strategy is outside its own expected behavior.
- **PDT flag (live only)**: ~245 day trades/yr requires a ≥$25k margin account under
  FINRA PDT rules. Paper unaffected. Recorded now.
- **Reporting (LOCKED)**: per-trade P&L in bps and realized R; hit rate; exit-type
  split (stop / EoD); **long vs short split**; per-year means (decay visibility);
  stop-distance and realized-R distributions; worst trade in R; max consecutive
  losses; daily-return correlation vs the overnight-long book.

## Data requirements

- **Data types**: RTH 5-minute OHLCV bars for QQQ; exchange calendar with early
  closes. No quotes, news, or fundamentals for signals.
- **Source**: Alpaca historical SIP bars, already on hand —
  `data/QQQ_5m_adj.parquet` (2017-06 → 2024) and `data/QQQ_5m_adj_wf.parquet`
  (2024 → 2026-07). The seam between the two files must be deduplicated and the
  overlap cross-checked at pregate time (recorded in the run's notes).
- **Adjustment — stated per the 2026-07-05 house finding.** Alpaca's `adjustment=all`
  has known dividend bugs (the QQQ 2022-09-19 dividend is double-applied; SPY
  2016/2018 events missing). **For this strategy that is immaterial by construction:**
  a dividend back-adjustment is a constant multiplicative factor on all prices before
  an ex-date, and factors change only at session boundaries — so every within-session
  quantity this strategy uses (bar-1 direction sign, bps returns, relative stop
  distance, R-multiples) is **invariant to the adjustment**, wrong or right. No
  position ever spans an ex-date (or any overnight). The adjusted files are therefore
  acceptable as-is; raw prints would be equally valid; no splice or dividend audit is
  required. Ex-div dates are still tagged in reporting for hygiene.
- **History depth**: no indicator warm-up needed (the signal is one bar). Windows per
  Success criteria: 2018-01 → 2026-07 used; 2017-06–12 left unused for a clean
  calendar start.
- **Live/paper path**: Alpaca Algo Trader Plus (real-time SIP, subscribed 2026-07-05)
  — the 09:35:00 signal computation and market order are feasible with consolidated
  data; the intrabar stop rests broker-side. No IEX-feed fidelity caveat applies.
- **Reproducibility**: every run records vendor, feed, symbol, bar size, adjustment,
  data range, file hashes, seed, git commit (house rule 5).

## Cost assumptions

Costs are mandatory (house rule 3), modeled in `core/backtest/costs.py`. QQQ is the
second-most-liquid US ETF (~1-cent spread on a ~$500+ price ≈ 0.2 bps full spread) —
the DIA/SPY cost templates would be miscalibrated by ~10x here, so the numbers are
QQQ-specific but still deliberately above observed frictions:

- **Commission**: $0/share (Alpaca). (Paper assumed $0.0005/share with **zero spread
  and zero slippage** — strictly lighter than this model despite the commission.)
- **Half-spread**: **0.1 bps/side** (~0.6 cents on $560 — approximately the observed
  half-penny; the conservatism lives in the slippage terms and the rounded-up bar
  below, not here).
- **Slippage**: **0.4 bps/side** on market fills (09:35 entry, EoD exit);
  **1.0 bps** on stop fills (stops fill on adverse momentum by construction).
- **Round trips**: EoD exit ≈ **1.0 bps**; stop exit ≈ **1.6 bps**; at an expected
  ~65–75% stop-exit rate, weighted ≈ **1.4 bps**.
- **LOCKED cost bar for the pregate: 2.0 bps round trip** (conservative rounding above
  the weighted model). **Cost-sensitivity gate**: the OOS backtest result must remain
  net-positive at **1.5× modeled costs** (3.0 bps).

**The arithmetic the result must be judged against (LOCKED framing):** the published
effect size is ~0.1–0.2R gross per trade; at `D` ≈ 30–50 bps that is **~3.5–4.5 bps of
notional per trade gross**. Minus ~1.4 bps costs → ~2–3 bps net × ~245 trades/yr at
≤1x notional → **~+5–7%/yr net**, with daily P&L vol ~0.4% → **net zero-filled Sharpe
roughly 0.8–1.1 — only if our data reproduces the full published effect size.** There
is no headroom for a half-strength effect: at 50% of published size the strategy nets
~1 bp/trade and fails. Annual cost drag at 245 trades ≈ 3.4% of equity — the gross
edge must be real, not rounding error.

## Success criteria (locked before first backtest)

Proposed bars — **must be signed off by the user, then immovable.** Every parameter in
this spec (5-min range, direction rule, stop placement, EoD exit, R = 0.5%, windows)
is pre-registered; **nothing is ever swept**, so there is nothing to re-tune between
IS and OOS.

### PREGATE — pre-scoring gross-edge diagnostic (run FIRST, outside the engine)

Following the rsi-5050 pattern (`scripts/pregate_rsi5050.py`,
`experiments/rsi-5050/2026-07-05-pregate/`), a standalone script
(`scripts/pregate_orb.py`) runs on `data/QQQ_5m_adj.parquet`, **IS window only
(2018-01-01 → 2022-12-31); the OOS and WF windows stay unread.**

Per session in the IS window: identify bar 1 (09:30–09:35 ET); apply the doji /
zero-range / sanity skips; direction = sign(C1 − O1); entry = `O2`; stop = `L1`/`H1`;
scan bars 2 → last with the **exact locked stop semantics** (touch → stop price;
gap-through → bar open; stop live on bar 2); otherwise exit at the final bar's open.
Record the signed gross return in bps of entry price per trade.

**Gate rule (LOCKED before the script is written):**

- **REJECT at spec validation if the IS mean gross return per trade ≤ 2.0 bps** (the
  locked round-trip cost bar), **or if it does not exceed the unconditional long
  QQQ open→close (O2 → final-bar-open) mean over the same sessions** — a "breakout"
  signal that loses to just being long QQQ every day intraday is a beta artifact plus
  noise. Sign/threshold rules are binding; the t-stat is reported for honesty about
  "~0" but does not move the gate (spx-swing convention).
- Declared **diagnostic-only** columns (never gate, never verdict): the 10R-target
  variant; per-year means (2018…2022); long/short split; hit rate; stop-distance and
  realized-R distributions; time-to-stop distribution. A pass driven entirely by one
  side or one year is recorded and carried into the OOS judgment.
- On PASS: the core intrabar-stop extension is built, then the engine backtest runs
  IS → OOS. On FAIL: reject, no tuning, no duration/instrument shopping, post-mortem
  in this file.

### Backtest bars (engine, net of locked costs)

- **Minimum OOS net Sharpe: ≥ 1.0 annualized, zero-filled convention** (flat days
  count 0 — house headline convention; with ~245 trades/yr zero-filled ≈ trade-days
  here). Held above the house 0.7 because an intraday, flat-by-close, high-frequency
  book has no overnight-risk excuse, plenty of statistical power, and real
  operational load.
- **Benchmark gate**: OOS net zero-filled Sharpe must **beat QQQ buy-and-hold net
  Sharpe over the identical OOS window**. Acknowledged as strict for a beta≈0
  long/short book in a bull OOS window — locked anyway: capital and attention are
  finite, and the paper's own claim is outperformance, not participation.
- **Net-positive expectancy** per trade after costs; **net-positive at 1.5× costs**.
- **Both-sides gate**: net expectancy > 0 on longs *and* shorts separately in OOS
  (a one-sided result is beta, not breakout).
- **Maximum OOS drawdown: ≤ 10%** peak-to-trough (consistent with the kill switch).
- **Worst single trade: ≤ 2.0·R realized** (a breach means gap-through overshoot is
  under-provisioned even if Sharpe passes).
- **Minimum OOS trade count: ≥ 400 filled trades.** Arithmetic: ~250 trading days/yr,
  ~97% of days directional → ~245 signals/yr → the 2-year OOS window should produce
  ~490; below 400 means data gaps or skip-rule bugs, and the verdict is
  **inconclusive-reject** regardless of Sharpe.
- **IS→OOS decay guard**: OOS net Sharpe not more than 50% below IS net Sharpe
  (worse = the 2016–2023-style regime carried the IS result; the published-then-gone
  pattern that killed spx-swing).

### Windows (pre-registered)

- **In-sample: 2018-01-01 → 2022-12-31** (5 yrs, ~1,230 trades; contains the vol-rich
  regimes the paper's result lives on).
- **Out-of-sample: 2023-01-01 → 2024-12-31** (2 yrs, ~490 trades; almost entirely
  **post-publication** of the April 2023 paper — the honest test).
- **Walk-forward: 2025-01-01 → present, unread until the OOS verdict.** Walk-forward
  numbers are the ones that count for any paper decision.
- **What "working" looks like (declared now so the drawdown doesn't get reinterpreted
  later):** hit rate ~25–35%, most trades small losses at −1R realized, P&L carried by
  a right tail of trend days; 10–15-loss streaks and 4–6% drawdowns are *normal
  operation*, not failure — failure is defined by the locked bars above, nothing else.

## Known failure modes

Regimes where this should lose, and what limits the damage:

- **Chop / range days (the signature failure).** The opening move reverses; the stop
  is hit by lunch. At a ~30% hit rate this is the *majority outcome by design* — the
  strategy is short mean-reversion, structurally. *Bounding:* realized-R sizing, one
  trade/day, the 2R daily backstop, exit-type reporting.
- **Low-volatility regimes (the likely quiet failure).** Quiet tape ⇒ small first
  bars ⇒ tiny stop distances ⇒ noise stops the trade before any trend develops, and
  the cost share per R rises. No minimum-range filter is added (that would be a new
  parameter); the per-year and stop-distance-bucket reporting exposes it instead.
- **Regime dependence of the published sample.** 2016–2023 contains 2018 Q4, 2020,
  and 2022 — an unusually trend-day-rich sample. If the edge is a vol-regime artifact,
  the IS (2018–2022) will pass and the OOS (2023–2024, calmer + post-publication)
  will fail — exactly what the decay guard and post-publication OOS are for.
- **Post-publication crowding/arbitrage.** The paper is famous. Any surviving edge
  must show up in 2023+ data; the OOS/WF placement makes that the binding test rather
  than an afterthought.
- **Morning news reversals (10:00 ET data, FOMC 14:00).** Scheduled releases reverse
  the opening direction violently; stop slippage is worst exactly then. *Bounding:*
  gap-through fills at the bar open (never the stop price), 1.0 bps stop slippage,
  worst-case intrabar ordering. No event filter in v1; event days tagged in reporting.
- **Gap-through overshoot past 1R.** A 5-min bar can open well beyond the stop
  (halts, LULD, news bursts). Accepted, measured (worst-trade ≤ 2.0R criterion), not
  hidden.
- **Loss-streak psychology → kill-switch interaction.** Normal operation includes
  double-digit consecutive losses; the 10% kill switch sits above normal-streak
  drawdown (~4–6%) but a bad quarter can plausibly reach it. If it trips, the
  strategy halts for manual review — it is not restarted because "streaks are
  normal"; the review decides against the locked criteria.
- **Fill divergence at 09:35 (paper phase).** Live market-order fills seconds after
  09:35:00 vs the backtest's 09:35 open print, and broker stop triggers vs bar-based
  backtest stops, are the two assumptions paper trading must verify (weekly
  fill-vs-assumption comparison per workflow gate 6; tolerance to be set in the paper
  plan if this ever gets there).

## Decisions record — user sign-off 2026-07-05 (criteria frozen from here)

All six open baselines were signed off before the pregate ran; every value below is
now immovable:

1. **Baseline exit — CONFIRMED: EoD-only**; the 10R target is diagnostic-only and can
   never become the verdict number.
2. **Cost bar — CONFIRMED: 2.0 bps round trip** for the pregate; OOS backtest must
   remain net-positive at **1.5× costs (3.0 bps)**. Not renegotiable after the pregate
   prints.
3. **Windows — CONFIRMED: IS 2018-01-01 → 2022-12-31 / OOS 2023-01-01 → 2024-12-31 /
   WF 2025-01→ (unread until the OOS verdict).** OOS and WF are almost entirely
   post-publication of the April 2023 paper — deliberately the binding test.
4. **Success bars — CONFIRMED strict: OOS net zero-filled Sharpe ≥ 1.0** plus the
   beat-QQQ-buy-and-hold benchmark gate (user chose strict over the house 0.7).
5. **Kill switch and OOS DD bar — CONFIRMED: 10%** (tighter than house 15%; an
   intraday flat-by-close book has no overnight-gap excuse).
6. **Sizing — CONFIRMED: R = 0.5% of equity, stop-distance sized, no leverage,
   notional capped at 100% of equity**, realized-R truncation accepted and reported;
   leverage will not be introduced later to rescue a thin pass.
