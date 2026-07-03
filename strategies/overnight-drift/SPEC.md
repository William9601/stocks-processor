# Strategy: overnight-drift

- **Status**: retired
- **Created**: 2026-07-03
- **One-liner**: Trade the full documented equity-index "night effect" decomposition on two ETFs (SPY and QQQ) — **long the overnight session** (close→open) and **short the intraday day session** (open→close) — betting that index returns accrue overnight while the intraday session is flat-to-negative, gated by a risk-on trend regime filter.
- **Implementation**: `strategies/overnight-drift/strategy.py` (+ `config.yaml`,
  `config.qqq.yaml`, `tests/`), on the shared core. Required an additive core change —
  market-on-close fills (`FillTiming.NEXT_CLOSE`) in `core/{strategy,execution/broker,
  backtest/engine,backtest/costs}.py`; `intraday-momentum`'s `NEXT_OPEN` path is
  byte-identical (28 tests pass).
- **Result — REJECTED (2026-07-03)**: Failed every locked criterion on real Alpaca SIP
  data, both instruments and both windows. Net Sharpe −2.00/−2.47 (SPY IS/OOS),
  −1.76/−1.96 (QQQ IS/OOS); net return ~−13% each; max DD hit the 15% kill switch.
  Quant-reviewer validated it is **not a bug** (no lookahead in the MOC path, correct
  leg handoff, honest costs). Cause: the overnight-long premium is real gross (SPY
  +3–5, QQQ +6 bps/day) but ~fully eaten by the conservative modeled auction cost
  (~7 bps/leg), and the **intraday-short leg has no gross edge (negative in QQQ) and is
  the entire net loss**. Rejected at spec-validation, not tuned, per the adversarial
  note. Runs: `experiments/overnight-drift/2026-07-03-{1826-spy,1827-qqq}-{is,oos}/`.

## Hypothesis

**Effect.** For major equity indices, the close-to-open ("overnight") return has
historically been positive and has accounted for essentially all of the index's total
return, while the open-to-close ("intraday") return has been flat-to-negative over long
samples. This strategy trades the **full decomposition**: **long the overnight leg**
(close→open) *and* **short the intraday leg** (open→close). The long overnight leg
captures the documented positive night drift; the short intraday leg captures the
documented flat-to-negative day return. This is the "night effect" / overnight drift
documented by Cliff, Cooper & Gulen (2008, "Return Differences between Trading and
Non-Trading Days") and reinforced by later work (e.g., Lou, Polk & Skouras 2019, "A
Tug of War"; Bogousslavsky 2021). The overnight/intraday return decomposition has been
robustly documented across SPY, QQQ, and international index ETFs.

**The two legs are not equally robust — and the short leg is the weaker bet.** The
long-overnight leg is the well-documented, risk-premium-backed half. The
**short-intraday leg is materially more fragile**: over 2010–2024 the equity market's
*unconditional* intraday drift has at times been positive, not negative (the "flat-to-
negative day" is a long-sample and regime-conditional average, not a stable law), and
shorting the day session fights the daytime dip-buying/retail bid and can be violently
squeezed on strong trend-up days. We short the day leg because it completes the
decomposition and lets us *measure* whether the intraday half still contributes — **not
because we are confident it is independently profitable.** The spec therefore tracks the
two legs' P&L separately (see Risk / reporting) so we can see if the edge is
one-legged, and the entry-gate regime filter (below) exists partly to keep the short leg
out of exactly the risk-on trend-up tape that punishes it hardest.

**Mechanism — why it exists and who is on the other side.** This is a market-level,
non-cross-sectional effect, so the story must be about aggregate flow and risk-bearing,
not stock-picking. Several non-exclusive channels:

1. **Overnight risk premium (the primary story).** The overnight period carries real,
   un-hedgeable gap risk: the market is closed for ~17.5 hours during which macro news,
   overseas moves, and after-hours earnings can gap the open. Leveraged,
   risk-averse, and mandate-constrained intraday participants (day traders, some
   market makers, levered funds under overnight margin/financing charges) systematically
   *shed* exposure into the close and re-establish it after the open, to avoid holding
   overnight. Whoever is willing to *bear* that close-to-open gap risk earns a premium
   for providing it. We are volunteering to hold the risk they are paying to offload.
   The counterparty is structural and price-insensitive (they de-risk on a schedule /
   mandate, not on expected value), which is why the premium can persist.

2. **Order-flow / liquidity-demand imbalance at the open.** The opening auction absorbs
   a night's worth of accumulated retail and institutional buy interest (overnight limit
   orders, pre-market news reactions, index-fund creation flow). Documented buy-pressure
   at/after the open lifts the open print relative to the prior close.

3. **Return-of-the-day-timing effects.** ETF and index rebalancing, dividend
   reinvestment, and short-covering flows have historically clustered around the open,
   contributing a positive close-to-open drift that is mechanically separate from
   intraday supply/demand.

**Why it might persist — and why it might not.** The risk-premium channel (1) is the
most durable: bearing overnight gap risk is a genuine, un-diversifiable exposure, and
being paid for it is not an arbitrage that closing capital erases — it is compensation
for a risk that is really there (and shows up as fat left-tail gap-down days). But:

- The effect is **publicly documented since 2008** and heavily popularized; a naive
  "buy-close/sell-open SPY" is one of the most well-known retail anomalies and is a
  prime candidate for decay.
- Several studies find the overnight premium **weakened or concentrated in specific
  sub-periods and specific instruments** (e.g., stronger in QQQ/tech and small-caps than
  in SPY; time-varying and even negative in some post-2018 windows).
- The premium is **not free**: it is compensation for tail risk, so a backtest Sharpe
  overstates the lived experience unless drawdown and gap-day behavior are examined
  directly.

**Adversarial note.** Overnight drift is a known, published, popularized effect. This is
a **replication-and-survival test, not a novel edge.** The sibling strategy
(intraday-momentum) was a known published effect that turned out to be *absent* in SPY
2018–2024 and was correctly rejected at spec-validation rather than tuned. We must hold
this idea to the same standard: the OOS bar (below) is pre-locked, and **if net-of-cost
OOS Sharpe does not clear it, the correct outcome is reject-at-spec-validation, not
tuning an entry filter until the curve turns up.** In particular, the raw
overnight-vs-intraday decomposition (both legs, before any regime gating) should be
computed as a diagnostic *before* the gated strategy is scored — if the raw close-to-
open premium and/or the raw open-to-close short leg are ~0 or negative net of costs in
the OOS window, there is nothing to tune toward. Both instruments (SPY and QQQ) are
declared and bar-set before backtest #1, judged against the *same* locked criteria, and
**reported separately — never pooled and never fished sequentially** (we do not run SPY,
see it fail, and then go shopping in QQQ). The regime gate, sizing, fill model, and cost
model below are **all pre-registered and will not be re-tuned** after seeing results;
re-tuning them turns a replication test into a curve-fit.

## Universe & timeframe

- **Instruments (LOCKED): BOTH SPY and QQQ** — two pre-registered instruments, no basket,
  no cross-sectional selection.
  - **SPY** (S&P 500 ETF). We already hold clean SPY 5-min SIP data 2018–2024 from the
    sibling strategy, so it is the zero-friction, most liquid, tightest-spread vehicle.
    Downside: SPY is exactly where the effect is most-arbitraged and where recent studies
    find the overnight premium weakest.
  - **QQQ** (Nasdaq-100 ETF). Literature generally finds the overnight premium
    **stronger and more persistent** in tech/growth (QQQ) than in SPY, at a modestly
    wider spread. **Data prerequisite:** QQQ requires a comparable 5-min RTH history pull
    (2018–present, same schema/vendor as SPY) *before* it is bar-set — this pull is a
    hard blocker on backtest #1 for QQQ (see Data requirements).
  - **Pre-registration discipline (LOCKED):** SPY and QQQ are **both declared and
    bar-set against the same locked success criteria before the first backtest.** QQQ is
    a co-equal pre-registered instrument, **NOT a fallback to fish in after SPY fails.**
    Results are **judged and reported separately, per instrument — never pooled, never
    run sequentially to cherry-pick a winner.** Each must independently clear its own
    (identical) bar to count.
  - Execution path is **Alpaca** (equities/ETFs), so both instruments are directly
    paper-/live-tradeable end to end. No futures vehicle is in scope.
- **Bar size / data resolution**: Signals require only two daily prints — the RTH
  **closing** price and the next RTH **opening** price. We use 5-minute RTH bars as the
  canonical source (reuse the sibling's schema): the close print is the close of the
  15:55→16:00 bar; the open print is the open of the 09:30→09:35 bar. Daily
  close/open bars are equivalent and may be used, but 5-min lets us model
  auction-adjacent slippage and inspect the last/first bar explicitly.
- **Trading session (hours, timezone)**: US regular session, 09:30–16:00 ET. All
  timestamps are ET. Both auction prints (open, close) are traded; the intraday
  day-session short is held *within* RTH. Overnight (Globex / pre-market / after-hours)
  bars are **not** traded and are **not** used for signals — the overnight leg is simply
  held flat through the closed market. Early-close days (half-days, 13:00 ET close) use
  that day's actual RTH close print (see Data / calendar handling).
- **Holding period — two chained legs per 24h cycle:**
  1. **Long overnight leg, ~17.5 hours.** Enter long at the RTH close on day *d* (MOC);
     exit at the RTH open on day *d+1* (MOO). **Un-stoppable** — the market is closed for
     the duration, so this leg has no intraday stop by construction.
  2. **Short intraday leg, ~6.5 hours.** Immediately at the same day-*d+1* open (MOO),
     flip to short for the day session; exit (cover) at that day's RTH close (MOC). This
     leg **can and does carry an intraday stop** (see Signals / Risk).
  The two legs share the open auction as a hinge: at each RTH open the book covers the
  overnight long and opens the day short in one turn. This strategy **deliberately
  violates the lab's usual "flat by the close / intraday-only" convention** on the
  overnight leg — that is the entire point, confronted head-on in Risk / Failure modes.
  One instrument, one directional position at a time per instrument; SPY and QQQ run as
  independent books.

## Signals

**A signal at time T uses only data timestamped strictly before T.** No same-bar fill,
no `.shift(-1)`, no use of the print we transact on to decide the transaction. Every
fill is a locked MOC/MOO auction fill (see Fill model), and every decision is committed
using data strictly before the print it fills at.

**Definitions (per trading day d):**

- `Close(d)` = official RTH closing (auction) price of day *d*.
- `Open(d+1)` = official RTH opening (auction) price of the next trading day.
- **Overnight (long) return** per cycle: `Open(d+1) / Close(d) - 1`, gross, before costs.
- **Intraday (short) return** per cycle: `-(Close(d+1) / Open(d+1) - 1)`, gross, before
  costs (short leg profits when the day session falls).
- `SMA200(d)` = simple moving average of the **daily RTH closing prices** over the 200
  most recent completed trading days **up to and including day *d***, dividend/split
  adjusted (see Data). Computed causally from daily closes; on the decision day *d* the
  value uses `Close(d)` and 199 prior closes — all known before the 16:00 print we act on
  because the MOC decision is committed *before* the close (see Fill model / no-lookahead).

**Entry gate (LOCKED, pre-registered causal trend/regime filter):**

- **Rule:** hold the cycle (long overnight AND short intraday) **only when day *d*'s RTH
  close is at or above its 200-day SMA** — i.e., `Close(d) ≥ SMA200(d)` (risk-on regime).
  When `Close(d) < SMA200(d)` (risk-off), **sit out entirely: no overnight long is
  entered that night and no day short is entered the following morning.**
- **Single fixed parameter (200-day SMA). This gate is pre-registered and will NOT be
  re-tuned** — we do not sweep the lookback (50/100/150/200) and pick the best; 200 is a
  standard, widely-used long-trend threshold chosen a priori. Sweeping it would convert
  the replication into a curve-fit and is explicitly disallowed.
- **The gate governs BOTH legs symmetrically (LOCKED).** Rationale: the overnight
  premium is a risk-on phenomenon (it is compensation for bearing equity gap risk, which
  is best rewarded in uptrends), and — critically — the **short intraday leg is most
  dangerous in strong risk-on tape**, precisely the regime this gate would *keep us in*.
  Making the gate symmetric means we only short the day session in risk-on regimes, which
  is where the short leg is *most* likely to be squeezed. We accept this deliberately:
  the symmetric gate is the honest, single-parameter choice, and the short-leg P&L is
  tracked separately so its regime behavior is fully visible. (An asymmetric variant —
  gate the long on risk-on, gate the short on risk-*off* — is plausibly better for the
  short leg but adds a second regime rule and a second parameter; it is **not** adopted
  in v1 to preserve the single-parameter pre-registration. Flagged only, not a baseline.)
- **Causality:** `SMA200(d)` uses only completed daily closes ≤ day *d*; the decision is
  committed before the 16:00 print. No lookahead.

**Leg 1 — Long overnight entry (MOC at close of day *d*):**

- **Direction:** long. **Fill:** market-on-close (MOC) into day *d*'s closing auction,
  filling at auction-slippage-adjusted `Close(d)`.
- **No-lookahead argument for the MOC cutoff:** the MOC order (and the gate decision that
  authorizes it) must be **committed before the exchange MOC submission cutoff
  (~15:50–15:59 ET)**, using only data available strictly before the cutoff. In the
  backtest this means the gate is evaluated on the **last completed daily close and the
  200-day SMA as of the prior close, plus the current day's price observed no later than
  the cutoff** — the order is *placed* before the closing print exists and merely *fills*
  at the auction price. We do NOT read the 16:00 closing print to decide whether to
  submit the order; that would be using the fill price to make the trade. Because the gate
  compares `Close(d)` to `SMA200(d)`, and `Close(d)` is not yet known at 15:50–15:59, the
  **decision uses the last-observed price at/just before the cutoff (e.g., the 15:45 or
  15:55 bar) as the proxy for `Close(d)`** in the causal implementation; any tiny drift
  between the cutoff proxy and the 16:00 print is a modeled fill uncertainty, not signal
  lookahead. This must be implemented as an explicit pre-cutoff decision, and any code
  path that evaluates the gate on the final 16:00 close before deciding to submit is a
  lookahead bug to be flagged in review.
- **No profit target, no discretionary early exit, and no intraday stop on this leg** —
  the market is closed; the position cannot be reduced, hedged, or stopped for ~17.5h. A
  gap-down open is realized in full. Overnight-leg risk is controlled purely at the
  sizing/kill-switch level (see Risk), never by a stop that could not fill in reality.

**Leg 1 exit / Leg 2 entry (the open hinge, MOO at open of day *d+1*):**

- At the RTH open of day *d+1*, a single MOO turn **covers the overnight long and opens
  the intraday short**, both filling at auction-slippage-adjusted `Open(d+1)`.
- If the gate was risk-off at day *d*'s cutoff, neither leg exists and there is no turn.

**Leg 2 — Short intraday, exit & stop:**

- **Time exit (cover):** market-on-close (MOC) at day *d+1*'s closing auction, filling at
  auction-slippage-adjusted `Close(d+1)`. The short is always flat by the close.
- **Intraday stop (LOCKED in mechanism, level flagged for final glance):** unlike the
  overnight leg, the day-short leg CAN be stopped and MUST be. Place a **hard intraday
  stop at `Open(d+1) · (1 + s)` on the upside** (a rising day session is adverse to a
  short), with baseline stop distance **`s = 1.0 · ATR%_20d`**, where `ATR%_20d` is the
  trailing 20-day average true range expressed as a percentage of price (causal, computed
  from daily bars ≤ day *d*), floored at **`s ≥ 0.75%`** and capped at **`s ≤ 3%`** to
  keep sizing sane on very quiet/very wild tape. If the intraday high crosses the stop,
  model the fill at the stop level plus conservative stop slippage (assume stop → market
  order; see Cost). Stop is fixed at the open (not trailing). *Baseline `s` needs a final
  user glance; the existence of an ATR/%-based intraday stop on the short leg is LOCKED.*
- **Precedence:** intraday stop takes precedence over the time exit; if neither fires the
  short covers at the MOC close. No pyramiding, no re-entry after a stop-out that day.

## Fill model (LOCKED: MOC / MOO auction fills)

All entries and exits transact in the **primary listing auctions**, never mid-session:

| Event | Order type | Fills at | Modeled auction slippage |
|---|---|---|---|
| Overnight long entry (close, day *d*) | **MOC** | `Close(d)` | heavier than a mid-session bar |
| Overnight long exit + intraday short entry (open, day *d+1*) | **MOO** | `Open(d+1)` | heaviest (gappiest print) |
| Intraday short exit / cover (close, day *d+1*) | **MOC** | `Close(d+1)` | heavier than a mid-session bar |
| Intraday short stop hit | stop → market | stop level | conservative stop slippage |

- **MOC submission cutoff & no-lookahead (LOCKED, restated):** every MOC order and the
  gate decision authorizing it are **committed before the ~15:50–15:59 ET MOC cutoff**,
  using only data available strictly before the cutoff (the closing print does not yet
  exist when the order is placed). The order *fills* at the auction print but is *decided*
  on the pre-cutoff proxy price; no code path may read the 16:00 close to decide whether
  to submit. See the detailed argument in Signals → Leg 1 entry. Any evaluation of the
  gate on the final close before submission is a lookahead bug for review to flag.
- **Auction slippage is modeled conservatively on both gappy prints** — heavier than the
  sibling's mid-session fills — because auction prints reflect accumulated imbalance and
  can print far from the prior indicative. Concrete bps are in Cost assumptions; the
  opening (MOO) leg is penalized hardest by design.
- **Live-contingency fallback (NOT the scored baseline):** if MOC/MOO are unavailable in
  live, a last-bar/first-bar fill is the degraded substitute, but the **scored backtest
  uses auction fills only**, and any run must record which fill model it used.

## Risk

The two legs have **different stop realities and are therefore sized differently.** The
overnight long has no stop (market closed) and is sized to a survivable gap budget; the
intraday short does have a stop and is sized to that stop distance, exactly like the
sibling. Both legs sit inside book-level circuit breakers. Sizing is delegated to
`core/risk`.

- **Baseline risk unit: `R = 0.5%` of equity per leg** (baseline, matches sibling;
  flagged for a final glance). The two legs are sized independently, so a single 24h
  cycle budgets up to ~`R` on the overnight leg and up to ~`R` on the intraday leg.
- **Leg 1 (overnight long) sizing — gap budget:** size so a worst-plausible adverse
  overnight gap `G` costs `R` of equity, where
  `G = max(3 · σ_overnight_20d, 5%)` (`σ_overnight_20d` = trailing 20-day realized stdev
  of close-to-open returns, causal). Then
  `shares_overnight = floor( (R · equity) / (G · Close(d)) )`, capped so notional ≤ equity
  (no leverage). If notional cap and gap-budget disagree, the **tighter** (gap-budget)
  binds. Baseline `G` formula flagged for a final glance.
- **Leg 2 (intraday short) sizing — stop distance:** size so the intraday stop distance
  `s · Open(d+1)` (per Signals) costs `R` of equity:
  `shares_short = floor( (R · equity) / (s · Open(d+1)) )`, capped so notional ≤ equity.
  This mirrors the sibling's `R / (stop distance)` rule. The two legs' share counts are
  computed separately and are generally **not** equal.
- **Max concurrent positions**: 1 directional position per leg per instrument. SPY and
  QQQ are independent books, each running its own overnight+intraday pair.
- **Per-trade stops**:
  - **Overnight leg: NO stop (impossible — market closed).** Effective loss cap is the
    gap budget `R` under a `G`-sized gap; a gap larger than `G` overshoots `R` and is a
    real, explicitly-accepted tail risk, monitored by the kill switches below.
  - **Intraday short leg: hard stop at `s` above the open (per Signals).** This is the
    risk unit the short-leg sizing targets — the day leg *is* stoppable, so it is stopped.
- **Per-cycle loss limit**: a single realized cycle loss worse than **2 · R** (either leg
  overshooting its budget — an overnight gap ~2× `G`, or a stop gap-through on the short)
  triggers **halt-and-review**: no new entries until manually inspected. Baseline flagged.
- **Max drawdown kill switch**: halt and require manual review if peak-to-trough equity
  drawdown exceeds **15%** (baseline, matches sibling, flagged). The realistic path here
  is a sustained regime that hurts *both* legs at once — e.g., a strong risk-on trend that
  the 200-SMA gate keeps us *in*, feeding the overnight long but repeatedly squeezing the
  day short.
- **Event nights**: baseline = **no event filter** (do not skip FOMC/CPI/NFP/election
  nights), but **tag event nights in reporting** so their contribution to the tail is
  isolable. Flagged for a final glance.
- **Reporting (LOCKED — decompose everything):** track P&L, hit rate, and the **full
  return distribution separately for the long-overnight leg and the short-intraday leg**
  (like the sibling tracks long vs. short), plus the combined cycle. Surface the left
  tail (worst 1% of nights / days), **worst single-night overnight loss**, stop-out rate
  on the short leg, and behavior bucketed by regime, event-night tag, and long-weekend/
  half-day tag. A high combined Sharpe that is actually **one-legged** (all from the
  overnight leg, with the short leg flat-to-negative) must be visible, not hidden — that
  is a specific, expected outcome we are testing for.

## Data requirements

- **Data types**: RTH OHLCV bars sufficient to extract the official **close** print of
  day *d*, the **open** print of day *d+1*, and the intraday high (for short-leg stop
  detection). 5-min RTH bars are canonical (closing/opening **auction prints** preferred
  over last/first 5-min bar for fill realism). Additionally, **daily RTH bars** are
  required to compute the causal `SMA200(d)` regime gate and `ATR%_20d` short-leg stop.
  No quotes/news/fundamentals needed. An exchange **market calendar with early-close
  days** is required so half-day closes (13:00 ET) use the correct close print, and so
  the ~65-hour long-weekend holds are identified and tagged.
- **History depth**: 2018–present for the trade windows (IS 2018–2021, OOS 2022–2024,
  walk-forward 2025→), **plus a ≥200-trading-day daily-close warm-up before the first
  tradeable day (i.e., daily closes from ~mid-2017)** so `SMA200` is fully populated on
  the first IS day — no partial-window SMA, no shrinking lookback at the start.
  - **SPY:** 5-min 2018–2024 already on hand; daily closes for the 2017 warm-up must be
    confirmed present.
  - **QQQ (data prerequisite / blocker):** a comparable **QQQ 5-min RTH history pull
    (2018–present) plus 2017 daily-close warm-up**, same vendor/schema as SPY, must be
    completed **before** QQQ is bar-set. Until this pull exists, QQQ cannot enter
    backtest #1, and the pre-registration requires both instruments bar-set together.
  - Longer pre-2018 history would strengthen regime coverage but is not required for v1.
- **Source**: Split by stage, same as sibling.
  - **Execution (paper → live): Alpaca.** Full SIP data (Algo Trader Plus tier) for
    trustworthy prints; free IEX feed is prototype-only. Alpaca supports MOC/MOO order
    types — the fill model below **depends** on them, so submission cutoffs and auction-
    fill behavior must be validated on the paper account before any live consideration.
  - **Backtest: a historical bar provider** (Alpaca SIP export, Polygon, or Databento —
    vendor TBD, flagged) exported to parquet and loaded via `core/data` on the canonical
    UTC/OHLCV schema. Every experiment records vendor, symbol, adjustment method, data
    range, seed, and git commit.
  - **Dividend/split adjustment convention (LOCKED in intent, mechanism flagged):**
    prices are **split- and dividend-adjusted** on a single consistent basis across the
    whole series. Critically, **an ETF ex-dividend date creates a mechanical overnight
    (close→open) price drop that is NOT overnight alpha and must NOT be counted as such.**
    On ex-div dates the overnight-leg return is computed on the **adjusted** series (or the
    dividend is added back to the raw gap), so the distribution reflects the ex-div drop as
    ~0 economic move, not a loss. Ex-div dates are additionally **tagged in reporting**.
    The precise adjustment mechanism (adjust-in-place vs. add-back) is flagged for a final
    glance, but the requirement that ex-div gaps are not credited/debited as alpha is
    locked.
  - *Flagged: which historical vendor for the backtest.*

## Cost assumptions

Costs are mandatory and modeled on every backtest (commission + spread + slippage).

**Turnover has doubled vs. the original single-leg draft — say so honestly.** Trading the
full decomposition means **~2 round-trips per day, not one**: one overnight round-trip
(MOC in, MOO out) and one intraday round-trip (MOO in, MOC out), all hinging on the two
auction prints. Every RTH open now carries a *double* auction cross (cover the long AND
open the short in the same MOO). So the **low-turnover advantage that was the core
selling point vs. the retired MIM strategy is partly given back.** We are back to ~2
round-trips/day — the same order of turnover that helped kill MIM at ~13% cost drag —
except every fill is at the two *gappiest, most auction-driven* prints of the day, which
is where slippage is worst. This is a real headwind and the cost model must be trusted to
expose it: **the net edge, per leg and combined, must clear roughly double the original
draft's cost floor.** If the short leg's gross edge does not exceed its own round-trip
cost, the short leg is a cost-drag anchor and should show up as such in the separated P&L.

Baseline for **SPY / QQQ on Alpaca** (implemented in `core/backtest/costs.py`,
configured in `config.yaml`):

- **Commission**: **$0/share** — Alpaca equities are commission-free.
- **Half-spread**: **1.0 bps** per side for SPY, **1.5 bps** per side for QQQ (QQQ's
  spread runs slightly wider). Deliberately conservative vs. the sub-1bp penny spread in
  liquid RTH.
- **Slippage — modeled higher at the auction than the sibling's intraday fills:**
  - **MOC (closing auction), both the overnight entry and the short cover: 2.0 bps.**
    Deep auction, but our order is a price-taker into it.
  - **MOO (opening auction), the double cross (cover long + open short): 3.0 bps per
    side.** The **opening print is the gappiest, least-certain fill of the session** — a
    night of accumulated imbalance, and it must be crossed **twice** here (once to exit
    the long, once to enter the short). This leg is penalized hardest; if the edge only
    survives with a generous open fill, it does not survive.
  - **Short-leg stop exit: 3.0 bps** (stops are adverse / gap-through, per sibling).
- **Round-trip cost is now ~2 cycles' worth**: order of **~12–18 bps/day** across both
  legs (vs. ~6–9 bps/cycle single-leg), reported **per leg and combined** so the short
  leg's cost burden is not hidden inside the long leg's premium.
- Spread + slippage are pushed against the trade direction in the fill price and tracked
  as explicit dollars, so `cost_drag`, `gross_return`, and `net_return` are reported per
  leg and combined. A result reported without these costs is not a valid result.

## Success criteria (locked before first backtest)

Defensible bars, **locked before backtest #1 and pending a final user sign-off** so they
cannot be moved afterward. **Applied identically and separately to SPY and QQQ** — each
instrument must clear every bar on its own; results are never pooled or cherry-picked
across the two. Because overnight drift is a known, popularized, possibly decayed effect
and the short leg is the weaker half, the OOS bar is modest but must clear the (now
doubled) costs *and* survive tail scrutiny.

- **Pre-gating decomposition diagnostic (run FIRST, before scoring the gated strategy):**
  compute the **raw overnight-vs-intraday return decomposition — both legs, ungated —**
  on each instrument. If the raw close→open premium net of auction costs is ~0/negative,
  or the raw open→close short leg net of costs is ~0/negative, in the OOS window, there is
  nothing for the gate to tune toward and the honest outcome is reject-at-spec-validation
  (exactly how the sibling MIM was rejected when its raw correlation came in ~0).
- **Minimum OOS Sharpe (net of all costs)**: **≥ 0.7** annualized on 2022–2024, for the
  **combined two-legged strategy per instrument.** (Flagged for sign-off; same level/
  rationale as the sibling.)
- **Benchmark gate (LOCKED as a gate, level flagged):** the combined strategy must **beat
  buy-and-hold of the same ETF on net Sharpe** over the OOS window. If it merely matches
  buy-and-hold's risk-adjusted return, it adds nothing for its operational and tail risk
  and is rejected.
- **Maximum drawdown tolerated (OOS)**: **≤ 15%** peak-to-trough, consistent with the
  kill switch. **Additionally**, the **worst single-night overnight loss (OOS) must be
  ≤ ~2 · R** of equity in the realized path; a breach means gap sizing is under-
  provisioning even if Sharpe passes.
- **Per-leg decomposition is diagnostic, not a pass/fail gate.** We do **not** require
  both legs to be individually profitable — we are explicitly testing whether the edge is
  one-legged. The combined net result is what is scored. **However:** if the combined
  strategy only clears the bar because the overnight long carries a cost-dragging short
  leg, dropping the short leg is a **new pre-registration** (re-declare and re-lock the
  criteria), not a post-hoc rescue of this spec.
- **Minimum trade count**: not the binding constraint — even with the 200-SMA risk-on
  gate cutting risk-off stretches, the OOS window should retain **≥ 250 gated cycles**;
  below that the Sharpe estimate is inconclusive regardless of level.
- **Additional gates**: net positive expectancy per cycle after costs; OOS Sharpe not
  more than ~50% below IS Sharpe (large IS→OOS decay = the effect is fading in real time).
- **In-sample window**: 2018–2021.  **Out-of-sample window**: 2022–2024.
  **Walk-forward**: 2025→present; walk-forward numbers are the ones that count for a
  paper-trading decision. The 200-SMA gate, sizing, fills, and costs are **frozen** across
  all three windows — no re-tuning between IS and OOS.

## Known failure modes

Regimes where this should lose, and what limits the damage:

- **Strong risk-on trend-up days squeeze the short leg (the signature two-legged risk).**
  The symmetric 200-SMA gate keeps us **in** during uptrends — feeding the overnight long,
  but also forcing the day short into exactly the risk-on tape where the intraday session
  grinds *up*, not down. A run of strong-up days bleeds the short leg (stopped out near
  the highs) even while the long leg profits, netting to a one-legged or negative result.
  *Mitigation:* the intraday `s`-stop caps each short-day loss to ~`R`; per-leg P&L
  reporting exposes a bleeding short leg immediately; and the pre-gating decomposition
  diagnostic will already have flagged if the raw day-short edge is ≤0 before we commit.
  This is the most likely way the *short* leg fails, and it is not hidden.
- **Regime-gate whipsaw near the 200-SMA.** When price oscillates around its 200-day SMA,
  the gate flips on/off across successive days, entering and exiting the market repeatedly
  and paying the (doubled) auction cost each time for little directional payoff.
  *Mitigation:* the gate is a single fixed rule (no hysteresis band added — that would be
  a second tuned parameter); cost drag from whipsaw is fully modeled and reported, and
  chop regimes are visible in the regime-bucketed reporting. Accepted as a known weak spot.
- **Bear markets / sustained down-open regimes.** The overnight premium is compensation
  for gap risk, so it is *supposed* to lose exactly when that risk materializes — clusters
  of gap-down opens (2018 Q4, Mar 2020, 2022 bear) hit a long-overnight book directly and
  cannot be stopped intraday. *Partial offset:* the 200-SMA risk-on gate should sit the
  book out through much of a confirmed downtrend (price below SMA), and in a downtrend the
  short leg is on the *right* side. But whipsaw entries at regime transitions, and gap-
  downs that occur while still above the SMA, remain exposed. *Mitigation:* gap-budgeted
  sizing, `2·R` per-cycle halt-review, 15% drawdown kill switch, regime-tagged reporting.
- **The un-stoppable overnight gap (tail).** A single overnight event (flash macro
  shock, geopolitical weekend, after-hours index-mover) can gap the open well beyond `G`,
  realizing more than `R` in one uncontrollable move. *Mitigation:* conservative `G`,
  no-leverage cap, worst-single-night criterion above. **Event nights (FOMC/CPI/NFP/
  elections): baseline = no filter (we hold), but event nights are TAGGED in reporting**
  so their outsized contribution to the tail is isolable. Accept that this tail cannot be
  fully removed while holding overnight.
- **Decayed / arbitraged premium (most likely quiet failure).** Post-2018 studies find
  the SPY overnight premium weak or absent in some windows, and the intraday-negative
  half is even less stable; the raw close→open long and/or the raw open→close short, net
  of the (doubled, heavier) auction slippage, may simply be ~0. *Mitigation:* pre-locked
  OOS Sharpe + benchmark gate + the raw pre-cost, **two-leg** decomposition diagnostic
  *before* scoring the gated strategy force an honest reject — exactly as the sibling MIM
  was rejected when its raw correlation came in ~0.
- **Auction-fill slippage worse than modeled.** The open print is genuinely uncertain;
  if real MOO fills are worse than 3 bps in stressed opens, the thin edge evaporates.
  *Mitigation:* intentionally heavy open-leg slippage in the cost model; validate against
  Alpaca paper auction fills before trusting the backtest.
- **Dividend / distribution ex-dates.** ETF ex-dividend dates create a mechanical
  overnight price drop that is *not* alpha and would corrupt overnight-return stats if
  counted. *Mitigation:* consistent dividend adjustment convention, and flag ex-dates in
  reporting; do not credit or debit the strategy for the ex-div gap.
- **Early-close / half-day sessions and long weekends.** Non-standard sessions (13:00 ET
  closes, day-before-holiday drift) have different dynamics and longer holds (over a
  3-day weekend the "overnight" is ~65 hours with proportionally more gap risk).
  *Mitigation:* market-calendar-aware close/open prints; **baseline = hold these longer
  cycles normally, but TAG the ~65h long-weekend/half-day holds in reporting** so their
  gap contribution is isolable (flagged for a final glance).
- **MOC/MOO mechanics failing in live.** If the MOC submission cutoff is missed or the
  auction rejects the order, the real fill diverges from the backtest's auction print —
  and this strategy crosses the *open* auction twice per day (cover + short), so open-
  auction failure hits both legs at once. *Mitigation:* the last-bar/first-bar fill is a
  degraded live substitute only (never the scored baseline), validated on Alpaca paper
  before any live consideration; paper-before-live per CLAUDE.md.

## Baselines pending a final user glance (do not block bar-setting)

These carry a stated baseline-with-rationale above and are pre-registered; they are
listed here only so the user can veto/adjust *before* criteria are frozen for backtest
#1. The four LOCKED design decisions (both instruments SPY+QQQ; long-overnight +
short-intraday; symmetric 200-SMA risk-on gate; MOC/MOO auction fills) are **not** on
this list — they are fixed.

1. **Sizing:** `R = 0.5%` equity per leg; overnight gap budget `G = max(3·σ_overnight_20d,
   5%)`; day-short stop distance `s = 1.0·ATR%_20d`, floored 0.75%, capped 3%.
2. **Circuit breakers:** per-cycle `2·R` halt-and-review; 15% peak-to-trough drawdown
   kill switch.
3. **Success bars:** OOS net Sharpe ≥ 0.7; OOS max DD ≤ 15%; worst single-night loss
   ≤ ~2·R; must beat buy-and-hold on net Sharpe; ≥ 250 gated OOS cycles; IS 2018–2021 /
   OOS 2022–2024 / walk-forward 2025→.
4. **Event nights (FOMC/CPI/NFP/elections):** no filter (hold), but tag in reporting.
5. **Long-weekend / half-day (~65h) holds:** hold normally, but tag in reporting.
6. **Dividend adjustment mechanism:** adjust-in-place vs. add-back (either is acceptable;
   the *requirement* that ex-div gaps are not counted as overnight alpha is locked).
7. **Backtest data vendor:** TBD (Alpaca SIP export / Polygon / Databento).
8. **QQQ 5-min + 2017 daily-close pull:** a hard data prerequisite before QQQ is bar-set
   (not a judgment call, but the gating dependency for backtest #1).
```
