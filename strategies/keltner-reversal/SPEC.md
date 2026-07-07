# Strategy: keltner-reversal

- **Status**: **REJECTED at spec validation (pregate) — 2026-07-07.** See the Verdict at
  the end of this file. Spec approved + criteria FROZEN 2026-07-07; the blocking data task
  (3-min DIA fetch + aggregation audit) was done; `scripts/pregate_keltner.py` ran on the
  IS window only. The setup is **gross-negative before costs** (IS mean −0.839 bps vs the
  2.5 bps bar) and loses to the matched trend-direction baseline by 2.7 bps. Robust to the
  intrabar ordering (optimistic ceiling −0.703 bps, still negative). No engine code
  written; OOS and WF windows never read; no-rescue clause binds.
- **Created**: 2026-07-07
- **One-liner**: On a 3-min Dow chart, fade a stab outside a Keltner band — wait for a reversal bar that closes back inside, enter on the break of that bar's extreme (+1/-1 tick), stop beyond the signal-bar extreme, target the channel midline (aggressive: the opposite band), order voided if unfilled within 3 bars.

> **Provenance — stated bluntly.** This is not a paper anomaly with a citation and a
> refereed sample. It is a **discretionary chart recipe dictated verbally by a trader**:
> "the Dow, 3-min, two Keltner channels EMA-13 Shift 1.3 and 2.0, check the higher
> timeframe for trend, wait for a bar that pokes outside the band and closes back in,
> buy the break of its high, target the middle line." The indicator dialog language
> ("Shift" as a band multiplier) is **MetaTrader 4/5**, i.e., the chart the idea was
> born on was almost certainly a **CFD or a Dow future running ~24h**, not an
> RTH-only US ETF. Every number in it (EMA 13, ATR period, two multipliers, the HTF
> choice, the trend rule, the tick offsets, the 3-bar expiry) is a **free parameter
> with no external validation**, and the pattern itself ("reached the channel", "a
> reversal bar") is a visual gestalt that must be reduced to inequalities before it can
> be tested at all. This spec's first job is that reduction; its second is to state
> honestly that the free-parameter surface here is the largest of any candidate the lab
> has specced, and the anecdote-to-edge prior is correspondingly low. A rejection at
> spec validation or pregate is the expected, cheap outcome.

## Hypothesis

**Effect claimed.** On a fast intraday chart of a Dow-Jones instrument, when price
stabs *outside* a volatility band (EMA ± multiplier·ATR) and then closes back inside,
that stab was an overshoot; entering on continuation through the reversal bar's extreme
and holding back to the channel midline (the EMA basis) harvests the reversion. Trade
only with the higher-timeframe trend, so the fade is a with-trend pullback entry, not a
naked counter-trend catch.

**Mechanism — who is on the other side, and why would they keep paying?**

The honest, defensible economic core is **short-horizon liquidity provision**. A move
to a 2-ATR extreme on a 3-minute bar is frequently *immediacy-demanded* flow:
stop-runs, forced/margin liquidations, index-tracking impact, and retail momentum
chasing a break. Those flows pay for instant execution at a bad price; a counterparty
who supplies liquidity into the extreme and unwinds as price mean-reverts collects the
overshoot. This is a real, documented effect at short horizons — Nagel (2012,
"Evanescent Liquidity") ties short-term reversal returns to compensation for supplying
liquidity when it is scarce (VIX-loaded); Khandani & Lo document the reversal factor's
returns and its post-2000s decay. The "with the higher-timeframe trend" filter is the
one genuinely principled ingredient: buying a dip *in an uptrend* means the reversion
target (the EMA) and the trend both point the same way, so the trade is a pullback, not
a knife-catch.

**The counterparties**: momentum/breakout traders and mechanical liquidators who push
price to the band and are wrong on a 3–15 minute horizon; we are paid the overshoot as
immediacy providers.

**Why this probably does not survive, stated up front (the adversarial core):**

1. **The liquidity-provision premium at liquid-large-cap intraday scale is exactly
   where HFT market-makers already live.** DIA / YM are among the most efficient
   instruments in the world at 3-minute resolution. The overshoot-reversion at a
   volatility band is precisely the trade colocated market-makers arbitrage in
   microseconds; a discretionary trader reading bars off a chart is the *slow* liquidity
   provider, adversely selected on exactly the fast-information stabs (news, halts) where
   the "overshoot" is real repricing, not noise. Nagel's own result is that the reversal
   premium **compressed sharply** as the space got crowded.
2. **Costs, not signal, are the likely killer.** This is a high-frequency intraday round
   tripper (potentially several trades/day). At DIA's spread + slippage, a per-trade edge
   has to clear a round-trip cost bar on *every* trade — the arithmetic that killed
   `rsi-5050` (+0.30 bps gross vs a 3.5 bps cost bar) and, at the OOS gate, `orb`.
3. **The lab base rate on intraday index-ETF edges is 0 for 2.** `intraday-momentum`
   (published SPY effect) was absent/negative even gross in our SIP data; `orb` (QQQ)
   passed its pregate then failed the post-publication OOS with the long side inverted.
   Both are the same family this idea joins: intraday, liquid US index ETF, mechanical
   rule. Neither survived. There is no in-house precedent for an intraday index-ETF edge
   that clears costs OOS.
4. **The free-parameter count is the highest we have specced.** EMA period (13), ATR
   period (unspecified), two band multipliers (1.3, 2.0), HTF timeframe, HTF trend rule,
   tick offsets, 3-bar expiry, midline-vs-opposite-band target. Every one is a knob the
   trader tuned *by eye on charts they liked*. This is the definition of an overfit
   surface, and the spec's discipline (pre-register one configuration, no sweeps, one OOS
   look) is the only thing standing between it and a data-mined pass.

**The falsifiable claim this spec tests:** a *single pre-registered* Keltner-reversal
configuration on the chosen Dow instrument, with with-trend filtering and honest costs,
produces a positive net per-trade expectancy and clears the frozen bars OOS. If the
edge exists only after choosing among the free parameters, it does not exist. **No
parameter sweeps as a promotion path, ever** — same rule that governed `orb`'s 5-minute
range and `fomc-drift`'s window.

## Universe & timeframe

- **Instrument (PROPOSED — DIA ETF, RTH; see Open Question 1).** "The Dow Jones" is an
  index, not tradeable. The three implementable choices: **DIA** (SPDR Dow ETF — inside
  the lab's existing Alpaca equities/ETF pipeline, RTH only, penny tick, MOC-friendly);
  **YM / MYM** (CME Dow futures — near-24h, 1-point tick, real intraday microstructure
  and the environment this pattern was actually drawn on, **but zero futures data or
  execution infra exists in this lab**); **CFD** (out of scope — no US retail access, no
  pipeline). Recommended default is **DIA**, because it is the only choice that needs no
  new data/broker infrastructure and keeps this idea a cheap test. The material cost of
  that choice is stated in Open Question 1: DIA RTH is a *different instrument* from the
  ~24h chart the recipe was born on.
- **Bar size / data resolution (PROPOSED): 3-minute RTH bars** for the signal, plus a
  **higher-timeframe bar for the trend filter (PROPOSED: 15-minute — already cached, see
  Data)**. 3-minute is the trader's stated chart. The lab currently has DIA **5-minute**
  and **15-minute** bars cached but **not 3-minute** — a data-fetch task (Data section).
  A full RTH day is 130 three-minute bars.
- **Trading session (PROPOSED): US regular session 09:30–16:00 ET; all timestamps ET;
  RTH bars only.** Early closes handled via the exchange calendar, never hardcoded. Note
  this is a deviation from the source chart (see Open Question 1): on a 24h future the
  overnight session carries the pattern too, and the first RTH bars each morning are the
  session's most gappy — the indicator warm-up and the "reached the channel" trigger
  behave differently at an RTH open than mid-session.
- **Holding period (PROPOSED): intraday only, flat by session close, never overnight.**
  Multiple trades per day permitted (one position at a time). This is the lab's **first
  intraday-bar chart-pattern strategy** — all prior work is daily-bar (fomc-drift,
  spx-swing) or overnight (overnight-long) or single-trade-per-day intraday (orb).

## Signals

**No-lookahead contract (binding).** Every quantity in the entry/exit decision at bar
`t` is computed from bars **completed strictly before `t`** (the signal/reversal bar and
earlier) and from the HTF bar **completed before `t`**. The single hardest lookahead
hazard in this strategy is the **intrabar entry-vs-stop ordering** on the 3-minute bar
(see "Entry mechanics" below) — flagged hard because it is exactly the trap `orb`'s core
intrabar-stop extension was built to handle.

### Indicator definitions (PROPOSED formulas — see Open Questions 2 & 3)

All computed on the 3-minute RTH series unless stated. Let `C` = close, and let ATR be
Wilder's ATR.

- **Basis** `E_t = EMA(13)` of the **close** `C`. (Standard-length seed: initialize the
  EMA on a simple 13-bar mean; warm-up ≥ 13 bars per session — see Session rules for the
  cross-session warm-up policy.)
- **ATR** `A_t = ATR(N)` of the 3-minute bars, **Wilder smoothing**. **`N` is
  UNSPECIFIED by the trader** — PROPOSED default `N = 13` (single-length Keltner: ATR
  period equals the EMA period, one fewer free knob). Common alternatives are ATR(10)
  and ATR(14); flagged as Open Question 3.
- **Bands (PROPOSED "Shift = ATR multiplier" reading — see Open Question 2):**
  - Inner: `Uinner_t = E_t + 1.3·A_t`, `Linner_t = E_t − 1.3·A_t`.
  - **Outer (the setup-trigger band): `Uouter_t = E_t + 2.0·A_t`,
    `Louter_t = E_t − 2.0·A_t`.**
  - **Both channels share the single basis `E_t`, so the "middle line" profit target is
    unambiguous: it is `E_t`.** Which band is the "channel" the setup must reach is *not*
    unambiguous from the dictation — PROPOSED: the **2.0 (outer) band** is the extreme
    that must be pierced for a setup; the **1.3 (inner) band's role is left undefined by
    the trader and is NOT used in the pre-registered baseline** (Open Question 2b). A
    plausible alternative use (inner band as the entry/aggression zone) is a sweep and is
    forbidden as a promotion path.

**"Shift" ambiguity (Open Question 2), stated in the formula itself:** on many MT4/MT5
"Envelopes"/"Keltner" indicators the **Shift/Deviation parameter is a *percentage* or a
fixed price offset, not an ATR multiple.** If Shift is a percent, the bands are
`E_t·(1 ± 0.013)` and `E_t·(1 ± 0.020)` — a *constant* 1.3%/2.0% envelope with no
volatility scaling, which is a completely different indicator and would almost never be
touched intraday on DIA (2% of ~$430 = $8.60, far outside a 3-minute range). The
ATR-multiplier reading is pre-registered as the baseline because it is the only reading
under which the pattern triggers at plausible intraday frequency; the percent reading is
recorded as the alternative to resolve with the trader.

### Higher-timeframe trend filter (PROPOSED — see Open Question 4)

"Check the higher time range for trend" has two undefined degrees of freedom (which
timeframe, which trend rule), each a free parameter. PROPOSED pre-registered default,
chosen to minimize new knobs:

- **HTF = 15-minute** (already cached; a 5× multiple of the 3-min signal bar).
- **Trend rule = price vs. the same-length basis on the HTF:** compute `E15_t = EMA(13)`
  of 15-minute closes. **Uptrend** iff the last *completed* 15-min close `> E15`
  **and** `E15` is non-decreasing over the last 3 completed 15-min bars (slope ≥ 0).
  **Downtrend** iff last completed 15-min close `< E15` **and** `E15` non-increasing over
  the last 3 bars. Otherwise **no-trend → no new entries.**
- **Only longs in an uptrend; only shorts in a downtrend.** The filter is evaluated at
  the signal bar using the most recently *completed* 15-min bar (no partial-bar peeking).

This is a filter with genuine overfitting surface (15m vs 30m vs daily; EMA-slope vs
price-vs-EMA vs HH/HL structure vs Keltner-basis slope). It is pinned to one
configuration and **not swept**; alternatives are Open Question 4.

### Setup and reversal-bar definition (PROPOSED — see Open Question 5)

Exact inequalities two implementations must agree on. Let bar `s` be the candidate
**reversal (signal) bar** with OHLC `Os, Hs, Ls, Cs`, evaluated against that bar's own
band values `Louter_s / Uouter_s` (computed from `E` and `A` through bar `s`):

- **Long reversal bar** (only if HTF uptrend): `Ls < Louter_s` (the bar's low pierced
  *below* the lower outer band — "trades outside the line") **and** `Cs > Louter_s` (the
  bar **closed back inside** the band). Strict inequalities; a touch that does not close
  back inside is not a signal.
- **Short reversal bar** (only if HTF downtrend): `Hs > Uouter_s` **and**
  `Cs < Uouter_s`.
- **"Reached the channel" = pierced the outer band with the bar's extreme** (`Low`/
  `High`), not merely closed beyond it — pre-registered as the "trades outside then
  closes inside" reading of the dictation. A bar that closes outside the band is *not* a
  reversal bar (no reversal yet). How far outside counts: **any** amount (`Ls < Louter_s`
  strictly); no minimum penetration depth is imposed (adding one would be a new
  parameter — flagged in Open Question 5 as a candidate, not baselined).

### Entry mechanics (PROPOSED — see Open Questions 6 & 7; intrabar hazard flagged hard)

- **Tick size**: DIA = **$0.01** (one cent). (YM would be 1.0 index point; MYM 1.0 pt —
  Open Question 1.)
- **Long entry**: a **stop-buy** order at `Hs + 1 tick` (= `Hs + $0.01`), armed on the
  bar *after* the reversal bar `s`.
- **Short entry**: a **stop-sell** order at `Ls − 1 tick`.
- **Fill model (backtest)**: on each subsequent bar `b` (`b = s+1, s+2, s+3`), the
  stop-entry is triggered if the bar trades through the level (long: `Hb ≥ Hs + tick`).
  Fill price = the stop level plus entry slippage; **gap-through** (bar opens beyond the
  level: `Ob > Hs + tick`) fills at the **bar open** plus slippage, never at the wished
  level — same discipline as `orb`'s locked gap-through rule.

**INTRABAR LOOKAHEAD HAZARD (LOCKED, flagged hard).** The entry stop and the protective
stop-loss can **both** fall inside the *same* 3-minute bar's range (a long entry through
`Hs+tick` and a protective stop at `Ls−tick` are ~one bar-range apart; a single
volatile 3-min bar can span both). At 3-minute bar resolution the true intrabar path is
unknown, so the fill/stop ordering is ambiguous and is a classic breakout-backtest lie.
This strategy therefore **requires the core intrabar-stop extension already built and
validated for `orb`** (`core/backtest`, touch → stop price / gap-through → bar open /
**worst-case ordering: assume the adverse leg fills first**). Pre-registered worst-case
rule: **on any bar that spans both the entry trigger and the protective stop, assume the
position is entered *and then* stopped the same bar for a full-`R` loss.** Optimistic
"entered and ran to target" assumptions on the same bar are forbidden. This is real
engine reuse, not new work — but it is gated behind the pregate exactly as `orb`'s was.

### Exit (profit — PROPOSED, see Open Question 8)

- **Baseline target = the channel midline `E_t` (the EMA-13 basis).** Exit when any bar
  after entry **touches** the basis: long exits when `Hb ≥ E_b`; short when `Lb ≤ E_b`.
  Fill at `E_b` (the basis at that bar) plus exit slippage; **gap-through the basis fills
  at the bar open.** Because the basis moves each bar, the target is re-evaluated bar by
  bar against the *current* `E_b` (a live quantity, no lookahead — `E_b` uses closes
  through `b−1`... see note).
  - *Basis-evaluation timing (LOCKED to avoid same-bar lookahead):* the target level for
    checking bar `b` is `E_{b}` computed from closes **through bar `b−1`** (the last
    completed value), held constant across bar `b`. This makes the touch test use only
    completed data.
- **Aggressive variant (diagnostic-only, NOT the scored baseline): hold to the opposite
  outer band** (long exits at `Uouter`, short at `Louter`). Pre-registered as a
  reported diagnostic column exactly like `orb`'s 10R target — it is never the verdict
  number, because it adds reward-tail dependence and a second free target. Choosing
  midline-vs-opposite-band *after seeing results* would be a sweep.

### Exit (stop — PROPOSED, see Open Question 7)

The trader left the stop unspecified ("placed accordingly"). PROPOSED, pre-registered:

- **Stop = 1 tick beyond the *opposite* extreme of the signal bar.** Long: stop-sell at
  `Ls − 1 tick`. Short: stop-buy at `Hs + 1 tick`.
- **Resulting R geometry** (why this stop): entry = `Hs + tick`, stop = `Ls − tick`, so
  **risk per share `D = (Hs − Ls) + 2 ticks`** = the signal bar's range plus two ticks.
  Reward to the midline target = `E − (Hs + tick)` for a long. Since the reversal bar
  pierced the 2.0 band and closed back inside, `Hs` sits roughly ~1.3–2.0 ATR below the
  basis while the bar range `D` is typically a fraction of one ATR — so the **midline
  target is commonly ~2–4× the stop distance (R:R ≈ 2:1 to 4:1)**, and the opposite-band
  variant ~2× that again. That favorable geometry is the whole appeal; it is also why
  hit rate can be low and the strategy still positive — *if* the reversion actually
  reaches the midline often enough, which is the empirical question the backtest settles.
- Same intrabar semantics as the entry: touch → stop price; gap-through → bar open;
  worst-case ordering on any bar spanning both stop and target.

### Exit (time — PROPOSED)

- **Forced flat via market order at the open of the session's final 3-minute bar**
  (15:57 ET on full days; close −3 min on early closes). No overnight positions, ever.
- **3-bar entry expiry (LOCKED to the dictation):** if the stop-entry order has not
  filled by the close of bar `s+3` (i.e., within 3 bars after the reversal bar), it is
  **cancelled** and that setup is dead. A fresh reversal bar starts a new setup.

### Session and re-entry rules (PROPOSED)

- **One position at a time** (no pyramiding, no simultaneous long+short). While a
  position or a live (un-expired) entry order is working, new reversal bars are ignored.
- **Re-entry**: after a flat (stop, target, or time exit), a *new* reversal bar may arm
  a new entry the same session — no cool-down in the baseline (a cool-down would be a new
  parameter; flagged in Open Question 9).
- **Warm-up**: no entries until ≥ `max(13, N)` completed 3-min bars **and** ≥ 3 completed
  15-min bars exist in the session. **Cross-session EMA/ATR carry (Open Question 3b):**
  PROPOSED to *reset indicators each session* (no carry across the overnight gap), since
  RTH-only DIA has an 17.5h gap the EMA/ATR would otherwise smear across; this delays the
  first entry to ~mid-morning. Flagged because it materially changes early-session
  behavior and is a real choice, not an obvious default.

## Risk

- **Baseline risk unit: `R = 0.5%` of equity per trade** (house standard), **stop-distance
  sized**: `shares = floor( min( (R·equity) / D, equity / price ) )`, with
  `D = (Hs − Ls) + 2 ticks`. **No leverage; notional capped at 100% of equity.** If
  `shares = 0` (stop so tight that 0.5% risk wants > 1× notional — common when `D` is a
  few cents), **skip the trade** rather than round up risk.
  - *Honest consequence (as in orb):* tight 3-min signal-bar ranges make `D` small, so
    the no-leverage cap will often bind and **realized R < 0.5%**. The realized-R
    distribution is mandatory reporting; all R-multiples refer to realized risk.
- **Max concurrent positions**: 1.
- **Per-trade stop**: the signal-bar opposite-extreme stop above, broker-side from the
  moment of fill; intrabar worst-case ordering in backtest.
- **Daily loss limit**: **2·R** anchored at the prior session's closing equity, per the
  house core `RiskManager.on_bar()`. With multiple trades/day this can bind *within* a
  session — PROPOSED: on hitting −2R realized+unrealized on the day, **halt new entries
  for the rest of the session** (existing position still managed to its stop/target/time
  exit). Flagged (Open Question 10) because a multi-trade-per-day intraday book is the
  first in the lab to plausibly hit an intraday daily-loss halt, and the exact behavior
  (halt-new-entries vs flatten-now) needs a decision.
- **Max drawdown kill switch: 10%** peak-to-trough equity (PROPOSED; tighter than the
  house 15% — an intraday flat-by-close book has no overnight-gap excuse, matching orb /
  rsi-5050). Flagged for sign-off.
- **PDT flag (live only)**: a multi-trade-per-day intraday book easily exceeds the FINRA
  pattern-day-trader threshold → requires a ≥ $25k margin account live. Paper unaffected.
  Recorded now.
- **Reporting (LOCKED if approved)**: per-trade P&L in bps and realized R; hit rate;
  exit-type split (stop / midline target / time); **long vs short split** (a one-sided
  result is trend/beta, not the reversal hypothesis); trades/day distribution; per-year
  means (decay visibility); stop-distance and realized-R distributions; time-to-target
  distribution; worst trade in R; max consecutive losses; midline-vs-opposite-band
  diagnostic; cost drag gross vs net per run.

## Data requirements

- **Data types**: RTH **3-minute** OHLCV bars for the chosen instrument (signal) + RTH
  **15-minute** OHLCV bars (HTF trend filter). No quotes, news, or fundamentals for
  signals. Exchange calendar with early closes (in core).
- **Data-availability task (BLOCKING, pre-declared).** The lab has cached
  `data/DIA_5m.parquet` and `data/DIA_15m.parquet` but **no 3-minute DIA file** — it
  must be fetched. Alpaca's bars endpoint supports arbitrary minute timeframes
  (`3Min`), so this is a fetch + cache task, not a provider problem. Deliverable:
  `data/DIA_3m.parquet` — a single file spanning 2017-12 → present (SIP, raw, RTH,
  matching the cached `DIA_5m`/`DIA_15m` provenance so the aggregation audit is
  apples-to-apples). The WF window (2025→) lives in the same file and stays **unread**;
  the discipline is enforced by the pregate's hard IS-only date slice, exactly as
  `pregate_rsi5050.py`/`pregate_fomc.py` do — not by a separate physical file. Built and
  audited against the existing 5m/15m files: the 3-min sequence must aggregate **exactly
  to the cached 15m bars** (five 3-min bars → one 15-min bar; boundaries align every
  15 min) and to daily OHLC. (3-min vs 5-min aligns only at 15-min boundaries — LCM(3,5)
  = 15 — so the 15m and daily aggregations are the binding checks.) Named `DIA_3m.parquet`
  (not `_adj`): adjustment is immaterial here (never spans an ex-date) and the raw label
  matches the raw cached siblings. If DIA is rejected in favor of YM/MYM (Open Question 1), this
  becomes a **new futures-data-pipeline task** — materially larger, and itself a reason
  the DIA default is recommended for a first cheap test.
- **Adjustment**: because the book is **intraday-only and never spans an ex-date or an
  overnight**, dividend back-adjustment is a constant within-session multiplicative
  factor and is **immaterial to every quantity used** (band distances in ATR units, bps
  returns, R-multiples, direction signs) — the same argument that made `orb` adjustment-
  invariant. Adjusted or raw prints are equally valid; no splice/dividend audit needed.
  Ex-div dates tagged in reporting for hygiene. (DIA pays monthly dividends — more
  ex-dates than SPY/QQQ — which is exactly why the never-overnight invariant matters.)
- **History depth**: PROPOSED windows below need ~2018 → present of 3-min DIA. No
  long warm-up beyond intraday indicator seed (indicators reset each session per Open
  Question 3b).
- **Source**: Alpaca historical SIP bars (equities pipeline, already on hand for
  SPY/QQQ; DIA 5m/15m already cached). Live/paper path: Alpaca Algo Trader Plus
  (real-time SIP, subscribed 2026-07-05).
- **Reproducibility**: every run records vendor, feed, symbol, bar size, adjustment,
  data range, file hashes, seed, git commit (house rule 5).

## Cost assumptions

Costs are mandatory (house rule 3), modeled in `core/backtest/costs.py`. **This is a
high-frequency intraday round-tripper and cost drag is the single most likely killer** —
state it plainly. DIA is liquid but **less liquid than SPY/QQQ**: ~$430 price, typical
quoted spread ~1–3 cents ≈ **0.2–0.7 bps full spread**, wider and thinner than SPY.

- **Commission**: $0/share (Alpaca).
- **Half-spread (PROPOSED)**: **0.3 bps/side** (~1.3 cents on $430 — above SPY/QQQ's
  ~0.1 to reflect DIA's thinner book).
- **Slippage (PROPOSED)**: **0.4 bps/side** on stop-entry / market-exit fills; **1.2
  bps** on protective-stop fills (stops fill on adverse momentum by construction).
- **Round trips (PROPOSED)**: target/time exit ≈ **1.4 bps**; stop exit ≈ **2.2 bps**;
  blended (assume ~40–60% stop-out) ≈ **~1.8 bps**.
- **LOCKED cost bar (proposed): 2.5 bps round trip** — rounded conservatively above the
  blended model, reflecting DIA's thinner book. **Cost-sensitivity gate**: OOS result
  must remain net-positive at **1.5× costs (3.75 bps)**.

**The arithmetic the result will be judged against (PROPOSED framing).** Suppose the
midline reversion is real and the R:R ≈ 3:1 with a ~40% hit rate → gross expectancy per
trade ≈ `0.4·3R − 0.6·1R = +0.6R`. But `R` in *bps of notional* is the stop distance `D`
= a signal-bar range + 2 ticks ≈ **8–20 bps of price** at 3-min DIA scale, so +0.6R ≈
**~5–12 bps gross per trade**. Minus ~1.8 bps costs → ~3–10 bps net *if the hit rate and
R:R hold*. At (say) 1–3 trades/day × ~250 days that is 250–750 trades/yr; the cost drag
alone is **~4.5–13% of notional/yr** — so a half-strength effect (hit rate 30%, or
target rarely reached) flips the sign. There is no cost headroom; the gross edge must be
robust, not rounding error. This arithmetic is the pregate's whole point.

## Success criteria (locked before first backtest)

**FROZEN 2026-07-07 (signed off by the user). Now immovable** (workflow gate 1). Every
parameter (instrument, EMA 13,
ATR period, 1.3/2.0 multipliers, HTF 15m + trend rule, tick offsets, midline target,
3-bar expiry, windows) is pre-registered as **one** configuration; **nothing is ever
swept**, so there is nothing to re-tune between IS and OOS.

### PREGATE — pre-scoring gross-edge diagnostic (run FIRST, outside the engine)

Following the house pattern (`pregate_orb.py`, `pregate_rsi5050.py`), a standalone
`scripts/pregate_keltner.py` runs on `data/DIA_3m.parquet` + 15m, **IS window only;
OOS and WF stay unread.** Per session: compute the indicators, the HTF filter, detect
reversal bars, simulate the stop-entry (3-bar expiry), the signal-bar-opposite stop, and
the **midline** exit with the **exact locked intrabar worst-case semantics** (stop before
target on any spanning bar); record signed **gross** return in bps of entry price per
trade, plus trades/day and long/short counts.

**Gate rule (PROPOSED, LOCKED before the script is written) — REJECT at spec validation
if:**

- **IS mean gross return per trade ≤ 2.5 bps** (the locked round-trip cost bar — the
  average trade must at least pay for its own round trip), **or**
- **the signal does not beat the matched unconditional intraday baseline** — i.e., the
  mean gross return of the *same number of with-trend entries taken at random 3-min bars*
  (or, simpler and pre-registered: the mean 3-min-bar forward return over the same
  holding-time distribution in the trend direction). A "reversal" edge that does not beat
  being long DIA in an uptrend for the same average holding time is beta plus noise —
  the arithmetic that killed spx-swing and gated orb.

t-stats reported for honesty; threshold rules bind (house convention). On PASS: reuse the
`orb` intrabar-stop core (no new engine work expected), engine IS run must reproduce the
pregate to rounding (the orb/fomc cross-check pattern), then the **one** pre-registered
OOS look + its 1.5×-cost companion. On FAIL: reject, **no** parameter/instrument/HTF
shopping, post-mortem in this file.

### Backtest bars (engine, net of the locked cost bar)

| # | Proposed frozen bar |
|---|---|
| 1 | **OOS net zero-filled Sharpe ≥ 1.0** annualized (house intraday convention; matches orb — an intraday flat-by-close book has no overnight-risk excuse and ample statistical power) |
| 2 | **Net-positive expectancy per trade after costs; and still net-positive at 1.5× costs (3.75 bps)** |
| 3 | **Both-sides gate**: net expectancy > 0 on longs *and* shorts separately in OOS (a one-sided result is trend/beta, not the reversal hypothesis) |
| 4 | **Beat DIA buy-and-hold net Sharpe** over the identical OOS window (capital and attention are finite; the claim is a tradeable edge, not participation) |
| 5 | **Max OOS drawdown ≤ 10%** peak-to-trough (consistent with the kill switch) |
| 6 | **Worst single trade ≤ 2.0·R realized** (breach ⇒ gap-through overshoot under-provisioned) |
| 7 | **Minimum OOS trade count ≥ 300 filled trades** (needed for per-trade significance at these bps-level edges; below it the verdict is inconclusive-reject regardless of Sharpe) |
| 8 | **IS→OOS decay guard**: OOS net Sharpe not more than 50% below IS net Sharpe |

**No-rescue clause (PROPOSED, LOCKED on approval):** the aggressive opposite-band target,
the inner (1.3) band, alternative HTF timeframes/trend rules, and per-year sub-splits are
**diagnostics only, never gates and never promotion paths**. A full-OOS fail cannot be
rescued by switching the target, the HTF, or the instrument.

### Windows (PROPOSED)

- **In-sample: 2018-01-01 → 2022-12-31** (vol-rich regimes where a liquidity-provision
  reversal edge should be *most* present — 2018 Q4, 2020, 2022).
- **Out-of-sample: 2023-01-01 → 2024-12-31.**
- **Walk-forward: 2025-01-01 → present, unread until the OOS verdict.**
- Windows subject to the actual date coverage of the fetched 3-min DIA file; if history
  is shorter than 2018, the IS start moves up and is re-declared **before** any backtest.
- **What "working" looks like (declared now):** most trades small losses at ~−1R
  realized, P&L carried by trades that reach the midline; hit rate plausibly 35–50% given
  the R:R; multi-loss streaks and mid-single-digit drawdowns are *normal operation* —
  failure is defined only by the locked bars above.

## Known failure modes

Regimes where this should lose, and what limits the damage:

- **Trend/breakout days (the signature failure).** A genuine information-driven break
  pierces the 2.0 band and *keeps going* — the "reversal bar" is a pause, price never
  returns to the midline, and the with-trend filter actively *encourages* the entry right
  before continuation resumes against a mean-reversion exit. This is the mode that
  inverted `orb`'s long side. *Bounding:* the signal-bar-opposite stop, worst-case
  intrabar ordering, realized-R sizing, both-sides gate (a fade strategy that only makes
  money on the trend-aligned side is closet momentum, and #3 catches it).
- **High-volatility news stabs (adverse selection — the mechanism's Achilles heel).** The
  liquidity-provision premium is *negative* exactly when the extreme is real repricing
  (FOMC 14:00, CPI 08:30 spillover, halts/LULD). We are the slow liquidity provider
  adversely selected on these bars; stop slippage is worst here. *Bounding:* gap-through
  fills at the bar open (never the wished level), 1.2 bps stop slippage, no event filter
  in v1 (event days tagged in reporting).
- **Costs in quiet tape (the likely quiet death).** Low vol ⇒ tiny signal-bar ranges ⇒
  tiny `D` ⇒ the midline target is a few cents away and the per-trade edge is dominated by
  spread+slippage; trade frequency may also rise as bands hug price. This is where the
  cost arithmetic flips negative. *Bounding:* the 2.5 bps pregate cost bar and the 1.5×
  cost-sensitivity gate; per-year and stop-distance-bucket reporting expose it. No
  minimum-range filter is added (a new parameter).
- **Intrabar-ordering optimism (the backtest-lie mode).** If entry and stop are assumed to
  fill in a favorable order on the same 3-min bar, the backtest manufactures edge that
  cannot be executed. *Bounding:* the LOCKED worst-case ordering (adverse leg first),
  reusing orb's validated core extension.
- **Overfitting / anecdote risk (the elephant).** The highest-free-parameter idea specced
  in the lab, from a chart the trader liked. *Bounding:* one pre-registered configuration,
  no sweeps ever, the pregate before any engine work, the single OOS look, and the base
  rate (intraday index-ETF edges 0/2 in-house) stated up front. A rejection here is the
  cheap, expected outcome — that is a feature.
- **Instrument mismatch (the provenance mode).** The pattern was drawn on a ~24h MT4
  chart; testing RTH-only DIA removes the overnight session and changes the open-bar
  microstructure. If the effect lived in the overnight/futures tape, DIA-RTH will not
  show it and the honest conclusion is "not tested as the trader meant it" — recorded, not
  papered over (Open Question 1).
- **RTH-open warm-up artifacts.** With indicators reset each session (Open Question 3b),
  the first ~13 bars have no signal and the bands are still stabilizing; the first tradable
  window is mid-morning. If carried across sessions instead, the overnight gap smears the
  ATR. Either choice has a cost; the choice is pre-registered, not optimized.

## Sign-offs (resolved 2026-07-07 — spec approved, criteria frozen)

All 11 gaps in the verbal dictation were put to the user 2026-07-07 and resolved as
follows. **Every one took the recommended default** (baked into the spec above). The
"PROPOSED" markers throughout the body are now the frozen configuration. The `orb`-mirrored
success-criteria set and windows are LOCKED and immovable from this point.

1. **Instrument — SIGNED OFF: DIA (RTH ETF).** No new data/broker infra; cheapest first
   test. Accepted cost: DIA-RTH is a different instrument from the ~24h MT chart the idea
   was born on (no overnight session, gappier opens) — recorded as the "instrument
   mismatch" failure mode, not papered over.
2. **"Shift" semantics + setup band — SIGNED OFF: Shift = ATR multiplier** (bands =
   EMA ± Shift·ATR), **outer 2.0 band** as the setup/extreme trigger, **inner 1.3 band
   unused** in the baseline (using it would be a sweep).
3. **ATR period + session carry — SIGNED OFF: ATR(13)** (single-length Keltner) and
   **reset EMA/ATR each session** (no carry across the RTH gap).
4. **HTF timeframe + trend rule — SIGNED OFF: 15-minute**, trend = price vs EMA(13) on the
   15-min **AND** 3-bar EMA-slope sign; longs only in uptrend, shorts only in downtrend.
5. **Reversal-bar exactness — SIGNED OFF:** pierce = bar extreme strictly beyond the 2.0
   band, close strictly back inside, **no minimum penetration depth**.
6. **Tick / entry offset — SIGNED OFF: +1 tick = +$0.01** (DIA).
7. **Stop placement — SIGNED OFF: 1 tick beyond the opposite signal-bar extreme**
   (`D = signal-bar range + 2 ticks`).
8. **Profit target — SIGNED OFF: midline (EMA basis)** scored baseline; opposite-band
   variant diagnostic-only, never a verdict number.
9. **Re-entry / cool-down — SIGNED OFF:** one position at a time, no cool-down, multiple
   setups/day allowed.
10. **Intraday daily-loss behavior — SIGNED OFF:** on a −2R day, halt new entries for the
    session; manage the open position to its stop/target/time exit.
11. **Success criteria — SIGNED OFF as written and FROZEN:** OOS net Sharpe ≥ 1.0;
    net-positive/trade at 1× and 1.5× costs; both-sides gate; beat DIA B&H; DD ≤ 10%;
    worst trade ≤ 2R; ≥ 300 trades; decay ≤ 50%; cost bar 2.5 bps; IS 2018–22 / OOS
    2023–24 / WF 2025→ unread until the OOS verdict.

**Next step per the funnel:** blocking data task (fetch + audit `data/DIA_3m.parquet`,
aggregation-checked against the cached 5m/15m) → `scripts/pregate_keltner.py` on the IS
window only, outside the engine; OOS and WF stay unread. Expected outcome per the lab's
base rate (intraday index-ETF edges 0/2 in-house, highest free-parameter surface specced):
reject at the 2.5 bps cost bar or the matched-baseline gate — a fine outcome that costs one
session and no engine code.

### Original open-question detail (retained for the record)

1. **Instrument.** *Recommend **DIA** (RTH ETF).* It is the only choice needing no new
   data/broker infra, keeps this a cheap first test, and is MOC/pipeline-native. Cost of
   the choice, stated: DIA-RTH is a *different instrument* from the ~24h MT4 chart the
   idea was born on (no overnight session, gappier opens). YM/MYM futures match the source
   microstructure but require a **new futures data + execution pipeline** the lab does not
   have — a large task to gate on an unvalidated anecdote. CFD is out of scope.
2. **"Shift" semantics + which band is the setup trigger.** *Recommend Shift = **ATR
   multiplier** (bands = EMA ± Shift·ATR), outer **2.0** band as the setup/extreme, and
   the inner **1.3** band **unused** in the baseline.* The ATR reading is the only one that
   triggers at plausible intraday frequency; a percent/offset reading (2% envelope) would
   essentially never be touched on 3-min DIA. Confirm with the trader what their MT
   indicator's "Shift" actually computes, and what the 1.3 band is *for* (my guess: a
   softer setup zone — but using it is a sweep, so it stays out of the pre-registered run).
3. **ATR period `N` + cross-session indicator carry.** *Recommend **ATR(13)** (single-
   length Keltner, one fewer knob) and **resetting EMA/ATR each session** (no carry across
   the 17.5h RTH gap).* Alternatives ATR(10)/ATR(14) are common; carrying indicators across
   sessions smears the overnight gap into the ATR. Both are real choices, not obvious
   defaults — needs a call.
4. **HTF timeframe + trend rule.** *Recommend **15-minute** (already cached) with trend =
   **price vs EMA(13) on the 15-min AND 3-bar EMA-slope sign**.* This is a filter with a
   big overfitting surface (15m/30m/daily × EMA-slope/price-vs-EMA/HH-HL/basis-slope);
   pinned to one config, never swept. Confirm the trader's actual "higher time range."
5. **Reversal-bar exactness.** *Recommend: pierce = bar **extreme** (Low/High) strictly
   beyond the **2.0** band, close strictly back inside; **no minimum penetration depth**.*
   The alternative "close beyond the band" reading makes it a different (non-reversal)
   signal. A minimum-penetration filter is a candidate parameter, deliberately **not**
   baselined.
6. **Tick / entry offset.** *Recommend **+1 tick = +$0.01** for DIA* (1.0 point for
   YM/MYM if the instrument changes). Governs entry `Hs+tick` and stop `Ls−tick`.
7. **Stop placement (trader left it open).** *Recommend **1 tick beyond the opposite
   extreme of the signal bar*** → `D = signal-bar range + 2 ticks`, giving R:R ≈ 2:1 to
   4:1 to the midline. The alternative (ATR-based or band-based stop) adds a parameter and
   is not baselined. **This is the single biggest trader-unspecified item.**
8. **Profit target.** *Recommend **midline (EMA basis)** as the scored baseline*; the
   **opposite-band** aggressive variant is diagnostic-only and can never become the verdict
   number (choosing it post-results would be a sweep).
9. **Re-entry / cool-down and multi-trade-per-day.** *Recommend **one position at a time,
   no cool-down**, multiple setups/day allowed.* A cool-down is a new parameter; flagged so
   the trader can veto if they intended one-and-done per session.
10. **Intraday daily-loss-limit behavior.** *Recommend on −2R day: **halt new entries for
    the session**, manage the open position to its exit.* First lab book that can hit an
    intraday daily halt; confirm halt-new-entries vs flatten-now.
11. **Success criteria set** (Sharpe ≥ 1.0, both-sides gate, beat-DIA-B&H, ≤ 10% DD,
    worst trade ≤ 2R, ≥ 300 trades, decay ≤ 50%, cost bar 2.5 bps + 1.5× companion, IS
    2018–22 / OOS 2023–24 / WF 2025→). *Recommend as written* — mirrors the frozen `orb`
    bars, the closest in-house comparable. **Freezes at first backtest; sign off before
    the pregate script is written.**

## Verdict — REJECTED at spec validation / pregate (2026-07-07)

The pipeline ran exactly as frozen, up to the first gate: blocking data task done
(`data/DIA_3m.parquet`, 279,583 bars, aggregation-audited clean against the cached 15m —
3m→15m OHLC exact, 3m→daily 0 violations) → `scripts/pregate_keltner.py` on the **IS
window only** (2018-01-01..2022-12-31, 1,259 sessions; OOS/WF hard-sliced, never read).
The setup fails the LOCKED gate before any engine work.

**Pregate scorecard (gross of costs; n=638 filled trades, 127.6/yr):**

| Gate | Result | |
|---|---|---|
| IS mean gross / trade > 2.5 bps (locked cost bar) | **−0.839 bps** (t=−1.90) | **FAIL** |
| Beat matched trend-direction baseline | strat −0.839 vs baseline **+1.905** → edge **−2.744 bps** | **FAIL** |

Both sides fail (long −1.03 bps t=−2.07 n=439; short −0.43 bps n=199). Every IS year is
negative except 2022 (+0.17). The gross edge is **negative before a single basis point of
cost** — the highest-free-parameter idea the lab specced dies at the cheapest gate.

**Why — the geometry was real and still lost.** Exit split: target 59.9% at +5.41 bps
(86.9% hit), stop 36.8% at −10.52 bps, time 3.3% at −6.15 → blend −0.84 bps. The *median*
trade is positive (+0.67 bps); the mean is dragged under by the stop tail (negative-skew
mean-reversion). The favorable-looking R:R does not survive the realized stop distances
(median 8.9 bps) and gap-through. And the "fade to the midline" structure earns **less**
than simply holding DIA in the 15-min-uptrend direction for the same ~1-bar clock time
(the +1.905 bps baseline). The reversal adds negative value.

**Reject is robust to the one modeling choice with latitude.** Re-running the exit under
the *optimistic* intrabar ordering (target-before-stop, the theoretical ceiling the LOCKED
worst-case can never beat) gives −0.703 bps — 0.14 bps better and **still negative, still
3.2 bps under the bar**. Failure is at the signal level, not the fill accounting — mirror
of `intraday-momentum` and `spx-swing`.

**No-rescue clause binds (LOCKED).** No parameter/HTF/instrument shopping, no ToD slice
(midday's ~flat +0.33 bps is a diagnostic, not a door), no opposite-band promotion
(diagnostic −0.878 bps, worse). The OOS and WF windows were never read and stay sealed.
**Intraday liquid index-ETF edges are now 0/3 in-house** (intraday-momentum, orb, this).
Full writeup + scorecard: `experiments/keltner-reversal/2026-07-07-pregate/notes.md`.

**Implementation note carried into the verdict** (the frozen spec was internally
under-determined on one point): "reset indicators each session" is incompatible with an
EMA(13) HTF trend warmed up after only 3 15-min bars. Resolved by the only coherent
reading — 3-min band indicators reset per session (the Open Q3b overnight-gap rationale),
15-min trend EMA continuous. It touches only the direction filter, and the reject is
gross-negative on both sides and robust to exit ordering, so the choice is not load-bearing
on the verdict. Recorded for any future reviewer.
