# Strategy: turtle-soup

- **Status**: **REJECTED at pregate (spec-validation), 2026-07-10** — IS-only, gross-negative; see Post-mortem. Frozen same day (all 12 open questions resolved to recommended defaults); success criteria locked before the pregate script existed; OOS/WF never read.
- **Created**: 2026-07-10
- **One-liner**: Fade false Donchian-channel breakouts (Raschke/Connors "Turtle Soup") — enter counter-trend when a 20-day high/low breakout fails, betting the breakout was stop-hunting fuel rather than trend initiation.

> **Provenance.** Raschke & Connors, *Street Smarts: High Probability Short-Term Trading
> Strategies* (1995), chapters "Turtle Soup" and "Turtle Soup Plus One." The published
> canonical rule (buys): (1) today the market makes a new 20-day low; (2) the *previous*
> 20-day low was made at least four trading sessions earlier; (3) place a buy entry stop
> just above the prior 20-day low, good for a limited window; (4) if filled, initial
> protective stop one tick below today's low; (5) take profits within 2–6 bars or trail.
> Mirror at 20-day highs for shorts. "Plus One" is the next-day variant: the setup day
> must *close* at/beyond the prior 20-day extreme, and the entry stop is placed the
> following session. The name is the joke: Richard Dennis's "Turtle" traders bought
> 20-day Donchian breakouts (Turtle System 1); this strategy makes soup out of them.
>
> **Stated bluntly:** this rule is 30 years post-publication, appears in every
> short-term-trading book since, and its modern rebranding ("liquidity sweep,"
> "stop hunt," ICT-style "turtle soup") is a retail meme — meaning *both* sides of the
> trade are now crowded. The lab's own base rate on adjacent families is 0-for-3
> (rsi-5050: daily index-ETF mean reversion, no gross edge; keltner-reversal: fade with
> a tight stop, gross-negative at pregate; orb: published breakout pattern, died OOS).
> The prior is low; the design goal is a **cheap kill at an IS-only pregate before any
> engine code**, exactly like keltner-reversal and tsmom.

## Hypothesis

**Effect claimed.** When price breaks a salient multi-day extreme (the 20-day Donchian
channel) and the breakout immediately fails — price snaps back through the old extreme
within a day — the subsequent move continues in the reversal direction for several days.
Entering *on a stop* back through the broken level (so the snap-back must already be
underway) captures that continuation.

**Mechanism — who is on the other side and why would they keep paying?**

1. **Trapped breakout traders.** Donchian-breakout followers (the original Turtles'
   System 1 was literally the 20-day channel; retail breakout systems still use it)
   enter on stops *at* the new extreme. When the breakout fails, they are underwater
   immediately; their protective stops sit just back inside the old range. The failure
   triggers a cascade of their exit stops — mechanical, price-insensitive flow — which
   fuels the snap-back we are positioned for. We are paid by trapped momentum traders
   forced to exit at bad prices.
2. **Stop-density at Schelling points.** Resting stops cluster at salient reference
   levels — prior N-day highs/lows are the canonical example. A shallow break that
   finds no follow-through buying/selling beyond the sweep is evidence the move was
   stop liquidity, not information. This clustering is structural (stops must live
   somewhere, and salient extremes are where humans and simple systems put them), so
   the payer class *regenerates* with each cohort of breakout traders — the best
   available argument for post-publication survival.
3. **Confirmation-gated liquidity provision.** Unlike keltner-reversal (which faded
   into the move and died in its stop tail), the entry here is a **stop order back
   through the broken level**: we never catch the falling knife. In a genuine cascade
   (2008, 2020) new lows keep printing, price never recovers the prior 20-day low, the
   entry never fills, and we have zero exposure. The trade only exists once the
   reversal has objectively begun. This is the structural difference from the 8th
   candidate — stated so the pregate can test whether it matters.

**Why this probably does not survive (the adversarial core):**

1. **Thirty years of publication.** Street Smarts (1995) is one of the most-read
   trading books ever; the pattern is taught, coded, and sold. ORB — a far more
   recently published pattern — inverted OOS in this lab. Post-publication decay is
   the default expectation, not a tail risk.
2. **The fade side is now crowded too.** "Buy the failed breakdown / sell the sweep"
   is contemporary retail orthodoxy. When both the breakout crowd and the fade crowd
   are retail memes, the residual after they net is whatever HFT liquidity providers
   leave behind — plausibly nothing, on the world's most liquid ETFs.
3. **Daily mean reversion on liquid US index ETFs is dead in-house.** rsi-5050 had no
   gross edge; keltner's fade was gross-negative. The 20-day-extreme conditioning must
   add real information over "buy weakness," or the matched-baseline gate kills it.
4. **The published evidence is anecdotal.** Street Smarts shows chart examples, not a
   refereed sample. Later independent tests of Turtle Soup on futures show marginal,
   parameter-sensitive results; there is no MOP-grade refereed anomaly here. This spec
   treats the rule as a hypothesis with a good mechanism story and weak evidence.

**The falsifiable claim this spec tests:** the single pre-registered Street Smarts
Plus-One configuration, applied symmetrically (long and short) across the lab's
audited 8-ETF multi-asset basket with honest costs, produces (a) a gross per-trade
edge above the locked cost bar and (b) positive edge over a matched same-instrument,
same-direction, same-holding-clock drift baseline — in-sample first (pregate), then
through one sealed OOS look. If the edge appears only under parameter choice, it does
not exist. **No sweeps as a promotion path, ever.**

## Universe & timeframe

- **Instruments (FROZEN — the existing 8-ETF tsmom basket; Open Question 2, resolved):**
  SPY / EFA / EEM (equities), IEF / TLT (bonds), DBC / GLD (commodities), UUP
  (dollar). One canonical choice, justified: (i) Turtle Soup was published for
  *futures* across asset classes — a multi-asset basket is closer to the source
  environment than a single index ETF, and SPY alone is both the most efficient
  instrument on earth and a repeat in-house graveyard; (ii) the basket **already
  exists, self-CRSP-adjusted and audited** (`scripts/build_tsmom_basket.py`,
  `data/tsmom/*.parquet`, common start 2007-03) including adjusted highs/lows — zero
  new data infrastructure; (iii) 8 instruments × 2 sides is the only way this
  low-frequency setup reaches a defensible trade count. **The set is pre-registered:
  no adding/dropping/swapping instruments to fish for a pass.** If the basket fails,
  the strategy is rejected, not re-composed.
- **Bar size / data resolution**: daily total-return-adjusted OHLCV bars,
  session-close stamped (canonical schema from the basket builder). No intraday data.
- **Trading session**: US regular session. Transacted prints: intraday stop fills
  (entry and protective stop) and closing-auction MOC (time exit). All timestamps ET
  in reporting; exchange calendar handles early closes.
- **Holding period**: multi-day swing, 1–5 sessions typical, overnight and
  over-weekend exposure by construction. Long and short.

## Signals

**No-lookahead contract (binding).** Every quantity used in the decision for session
`t` is computed from bars completed **strictly before** `t`. The setup is detected on
the completed setup-day bar; orders are armed for the *next* session. The hard hazard
here is **intrabar (intraday-path) ordering on daily bars** — the entry stop and the
protective stop can be spanned by one daily bar — handled by the locked worst-case
rule below, reusing the intrabar-stop core built and validated for `orb`.

### Variant selection (FROZEN — Open Question 1, resolved)

**Baseline = Turtle Soup Plus One** (the published next-day variant). Reason: the
original same-day variant arms the entry stop *intraday after* today's new low is
made, which is unimplementable on daily bars without inventing an intraday path. Plus
One's setup is fully determined by the completed setup-day bar — clean daily-bar
semantics, same book, same page. The same-day variant is **not** a fallback or a
diagnostic; it is out of scope.

### Definitions (per instrument `i`; all from adjusted daily OHLC)

- **Prior 20-day extremes (excluding today):**
  `DCL_t = min(L_{t-20} … L_{t-1})`, `DCH_t = max(H_{t-20} … H_{t-1})`.
- **Separation**: let `m_L(t)` = the most recent session in `{t-20 … t-1}` whose low
  equals `DCL_t` (ties → most recent). Mirror `m_H(t)` for highs.
- **Tick** = $0.01 (all 8 are US-listed ETFs).

### Setup day `s` (Street Smarts rules 1–2 + the Plus-One close condition)

- **Long setup**: `L_s < DCL_s` (new 20-day low today) **AND** `s − m_L(s) ≥ 4`
  sessions (the previous 20-day low is at least 4 trading days old — the published
  "at least four trading sessions earlier") **AND** `C_s ≤ DCL_s` (closes at or below
  the prior 20-day low — the Plus-One condition). Strict inequality on the low;
  `≤` on the close per the book's "close at or below."
- **Short setup** (mirror): `H_s > DCH_s` **AND** `s − m_H(s) ≥ 4` **AND**
  `C_s ≥ DCH_s`.

### Entry (session `s+1` only — FROZEN validity window, Open Question 4, resolved)

- **Long**: buy-stop at `DCL_s + $0.01`, armed at the open of session `s+1`,
  **cancelled at the close of `s+1` if unfilled** (mirrors the original rule's
  "good for today only"; the re-entry rule the book appends is excluded — Open
  Question 7). The entry offset is 1 tick (Open Question 3 — the book's futures
  "5–10 ticks" has no canonical penny-ETF translation; 1 tick is the minimal,
  least-parameterized reading).
- **Short**: sell-stop at `DCH_s − $0.01`, same validity.
- **Fill model**: if `O_{s+1}` is already through the level (long: `O_{s+1} >
  DCL_s + 0.01`), fill at the **open** plus slippage (gap-through never fills at the
  wished level); else if the bar trades through it (long: `H_{s+1} ≥ DCL_s + 0.01`),
  fill at the level plus slippage; else no fill, setup dead.

### Exit (stop)

- **Long**: protective sell-stop at `L_s − $0.01` (one tick below the setup day's
  low — the published rule), live from the moment of fill. **Short**: buy-stop at
  `H_s + $0.01`.
- **Risk per share** `D` = entry − stop = (long) `(DCL_s − L_s) + $0.02` — i.e. the
  breakout's penetration depth plus two ticks. Shallow sweeps ⇒ tight stops ⇒
  frequent small losses; this is the negative-skew axis named in Known Failure Modes.
- Stop fill: touch (`L_b ≤ stop`) → fill at the stop price plus slippage;
  **gap-through** (`O_b < stop`) → fill at the **bar open** plus slippage. Overnight
  gaps can therefore lose **more than 1R**; provisioned in sizing and the worst-trade
  bar.

**INTRADAY-PATH WORST-CASE ORDERING (LOCKED).** On any bar that spans both the entry
trigger and the protective stop (long: `H_b ≥ entry` and `L_b ≤ stop` — always
possible since `stop < entry`), assume the **adverse leg fills last**: entered, then
stopped, a full-loss round trip that bar. On any position-holding bar that spans both
the stop and the time-exit close, the **stop fills first**. Optimistic orderings are
forbidden. This reuses `orb`'s validated intrabar-stop core semantics; no new engine
work expected.

### Exit (time — FROZEN, Open Question 6, resolved)

- If the stop has not fired, exit **MOC at the close of the 4th session of the hold**,
  where the fill session counts as session 1 (fill day `E` → exit at close of `E+3`).
  Rationale: the book says "take profits within 2–6 bars or trail"; 4 is the midpoint
  of the published window and a *fixed time exit with no trailing* is the
  least-parameterized reading (a trail adds a knob-rich sub-system; partial profits
  add another). One number, frozen ex-ante.
- No profit target in the baseline. The payoff is: tight stop, open-ended 4-session
  reversion window.

### Order/position state rules

- **One position or working entry order per instrument** at a time. A new setup on an
  instrument with an open position or live order is ignored.
- **No re-entry after a stop-out** (the book's "re-enter at the original price within
  the next two days" rule is excluded from the baseline — Open Question 7). The next
  *fresh* setup (a new setup-day bar satisfying all conditions) may trade.
- **Concurrency cap: 4 positions + pending orders combined** (Open Question 8). If
  more than 4 candidates compete for slots on the same day, priority is
  **alphabetical by ticker** — dumb, deterministic, unbiased; pre-registered so no
  discretionary selection can leak in.

## Risk

- **Position sizing (FROZEN)**: risk unit `R = 0.5%` of equity per trade
  (house standard), stop-distance sized:
  `shares = floor( min( (0.005·equity)/D , (0.25·equity)/entry_price ) )` —
  **per-position notional cap 25% of equity**; if `shares = 0`, skip the trade
  (never round risk up). With the 4-position cap, gross exposure ≤ 100% of equity;
  **no leverage.** Tight `D` (shallow sweeps) makes the notional cap bind often, so
  **realized R < 0.5% frequently**; the realized-R distribution is mandatory
  reporting and all R-multiples refer to realized risk (orb/keltner convention).
- **Max concurrent positions**: 4 (positions + pending entry orders).
- **Per-trade stop**: the setup-day-extreme stop above; broker-side from fill;
  worst-case ordering and gap-through-at-open in backtest.
- **Daily loss limit**: **2R (−1.0% of equity)** realized + mark-to-market, anchored
  at prior session close, via house `RiskManager.on_bar()` → **halt new entries** for
  the session; existing positions still managed to their stop/time exits. (A daily
  limit cannot un-gap an overnight gap; it stops the book from adding risk after one.)
- **Max drawdown kill switch (FROZEN): 15%** peak-to-trough equity — the house
  standard. Wider than orb/keltner's 10% because this book holds overnight and over
  weekends (gap risk is structural, not an execution failure); far tighter than
  tsmom's 20% because there is no vol-targeted-grind excuse here.
- **Haltable-tail argument (screen criterion, addressed explicitly).** (i) The
  stop-entry structure means **zero exposure during a waterfall**: in a 2008/2020-style
  cascade, price keeps making new lows without recovering the prior 20-day low, the
  buy stop never fills, and the order cancels after one session. (ii) Once filled, the
  worst case is an overnight gap through the stop on up to 4 concurrent positions,
  each capped at 25% notional — a 10% adverse gap on all four simultaneously (already
  an extreme, correlated-crash assumption for a basket spanning bonds/gold/dollar) is
  a −10% equity day, inside what a daily `halt_on_drawdown` at 15% can actually stop.
  No short-vol-style un-haltable termination structure exists: shorts are on ETFs with
  diversified underlyings and exchange halts, and are equally 25%-capped. The
  worst-single-trade ≤ 3R bar (Success criteria) verifies the provision empirically.
- **Reporting (LOCKED)**: per-trade gross/net P&L in bps and realized R;
  hit rate; exit-type split (stop / time); **long vs short split**; per-instrument and
  per-asset-class split; per-year means (decay visibility); penetration-depth (`D`)
  and realized-R distributions; entry-order fill rate; holding-day mark curve (P&L
  marked at hold days 1–6 — a diagnostic on the published 2–6 window, **never** a
  gate); concurrency/cluster stats; worst trade in R; max consecutive losses; gross
  vs net cost drag.

## Data requirements

- **Data types**: daily adjusted OHLCV per instrument. No quotes, news, or
  fundamentals. Exchange calendar with early closes (in core).
- **Source — already on hand**: the audited tsmom basket,
  `data/tsmom/<TICKER>_daily_adj.parquet` (gitignored), built by
  `scripts/build_tsmom_basket.py`: Yahoo split-adjusted raw OHLC + self-CRSP
  distribution adjustment applied to **all four price columns** (open/high/low/close),
  audited against Yahoo AdjClose (≤0.02 bps/day) and Alpaca SIP. Adjusted highs/lows —
  the Donchian inputs — exist and are covered by the audit. **Never** use Alpaca
  `adjustment=all` unaudited (house dividend-bug finding).
- **Adjustment materiality**: holds span ex-dates (multi-day, monthly-dividend ETFs
  in the basket), so total-return adjustment is load-bearing here — unlike the
  intraday books. Covered by the existing basket audit.
- **Small verification task (pre-declared, non-blocking)**: one check cell confirming
  the parquet files carry OHLC (not close-only) over the full range, that daily bars
  are session-close stamped (the fomc lesson: MOC never fires on mis-stamped daily
  bars — the builder writes canonical close-stamped UTC, so this should pass), and
  recording per-file `data_sha256` into the pregate config.
- **History depth**: common basket start 2007-03; first valid setup after the 20-day
  warm-up ⇒ signals from 2007-04. Windows below.
- **Reproducibility (house rule 5)**: every run records vendor, adjustment method,
  data range, per-file hashes, seed, git commit.

## Cost assumptions

Costs are mandatory (house rule 3), modeled in `core/backtest/costs.py`. Both entry
and protective-stop exits are **taker fills on stop orders that trigger with adverse
short-term momentum** — assume the spread is crossed every time, plus momentum
slippage. Basket-wide numbers follow the tsmom sign-off (1.5 bps half-spread covers
EEM/DBC/UUP, conservative for SPY/IEF).

- **Commission**: $0/share (Alpaca).
- **Half-spread**: **1.5 bps/side** (all fills).
- **Slippage**: stop-entry fill **+1.0 bps**; protective-stop fill **+1.5 bps**
  (stops fill into adverse momentum by construction); MOC time exit **+0.5 bps**
  (auction).
- **Round trips**: time exit ≈ 4.5 bps; stop exit ≈ 5.5 bps.
- **Short borrow (LOCKED)**: 50 bps/yr on short notional while held (GC ETFs;
  ~1 bp per 4-session short — modeled, not assumed zero).
- **LOCKED cost bar: 5.0 bps round trip** (blended), with the **pre-registered 1.5×
  companion (7.5 bps)** the OOS must survive.

**The arithmetic the result will be judged against.** Per-trade gross returns here
have σ plausibly ~100–200 bps (tight stop truncates the left tail at ≈ −D − slippage
except gaps; winners run 4 sessions). At an expected ~300–600 IS fills, the standard
error on the mean is ~5–10 bps — so an edge that merely *squeaks over* the 5.0 bps
cost bar is statistically indistinguishable from zero. House convention: **threshold
rules bind, t-stats are reported for honesty** — but a pass with |t| < 2 will be
called what it is in the pregate notes.

## Success criteria (locked before first backtest)

**FROZEN at sign-off 2026-07-10.** Every parameter (variant, basket,
20-day channel, 4-session separation, 1-tick offsets, 1-session order validity,
setup-extreme stop, 4-session time exit, no re-entry, sizing, caps, costs, windows)
is pre-registered as **one** configuration; nothing is ever swept, so there is
nothing to re-tune between IS and OOS.

### Matched-baseline definition (the anti-drift gate — pre-registered, the crux)

For each filled trade (instrument `i`, direction `d ∈ {+1,−1}`, holding length `h`
sessions from fill session to exit session), define its **matched baseline** as
`d × mean( close-to-close h-session return of instrument i over ALL sessions in the
scored window )` — same instrument, same direction, same holding clock,
unconditional timing. Deterministic (no random seed). Then

`EDGE = mean over trades of ( trade gross return − matched baseline term )`.

A long-at-20-day-lows rule that does not beat *being long that instrument for the
same number of days at random times* is drift plus noise (the arithmetic that killed
spx-swing and tsmom); a short leg is likewise credited for fighting drift. The
small clock mismatch (trades enter intraday at the stop level; the baseline is
close-to-close) is accepted and stated — it slightly *flatters* the strategy on the
entry leg and is common-mode across trades.

### PREGATE — pre-scoring gross-edge diagnostic (run FIRST, outside the engine)

Standalone `scripts/pregate_turtle_soup.py` (house pattern: pregate_orb / _keltner /
_tsmom) on `data/tsmom/*.parquet`, **IS window only; OOS and WF hard-sliced out
before any computation and never read.** Simulates the full rule — setup detection,
1-session stop-entry with gap-through-at-open, setup-extreme stop, 4-session MOC time
exit, LOCKED worst-case intraday ordering, concurrency cap with alphabetical
tie-break — and records signed **gross** per-trade returns in bps, plus every
diagnostic in the Risk reporting list.

**Gate rule (LOCKED before the script is written) — REJECT at spec validation if:**

1. **IS mean gross return per trade ≤ 5.0 bps** (the locked cost bar — the average
   trade must at least pay its own round trip), **or**
2. **EDGE(IS) ≤ 0** (gross, vs the matched baseline above — conditioning on the
   failed breakout must add value over unconditional same-direction drift), **or**
3. **IS filled trades < 200** — the setup is too rare to ever power the OOS bars
   (~9.75 IS years; <200 fills ⇒ the OOS minimum below is unreachable) ⇒
   inconclusive-reject.

t-stats reported; thresholds bind. On PASS: implement against core (daily-bar MOC
path + orb intrabar-stop core, both already built — no core extension expected,
flagged to verify), engine IS run must reproduce the pregate to rounding (the
orb/fomc cross-check pattern), then the **one** pre-registered OOS look + its
1.5×-cost companion. On FAIL: reject, no parameter/variant/universe shopping,
post-mortem in this file.

### Backtest bars (engine, net of the locked cost model; OOS window below)

| # | Proposed frozen bar |
|---|---|
| 1 | **OOS net zero-filled Sharpe ≥ 0.7** annualized (daily-bar episodic-exposure convention, matches fomc-drift) |
| 2 | **Net-positive expectancy per trade after costs; still net-positive at 1.5× costs (7.5 bps + 75 bps/yr borrow)** |
| 3 | **EDGE(OOS) > 0 net** — beats the matched same-instrument/direction/holding-clock baseline out of sample |
| 4 | **Both-sides gate**: net expectancy > 0 on longs *and* shorts separately in OOS, each side with ≥ 30 fills; a side with < 30 fills makes the gate unresolvable ⇒ inconclusive-reject (house lean: unresolved = fail) |
| 5 | **Max OOS drawdown ≤ 15%** peak-to-trough (consistent with the kill switch) |
| 6 | **Worst single trade ≤ 3.0·R realized** (breach ⇒ overnight-gap risk under-provisioned; wider than keltner's 2R because gaps are structural here) |
| 7 | **Minimum OOS trade count ≥ 150 filled trades** (below it the verdict is inconclusive-reject regardless of Sharpe) |
| 8 | **IS→OOS decay guard**: OOS net Sharpe not more than 50% below IS net Sharpe |

**No-rescue clause (LOCKED on approval):** per-instrument, per-asset-class, per-year,
long-only/short-only, and holding-day-curve splits are **diagnostics only — never
gates, never promotion paths.** A full-OOS fail cannot be rescued by dropping
instruments, keeping only the long side, changing the exit day inside the published
2–6 window, re-adding the book's re-entry rule, switching to the same-day variant, or
moving to futures. The original Turtle Soup same-day variant and the re-entry rule
are **out of scope entirely** (not even computed as diagnostics — each is one
resurrection door this lab has learned not to leave open).

### Windows (FROZEN)

- **In-sample: 2007-04-01 → 2016-12-31** (~9.75 yrs; first valid signals after the
  20-day warm-up on the 2007-03 basket). Contains the 2007 top, the 2008 cascade
  (the no-fill-in-waterfalls property gets tested where it matters), 2010/2011
  corrections, and the low-vol mid-decade.
- **Out-of-sample: 2017-01-01 → 2024-12-31** (8 yrs, sealed; one look ever).
  Contains Volmageddon 2018, COVID 2020, the 2022 bond/equity double bear.
- **Walk-forward: 2025-01-01 → present, unread until the OOS verdict.**
- Consistent with tsmom's windows on the same data files (IS ends 2016, OOS 2017–24,
  WF 2025→), so cross-strategy comparison is apples-to-apples.
- **What "working" looks like (declared now):** many small stop-outs near −1R
  realized, P&L carried by multi-day reversion winners; hit rate plausibly 40–55%;
  losing streaks and mid-single-digit drawdowns are normal operation. Failure is
  defined only by the locked bars above.

## Known failure modes

- **Negative skew via the stop tail (the keltner mode — named explicitly).** The
  published stop (1 tick beyond the setup-day extreme) is tight; shallow sweeps make
  `D` a few dozen bps. If the level gets re-tested noisily before reverting, the book
  bleeds full-R stop-outs whose mean overwhelms a positive median trade — **exactly
  how keltner-reversal died gross-negative (target 60% small wins, stop 37% large
  losses, mean in the tail).** *Bounding:* the pregate scores the **mean**, not the
  median, gross of costs, before any engine work; the exit-type split and realized-R
  distribution are mandatory reporting; worst-case intraday ordering forbids
  optimistic fills.
- **Crash continuation (the long-at-lows nightmare).** In 2008/2020, new 20-day lows
  kept coming. *Structural bound:* the stop-entry never fills while price keeps
  falling — exposure requires recovery through the prior low first; orders die after
  one session. *Residual:* fill on a dead-cat bounce, then gap through the stop
  overnight — bounded by gap-through-at-open accounting, 25% notional cap, 4-position
  cap, the 3R worst-trade bar, and the 15% kill switch. Mirror for shorts in melt-ups.
- **Post-publication decay (the ORB mode).** 30 years in print; the fade side is now
  itself retail orthodoxy. If the 1995 edge existed and has been arbed to zero on
  liquid ETFs, the expected result is EDGE ≈ 0 at the pregate or an OOS collapse
  after a nostalgic IS. *Bounding:* per-year reporting makes decay visible; the decay
  guard (bar 8) and the sealed lean-inclusive OOS refuse an IS-only story.
- **Drift masquerading as edge (the tsmom mode).** Buying weakness in
  secularly-rising equity ETFs "works" for beta reasons; a long-biased result is not
  the reversal hypothesis. *Bounding:* the matched-baseline EDGE gate (pre-registered
  at pregate **and** OOS) and the both-sides gate.
- **Costs in quiet tape.** Low vol ⇒ shallow penetrations ⇒ tiny `D` ⇒ per-trade
  gross shrinks toward the 5.0 bps bar while stop-outs stay full-cost. *Bounding:*
  the cost bar in the pregate, the 1.5× companion, penetration-depth-bucket
  reporting. No minimum-depth filter is added (a new parameter).
- **Signal clustering / correlated fills.** Risk-off puts several basket instruments
  at 20-day extremes simultaneously; 4 concurrent positions can be one macro bet.
  *Bounding:* the 4-slot cap, 25% notional cap, daily −2R halt, concurrency
  reporting; accepted residual, stated.
- **Intraday-path optimism (the backtest-lie mode).** Daily bars hide whether the
  entry or the stop hit first. *Bounding:* the LOCKED adverse-ordering rule (entered
  then stopped on any spanning bar; stop before time exit), reusing orb's validated
  core semantics.
- **Sample starvation.** Two filters (4-session separation + Plus-One close) on top
  of a 20-day extreme is rare by design; 8 instruments may still not produce 150 OOS
  fills. *Bounding:* pregate gate 3 kills it cheaply in-sample before any engine work.

## Open questions — RESOLVED (sign-off record)

**User sign-off 2026-07-10: all 12 resolved to the recommended defaults** (the lab's
8th recommend-first session). The numbered items below are preserved verbatim as the
decision record; every "Recommend" reads as "Frozen."

1. **Variant.** *Recommend **Turtle Soup Plus One*** (next-day entry) — the only
   variant with clean daily-bar semantics; the same-day original requires intraday
   data or path assumptions. Cost: fewer fills, and the freshest failures (same-day
   snap-backs) are excluded.
2. **Universe.** *Recommend the existing **8-ETF tsmom basket*** — zero new data
   work, audited adjusted OHLC, multi-asset like the futures the rule was written
   for, and the only route to sufficient trade count. Alternatives: SPY-only
   (cheapest, but the most efficient instrument alive and an in-house graveyard) or
   futures (matches the source exactly, but requires a futures pipeline the lab
   refused to build for tsmom).
3. **Entry offset.** *Recommend **1 tick ($0.01)** above/below the prior 20-day
   extreme.* The book says 5–10 *futures* ticks (≈5–10 bps on the 1995 S&P); there is
   no canonical penny-ETF translation, and a bps-based offset would be an invented
   parameter. 1 tick is minimal and matches the rule as commonly quoted for
   equities.
4. **Entry-order validity.** *Recommend **session s+1 only*** (cancel at its close),
   mirroring the original's "good for today only." Alternative: valid s+1 and s+2
   (more fills, weaker freshness). One must be frozen; s+1-only is the tighter
   reading.
5. **Stop reading.** *Recommend **1 tick beyond the setup-day extreme** (`L_s − 0.01`
   / `H_s + 0.01`).* The book's "one tick below today's low" most plausibly refers to
   the setup/breakout day. Alternative reading (below the lowest low up to the fill
   day) is nearly always the same level here given the 1-session validity.
6. **Time exit.** *Recommend **MOC at the close of hold-session 4** (fill day = 1),
   no trailing, no partial profits.* The book's "2–6 bars, trail" is a range plus a
   knob-rich sub-system; 4 is the midpoint frozen ex-ante. Any other single value in
   2–6 is defensible — pick one now, never revisit.
7. **Re-entry rule.** *Recommend **exclude*** the book's "re-enter at the original
   price within 2 days after a stop-out." It adds a state machine and a second
   free choice; excluded entirely (not even a diagnostic — no resurrection door).
8. **Concurrency + sizing caps.** *Recommend **4 concurrent positions/orders, 25%
   notional cap per position, R = 0.5% equity, alphabetical tie-break**.* Gross ≤
   100%, no leverage. The tie-break is arbitrary by design (deterministic,
   unbiased); any alternative (deepest penetration, highest vol) is a new parameter.
9. **Kill switch & daily limit.** *Recommend **15% kill switch** (house standard;
   overnight-gap book) and **−2R daily → halt new entries**.*
10. **Windows.** *Recommend **IS 2007-04→2016-12 / OOS 2017-01→2024-12 / WF
    2025-01→*** — aligned with tsmom on the identical data files.
11. **Cost model.** *Recommend **5.0 bps locked RT bar** (1.5 half-spread + 1.0–1.5
    slippage per side, MOC 0.5) + 50 bps/yr short borrow; 1.5× companion 7.5 bps.*
12. **Success-bar set.** *Recommend as written*: OOS zero-filled Sharpe ≥ 0.7;
    net-positive at 1× and 1.5× costs; EDGE(OOS) > 0; both-sides gate (≥30/side);
    DD ≤ 15%; worst trade ≤ 3R; ≥ 150 OOS fills; decay ≤ 50%; pregate gates
    (gross > 5.0 bps, EDGE(IS) > 0, ≥ 200 IS fills). **Freezes at sign-off, before
    the pregate script is written.**

**Next step per the funnel (criteria now frozen):** small data-verification cell →
`scripts/pregate_turtle_soup.py` on the IS window only, outside the engine; OOS and
WF stay sealed.

## Post-mortem — REJECTED at pregate, 2026-07-10 (11th candidate death)

Run: `scripts/pregate_turtle_soup.py` on IS 2007-04 → 2016-12 only (OOS/WF hard-sliced
out before any computation, never read). Results + trade log in
`experiments/turtle-soup/2026-07-10-pregate/`. Git at run: db05fb7 (spec frozen first).

**Gate outcome (rule locked before the script existed):**

| Gate | Bar | Result | Verdict |
|---|---|---|---|
| 1. IS mean gross/trade | > 5.0 bps | **−12.40 bps** (t = −1.44) | **FAIL** |
| 2. EDGE(IS) vs matched drift baseline | > 0 | **−12.78 bps** | **FAIL** |
| 3. IS filled trades | ≥ 200 | 399 | pass |

**Failure mode: the pre-named keltner mode, on cue.** 62% of fills die on the stop
(same-bar −70, later-touch −103, overnight gap −128 bps means); the 38% that reach the
4-session MOC average +111 bps — but the stop tail owns the mean. Median trade −37 bps,
hit rate 31%, max 14 consecutive losses.

**The deeper kill — there is no signal, not just bad stop geometry.** The hold-day mark
curve *ignoring the stop entirely* is negative at every horizon 1–6 (−0.7 … −11.7 bps):
after a Plus-One failed breakout in this universe, no multi-day reversion drift exists
for any exit inside the published 2–6 window. The tight stop doesn't ruin a good
signal; it truncates a non-signal. EDGE ≈ mean gross because the matched drift
baselines are ~0.4 bps — conditioning on the failed breakout adds nothing over
unconditional same-direction exposure.

**Robust to intrabar ordering — in both directions.** The diagnostic-only
optimistic-ordering ceiling (spanning entry bars survive; physically unattainable)
scores **−13.1 bps, slightly worse**: trades that dodge the same-bar stop mostly gap
through it overnight instead (stop-gap fills 45 → 117, mean −154 bps). The locked
worst-case rule was not what killed it.

**Splits (diagnostics only — the no-rescue clause binds):** both sides negative (long
−7.5 / short −17.5 bps); equities worst (−24.9), bonds +5.0 on n=100 (noise); every
year 2008–2013 negative, 2007/2014/2016 mildly positive — no live sub-edge anywhere,
and reading one in would be forbidden regardless.

**Reading:** consistent with the adversarial prior stated above — 30 years
post-publication, both sides of the trade crowded, daily mean reversion on liquid US
ETFs dead in-house (now 0-for-4 as a family: rsi-5050, keltner-reversal, orb's long
side, turtle-soup). Cost of this death: one session, zero engine code.

**Data-verification finding (recorded for future basket consumers):** the tsmom
parquets carry full non-null OHLC (pass, hashes in the results JSON) but are
midnight-ET date-stamped, **not** session-close stamped — irrelevant to this pregate
(pure date indexing) but the engine's daily-MOC path would have required the fomc-mode
re-stamp had this survived.

**Infrastructure that survives:** `scripts/pregate_turtle_soup.py` — the lab's first
multi-instrument stop-order/position/slot simulator on daily bars (setup → armed
order → gap-aware stop fills → worst-case ordering → concurrency cap), reusable for
any future order-driven daily-bar pregate. Expected outcome per the lab's base
rate (11 candidates, 10 deaths, adjacent families 0-for-3): rejection at the cost bar
or the matched-baseline gate — a fine outcome that costs one session and no engine
code.
