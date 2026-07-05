# Strategy: rsi-5050

- **Status**: retired — REJECTED at spec validation 2026-07-05 by the pre-registered
  gross-edge gate (5-min: +0.30 bps mean gross vs 3.5 bps cost bar, n=767, t=0.64;
  15-min variant: −2.86 bps, n=28; see `experiments/rsi-5050/2026-07-05-pregate/`).
  Approved by user 2026-07-05; rejected the same day, before any engine implementation.
- **Created**: 2026-07-04
- **One-liner**: Intraday momentum on the Dow (via DIA): RSI(21) crossing the 50 line flags a directional regime shift; enter on a breakout of the signal bar, stop beyond its opposite extreme, exit when RSI crosses back — traded only when ATR(5) shows enough volatility.

> **Provenance.** This formalizes the USER'S OWN discretionary method, traded manually
> on Dow Jones charts: RSI period 21 with overbought/oversold both set to 50 (only the
> midline matters), breakout entry 1 point beyond the signal bar's extreme, stop 1 point
> beyond its opposite extreme, exit on RSI recross, ATR(5) 20–30 Dow points as the
> tradeable-volatility band, both directions, multiple trades per day. The spec's job is
> to make those rules mechanical and testable — not to replace them. Where a rule cannot
> survive translation to a tradeable instrument literally (the 1-point buffer, the fixed
> point band), the translation preserves the *intent* and the original is kept as the
> anchor. **Known caveat of mechanization:** the discretionary version may embed trade
> selection the rules don't capture (skipping "obviously bad" setups, timing the entry).
> If the mechanical version underperforms the remembered experience, that gap is a
> finding about the discretionary overlay, not an implementation bug.

## Hypothesis

**Effect.** After the intraday trend regime flips — RSI(21) crossing its 50 midline,
which is algebraically close to "price crossing a ~21-bar smoothed trend of itself" —
price continues in the new direction for long enough to pay a breakout entry, *provided
volatility is elevated* (the ATR(5) band). The breakout-beyond-the-signal-bar entry is a
confirmation filter: the market must actually follow through before capital is committed,
so pure oscillation around the midline never fills.

**Mechanism — who is on the other side?** The honest answer: no structural, mandate-driven
counterparty is identified (unlike the leveraged-ETF-rebalance flow behind
intraday-momentum or the gap-risk premium behind overnight-long). The candidate losers are
(a) mean-reversion traders fading a genuine regime flip too early, and (b) slow-reacting
participants and VWAP/TWAP parent-order flow that keeps pushing in the new direction after
the flip (order-flow persistence). Both are plausible only in **elevated-volatility,
directional sessions** — which is exactly what the user's ATR(5) band is for. The band is
the load-bearing component of the hypothesis, not a tweak.

**Adversarial notes — read before falling in love:**

1. **The in-house prior is negative.** The retired `intraday-momentum` sibling tested a
   different formulation of intraday index momentum (morning→afternoon, SPY, 2018–2024,
   real SIP data) and found the effect **absent — negative even gross of costs**
   (corr ≈ −0.035, ~50% hit rate). This spec's formulation differs (bar-scale
   trend-following with a vol gate, any time of day, both directions, Dow vehicle), so it
   is a separate hypothesis — but the closest evidence we own points *against* generic
   intraday index momentum.
2. **The academic prior is negative at this horizon.** Time-series momentum is documented
   at daily-to-monthly horizons. At minutes-scale, liquid index ETF returns post-2010 are
   approximately unpredictable to slightly *mean-reverting* net of costs. An RSI midline
   cross is one of the most widely known and heavily mined signal classes in existence;
   any easy edge in it on an index ETF is long arbitraged.
3. **Costs, not signal quality, are the most likely killer.** At 5-minute scale the stop
   distance is a few bps while the round-trip cost is ~3–4 bps — every trade starts
   roughly half to one full risk-unit in the hole (arithmetic in Cost assumptions). The
   gross edge per trade required to clear the bar is large for a breakout system.
4. **Base-rate expectation is a reject.** A pre-gating gross-edge diagnostic (Success
   criteria) is computed FIRST; if the raw post-cross continuation has no gross edge in
   the IS window, the honest outcome is reject-at-spec-validation, exactly as the two
   retired siblings were rejected — not a tuning campaign on the band edges.

## Universe & timeframe

- **Instrument: DIA** (SPDR Dow Jones Industrial Average ETF Trust). "The Dow" is not
  directly tradeable on Alpaca (no futures, no cash index); DIA is the natural vehicle
  (NAV ≈ DJIA / 100, so **1 Dow point ≈ $0.01 on DIA — one tick**). Caveats, flagged:
  - DIA is materially less liquid than SPY/QQQ (ADV ~3–4M shares) but still penny-to-
    few-penny spreads in RTH — adequate for one small book, modeled in costs.
  - The user's charts were the **index**, whose prints are a calculation, not trades:
    smoother, spreadless, and slightly different bar highs/lows than DIA. Signals on DIA
    bars will not exactly match the remembered index charts. Accepted and flagged.
  - The ≈/100 divisor drifts slowly (fees, tracking); all point translations below are
    anchored at **Dow ≈ 44,000 / DIA ≈ $440 (mid-2026)** and expressed scale-invariantly
    in bps so the drift doesn't matter.
- **Bar size / data resolution**: **5-minute bars (DECIDED by user, 2026-07-05).**
  Rationale: RSI(21) on 5-min = ~105 min of
  lookback (a meaningful intraday regime, not noise); midline crosses arrive ~2–5 per
  session unfiltered, matching the stated goal of multiple trades/day; 1-min bars give
  ~21 min lookback and cost-suicidal churn; 15-min bars give ~1 signal/day — below the
  user's stated frequency goal, but ~3× better cost-to-stop-distance ratio (see Cost
  assumptions). A **15-minute variant is pre-registered as a co-equal diagnostic run**
  (declared now so it cannot be introduced post hoc as an escape hatch).
- **Trading session (hours, timezone)**: US regular session, 09:30–16:00 ET; all
  timestamps ET; RTH bars only (no pre/post-market bars for signals or fills).
  78 five-min bars per full session. Calendar-aware early closes (13:00 ET) — the
  phantom-half-day-bar lesson from overnight-long applies.
- **Holding period**: **Intraday only, flat by close, no exceptions.** A tight-stop
  breakout system must not hold an un-stoppable overnight gap; this also keeps it cleanly
  differentiated from overnight-long (which owns the overnight session on this book).

## Signals

**No lookahead.** All indicators are computed on **completed bars only**. A signal
confirmed at the close of bar *t* can act no earlier than bar *t+1*. Stop-entry and
stop-loss orders trigger intrabar on later bars (that is what stop orders are); the
*decision* to place them uses only completed-bar data. Any code path reading bar *t*'s
close to trade within bar *t* is a lookahead bug.

### Indicator definitions (exact)

- **RSI(21), Wilder.** On bar closes `C_t`:
  `U_t = max(C_t − C_{t−1}, 0)`, `D_t = max(C_{t−1} − C_t, 0)`.
  Seed after the first 21 deltas: `avgU = mean(U_1..U_21)`, `avgD = mean(D_1..D_21)`.
  Then Wilder smoothing: `avgU_t = (20·avgU_{t−1} + U_t)/21` (same for D).
  `RSI_t = 100 − 100/(1 + avgU_t/avgD_t)` (if `avgD_t = 0`, RSI = 100).
- **ATR(5), Wilder.** `TR_t = max(H_t−L_t, |H_t−C_{t−1}|, |L_t−C_{t−1}|)`; seed = mean of
  first 5 TRs; then `ATR_t = (4·ATR_{t−1} + TR_t)/5`. Expressed in bps of price:
  `ATR5_bps(t) = 10^4 · ATR_t / C_t`.
- **Warm-up**: no signals until ≥ 250 completed bars exist (≈ 3.2 sessions at 5-min), so
  Wilder smoothing has converged. Data fetch must start ≥ 1 week before the first
  tradeable day.
- **Session-boundary convention (baseline, flagged as open)**: indicators run
  **continuously across days on RTH bars — no daily reset** (a reset would blind the
  strategy for ~2h every morning during re-warm-up). One asymmetric adjustment: for the
  **first bar of each session, `TR = H − L`** (ignore prior close), so the overnight gap
  — which is not tradeable intraday range — does not inflate the ATR band for the first
  ~25 minutes. RSI keeps the gap return (a gap *is* regime information).

### Point translation (LOCKED intent, anchored numbers)

The user's rules are in Dow points; on DIA, 1 point ≈ $0.01 ≈ 0.23 bps — smaller than the
spread, so literal translation is meaningless. Scale-invariant equivalents, anchored to
the user's numbers at Dow ≈ 44,000:

- **Entry/stop buffer** (user: "1 point beyond the signal bar extreme"): 1 point is 4% of
  the user's ATR band midpoint (25 points). Rule:
  `buffer = max(0.04 · ATR5, 2 ticks = $0.02)`.
  The floor guarantees the confirmation buffer always clears the quoted spread — the
  user's intent (a real breakout beyond the extreme, not a tick of noise) preserved on
  the actual instrument.
- **Volatility band** (user: "ATR(5) between 20 and 30 points"): 20–30 points at Dow
  44,000 = **4.5–6.8 bps of price**. Tradeable regime: `4.5 ≤ ATR5_bps ≤ 6.8`.
  **Flag:** a fixed point band is level-dependent — at Dow 30,000 the same 20–30 points
  would be 6.7–10 bps, a different vol regime entirely. The bps band preserves what the
  user's eye actually calibrated (a *fraction* of price movement) across index levels.
  **Also flagged:** (a) the band was eyeballed at an unknown bar size and an unknown
  index level/era (user confirmed 2026-07-05 they don't recall when it was calibrated) —
  the 4.5–6.8 bps conversion anchors it at Dow ≈ 44,000 and at the decided 5-min bar
  size, and is therefore an ASSUMPTION about what the user's eye saw, not a record of
  it; if the pre-gating diagnostic shows the band selecting nothing sensible, the band
  anchor — not the strategy — is the first suspect; (b) intraday
  vol is strongly U-shaped, so a fixed band will systematically pass the open/close and
  block midday — possibly the intent (midday chop is the enemy), but reporting must
  bucket signals by time of day so we can see what the band is really selecting; (c) the
  *upper* bound excludes the highest-vol regimes, where momentum continuation is often
  strongest — kept, because it is the user's rule, but its cost is reported.

### Entry (symmetric long/short; long described, short is the exact mirror)

1. **Cross**: at the close of completed bar *s*, `RSI_{s−1} ≤ 50` and `RSI_s > 50`
   (cross **above**; cross-below is `RSI_{s−1} ≥ 50` and `RSI_s < 50` — the equality
   conventions make simultaneous double-signals impossible). Bar *s* is the **signal
   bar**.
2. **Gates at signal-bar close** (all must pass, else no order):
   `4.5 ≤ ATR5_bps(s) ≤ 6.8`; current time within the entry window (below); no daily
   halt active (Risk).
3. **Arm**: place a **buy-stop at `High(s) + buffer`**, working from bar *s+1* onward.
   Simultaneously fix the initial protective stop level at **`Low(s) − buffer`**
   (activated on fill).
4. **Pending-order validity — cancel the stop-entry when the first of these occurs**
   (baseline, flagged):
   a. RSI closes back across 50 in the adverse direction on a completed bar (signal
      invalidated — this recross is itself a new opposite-side signal bar, see
      stop-and-reverse below);
   b. **10 bars** elapse after the signal bar without a fill (stale breakout);
   c. the entry cutoff time is reached (Session rules).
5. **Fill model (backtest, OHLC bars)**: the order fills on the first bar with
   `High ≥ trigger`; fill price = `max(Open, trigger)` + slippage (gap-through opens fill
   at the open, not the trigger). **Worst-case intrabar convention (LOCKED):** if the
   fill bar's range also crosses the protective stop, assume entry first, then stopped
   out in the same bar — the full loss is taken. Optimistic path assumptions are how
   breakout backtests lie.
6. **One position at a time**, long or short, never both; no pyramiding. **Re-entry after
   a stop-out requires a brand-new cross** — after a long stop-out with RSI still above
   50, the strategy stays flat until RSI dips below and crosses above again.

### Exit

- **Exit (signal — the primary exit)**: RSI closes across 50 in the adverse direction on
  a completed bar → **exit at the next bar's open via market order**. (Exit on the close
  of the recross bar itself would require acting on the bar being formed — lookahead.)
- **Stop-and-reverse structure**: the adverse-recross bar is simultaneously the signal
  bar for the opposite direction. The exit executes at next-bar open; a new opposite-side
  stop-entry is armed off that same bar's extreme **iff** the ATR band and session gates
  pass. The position itself never flips intrabar.
- **Exit (stop)**: resting stop-loss at `Low(s) − buffer` (long), fixed at entry — not
  trailed. Backtest fill: first bar with `Low ≤ stop`; fill = `min(Open, stop)` −
  stop-slippage.
- **Exit (volatility collapse — the user's "stand aside on weak momentum", baseline
  flagged)**: if `ATR5_bps` closes **below 4.5 on 3 consecutive completed bars** while in
  a position, exit at next bar open. The 3-bar persistence requirement prevents
  single-bar churn at the band edge. (Variant with no vol-exit is Open question #3.)
- **Exit (time)**: forced flat at **15:55 ET** — market order at the open of the
  15:55→16:00 bar. Positions never touch the closing auction and never hold overnight.

### Session rules

- **Entry window**: no signal bars taken and no fills accepted before **09:45 ET** (the
  first three 5-min bars are auction noise, gap-digestion, and the thinnest data); no new
  stop-entry orders armed after **15:30 ET**; all pending entries cancelled at 15:30.
- **Early-close days** (13:00 ET close): entry cutoff = close − 30 min (12:30), forced
  flat at close − 5 min (12:55). All times derived from the exchange calendar, never
  hardcoded.
- Expected activity at 5-min bars: ~2–5 raw crosses/session; after the ATR band, session
  window, and one-position constraint, ~1–3 armed signals/day with a sub-100% fill rate →
  order of **250–500 filled round trips/year**. This satisfies the user's frequency goal
  and is the number the cost drag is computed at.

## Risk

- **Position sizing**: risk-per-trade rule, delegated to `core/risk`. Per-trade risk
  distance = `entry trigger − stop level` = signal-bar range + 2·buffer.
  `shares = floor( min( (R · equity) / risk_distance, equity / price ) )` with house
  baseline `R = 0.5%` and **no leverage** (notional ≤ equity).
  **Honest consequence, flagged:** at 5-min scale the risk distance is ~4–8 bps of
  price, so the R = 0.5% target would demand ~6–12× leverage — the notional cap binds on
  essentially every trade, and the **realized risk per trade is ~4–8 bps of equity**, not
  0.5%. This is fine (small, frequent bets) but means per-trade R and the R-multiples
  below refer to the *realized* per-trade risk, not 0.5%.
- **Max concurrent positions**: 1 (single instrument, one direction at a time).
- **Per-trade stop**: the resting stop-loss above — every position has a broker-side stop
  from the moment of fill. If computed `shares = 0`, skip the trade.
- **Daily loss limit (baseline, flagged)**: no new entries for the rest of the day after
  the first of: **3 full-stop losses** (≈ 3R realized), or **day realized P&L ≤ −0.5% of
  equity** (absolute backstop). Open positions still exit by their normal rules.
- **Max drawdown kill switch**: halt the strategy and require manual review at **10%**
  peak-to-trough equity drawdown (tighter than the house 15% because an intraday
  flat-by-close book has no gap excuse for deep drawdowns; flagged for sign-off).
- **PDT flag (live only, not paper)**: this strategy day-trades many times per week;
  live trading requires a ≥ $25k margin account under FINRA pattern-day-trader rules.
  Paper is unaffected. Recorded now so it isn't a surprise at promotion time.
- **Reporting**: P&L, hit rate, and expectancy bucketed by **side (long/short)**,
  **time of day** (open/midday/close — to expose what the ATR band actually selects),
  **exit type** (recross / stop / vol-collapse / time), and **ATR regime**.

## Data requirements

- **Data types**: RTH OHLCV bars for DIA at the chosen bar size (5-min baseline, 15-min
  for the pre-registered variant), plus daily bars for reporting; exchange calendar with
  early closes. No quotes/news/fundamentals needed for signals.
- **Adjustment**: **unadjusted prices** — the book is intraday flat-by-close, so ex-div
  overnight drops never touch P&L; unadjusted bars match what would actually have been
  traded intrabar. DIA goes ex-div monthly (~15 bps); those overnight gaps flow through
  the continuous RSI once a month — negligible at a 21-bar horizon, and ex-div mornings
  are tagged in reporting.
- **History depth**: warm-up (≥ 1 week) + IS 2018–2021 + OOS 2022–2024 + walk-forward
  2025→. **DIA intraday data is NOT on hand** (`data/` has SPY/QQQ only) — a DIA fetch is
  a prerequisite for backtest #1. **Assumption, flagged:** Alpaca historical SIP minute
  bars are assumed to cover DIA from ≥ 2018 (they did for SPY/QQQ); the actual first
  available date must be verified at fetch time and recorded. **Do not assume anything
  pre-2016 exists**; if DIA minute history starts later than 2018, the IS window shrinks
  and the trade-count bar below still applies.
- **Source — split by stage, stated honestly (this section is a viability gate):**
  - **Backtest: Alpaca historical SIP bars** (free tier serves historical SIP at a
    15-minute delay — fine for backtests), exported to parquet via the existing fetch
    path, loaded through `core/data`. Backtest bars are consolidated-tape truth.
  - **Paper / live: the free-tier real-time feed is IEX-only (~2–3% of consolidated
    volume — ADR 0003), and for THIS strategy that is not a cosmetic problem.** Unlike
    overnight-long (whose gate uses yesterday's completed close, so IEX real-time is
    harmless), rsi-5050 computes RSI/ATR on live intraday bars and triggers stop orders
    intrabar. On thin IEX prints for a mid-liquidity ETF like DIA: bar OHLC (especially
    highs/lows) will diverge from SIP bars → **different signal bars than the backtest**;
    stop-entry/stop-loss triggers keyed to IEX trades fire late, early, or not at all;
    Alpaca's paper simulator fills off the same feed, so paper fills are doubly
    synthetic. The 15-minute-delayed SIP feed is useless for intrabar triggers.
    **Verdict as originally drafted: backtest-viable but not signal-faithful in paper
    on the free tier. RESOLVED — the user subscribed to Alpaca Algo Trader Plus on
    2026-07-05** ($99/mo — full real-time SIP via CTA+UTP, 10k API calls/min), so
    real-time SIP is available for any future paper phase and the IEX-fidelity blocker
    no longer applies. No mechanics-only IEX paper phase will be used as evidence.
- **Reproducibility**: every experiment records vendor, feed, symbol, bar size,
  adjustment, data range, seed, and git commit.

## Cost assumptions

Costs are mandatory on every run (`core/backtest/costs.py`). Baseline for **DIA on
Alpaca** — modeled slightly heavier than SPY because DIA is less liquid:

- **Commission**: $0/share (Alpaca).
- **Half-spread**: **0.5 bps/side** (DIA quotes ~1–3 cents on ~$440; 0.5 bps ≈ 2.2 cents —
  deliberately at the wide end).
- **Slippage**: **1.0 bps** on stop-entry fills and market exits (recross / vol / time);
  **2.0 bps** on stop-loss fills (stops fill on adverse momentum by construction).
- **Round trip ≈ 3.0–4.0 bps** depending on exit type.

**The arithmetic that will probably kill this strategy — stated up front (LOCKED as the
framing; a result must be judged against it):**

- Typical risk distance at 5-min bars, mid-band (ATR5 ≈ 5.5 bps): signal-bar range
  ~4–7 bps + 2 buffers ~0.5 bps → **stop distance ≈ 4.5–7.5 bps**.
- Round-trip cost 3–4 bps is therefore **≈ 0.5–0.9× the per-trade risk unit**: every
  trade starts roughly half an R in the hole, before edge.
- At ~500 round trips/year with notional ≈ equity (the no-leverage cap binds), annual
  cost drag ≈ 500 × 3.5 bps ≈ **17–18% of equity per year**. The strategy must generate
  ~3.5 bps of *gross* edge per trade — ~0.5–0.8 R — just to break even; a clearly
  positive net result needs a per-trade gross edge that would be exceptional for any
  breakout system at this horizon.
- The pre-registered **15-min variant** exists precisely because the same rules at 15-min
  triple the stop distance while costs stay fixed (cost ≈ 0.15–0.3× R) at the price of
  ~1 trade/day. If the 5-min edge exists gross but drowns in costs while 15-min survives,
  that is a legitimate, pre-declared outcome — not post-hoc shopping.
- **Cost-sensitivity gate**: the OOS result must remain net-positive at **1.5× modeled
  costs** (see Success criteria). Given cost dominance, a result that dies at 1.5× is not
  robust enough to trade.

## Success criteria (locked before first backtest)

Proposed bars — **must be signed off by the user before backtest #1**, then immovable.
Applied identically to the 5-min baseline and the 15-min variant, judged separately.

- **Pre-gating gross-edge diagnostic (run FIRST, outside the engine)**: on IS data,
  compute the distribution of the raw continuation — from `signal-bar extreme + buffer`
  to the RSI-recross exit — for all band-passing crosses, gross of costs, both sides. If
  the mean gross continuation ≤ the modeled round-trip cost (~3.5 bps), there is no edge
  to trade and the strategy is **rejected at spec-validation** without tuning, exactly as
  intraday-momentum was.
- **Minimum OOS net Sharpe: ≥ 1.0 annualized** (2022–2024). Higher than the house 0.7
  because an intraday, flat-by-close, hundreds-of-trades strategy has no overnight-risk
  excuse and plenty of statistical power; anything below 1.0 net does not justify the
  operational load of intraday execution.
- **Maximum OOS drawdown: ≤ 10%** peak-to-trough (consistent with the kill switch).
- **Minimum OOS trade count: ≥ 500 filled round trips** over 2022–2024. At the expected
  1–2 fills/day this is comfortable; if the ATR band gates so hard that < 500 trades
  occur, the result is **inconclusive regardless of Sharpe** (and the band, not the
  Sharpe, is the finding).
- **Additional gates**: net-positive expectancy per trade after costs; edge present on
  **both long and short** sides (a one-sided result in 2018–2024 is a beta artifact, not
  the hypothesis); OOS Sharpe within ~50% of IS Sharpe (worse = overfit band/buffer);
  **net-positive OOS at 1.5× modeled costs**.
- **In-sample: 2018–2021. Out-of-sample: 2022–2024. Walk-forward: 2025→present** —
  walk-forward numbers are the ones that count for any paper decision. The only tunable
  parameters (bar size confirmed by user, band edges, buffer fraction, pending-order N)
  are tuned on IS only and frozen thereafter.

## Known failure modes

Regimes where this should lose, and what limits the damage:

- **Chop straddling the 50 line (the signature failure).** RSI(21) hovering at the
  midline generates alternating crosses; each breakout fills and promptly recrosses —
  a cost-paying whipsaw machine. *Mitigations that exist by design:* the ATR band (the
  user's own answer — chop is worst in low vol), the breakout buffer (pure oscillation
  without follow-through never fills), pending-order expiry, and the 3-stop daily halt.
  This will still be the dominant loss bucket; exit-type reporting will show it.
- **Cost dominance (the most likely overall failure).** Per the arithmetic above, costs
  ≈ 0.5–0.9× the risk unit at 5-min scale. Even a genuinely positive gross edge can net
  out negative. *Mitigation:* none within the rules — this is what the pre-gating
  diagnostic, the 1.5× cost gate, and the 15-min variant are for.
- **Band-edge flip-flop and the vol U-shape.** ATR5_bps oscillating around 4.5 (or 6.8)
  toggles eligibility; the intraday vol U-shape means the band systematically passes
  open/close and blocks midday. Not tuned around in v1 — time-of-day reporting exposes
  what the band actually does, and Open question #2 offers a relative-band alternative.
- **Upper-band exclusion of the best regimes.** The user's 30-point cap stands aside in
  panic/high-vol tape — precisely when breakouts run furthest (and also when slippage is
  worst). Kept because it is the user's rule; its opportunity cost is reported.
- **News spikes through the trigger.** CPI/FOMC bursts gap through the stop-entry and
  fill at the open of the burst bar, then often mean-revert; stop-loss slippage is worst
  here too. *Mitigation:* gap-through fills modeled at the open (not the trigger), 2 bps
  stop slippage, worst-case same-bar entry-then-stop convention. No event filter in v1;
  event days tagged in reporting.
- **Trend days without pullbacks.** A one-way day produces exactly one cross near the
  open; the strategy is in one position all day and the "multiple trades/day" premise
  fails — fine for P&L, but it means trade frequency is regime-dependent and the 500-
  trade bar must survive trend-heavy years.
- **Overnight gap contaminating the morning regime.** With continuous (no-reset)
  indicators, a large gap yanks RSI across 50 at 09:30 without any intraday trend behind
  it. *Mitigation:* no entries before 09:45; gap excluded from first-bar TR; the
  session-boundary convention is Open question #6 if this bucket bleeds.
- **IEX-fed paper divergence.** If promoted on the free tier, paper signals and fills
  will not match the backtest for feed reasons alone (see Data). *Mitigation:* the paper
  blocker is pre-declared; a mechanics-only paper phase carries zero evidentiary weight
  on fills.

## Decisions record (open questions resolved 2026-07-05)

1. **Bar size: 5-minute (user decision).** The user did not recall/confirm the original
   chart timeframe; 5-min was chosen going forward. 15-min remains pre-registered as a
   co-equal diagnostic.
2. **ATR band form: fixed bps band 4.5–6.8** (faithful conversion of 20–30 points at
   Dow ≈ 44,000). Calibration era unknown (user does not recall) — anchor flagged as an
   assumption in Point translation above.
3. **Volatility-collapse exit: exit after 3 consecutive closes below the band**
   (designer recommendation, accepted by user by default).
4. **Pending stop-entry lifetime: 10 bars** (accepted by default).
5. **Daily halt: 3 full-stop losses OR −0.5% equity day, whichever first** (accepted by
   default).
6. **Indicator session handling: continuous across days, overnight gap excluded from
   first-bar TR only** (accepted by default).
7. **Success bars: as specified above** — OOS net Sharpe ≥ 1.0, OOS DD ≤ 10%, ≥ 500 OOS
   trades, both-sides gate, 1.5× cost gate, kill switch 10%. Locked at approval;
   immovable once backtesting starts.
8. **Paper path: Alpaca Algo Trader Plus (real-time SIP).** User subscribed on
   2026-07-05 (ahead of the green-backtest gate — the account now has full real-time
   SIP). No mechanics-only IEX paper phase as evidence. Note: the paper gate itself
   (pre-registered criteria per workflow gate 6) is still required before promotion.
