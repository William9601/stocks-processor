# Strategy: overnight-long

- **Status**: PAPER (QQQ gated only) — user-approved 2026-07-03, first session planned 2026-07-06; all 4 blocking fixes landed and re-judged 2026-07-04 (verdict v3); paper gate pre-registered below
- **Created**: 2026-07-03
- **One-liner**: Harvest the equity-index overnight risk premium with a single leg — buy a liquid index ETF at the regular-session close (MOC) and exit at the next open (MOO), gated by a risk-on 200-day-SMA regime — deliberately dropping the structurally-edgeless intraday-short leg that sank the retired overnight-drift strategy.
- **Implementation**: `strategies/overnight-long/strategy.py` (+ 4 configs: SPY/QQQ ×
  gated/ungated, `tests/`), on the shared core (reuses the MOC/MOO machinery built for
  overnight-drift; no new core code). Data is dividend+split adjusted (`*_adj.parquet`,
  via the new `fetch_data.py --adjustment all`) — mandatory for a long-only overnight book.
- **Result v3 — blocking fixes landed, 15:40 decision bar re-judged; candidacy STANDS
  (2026-07-04)**: All four v2 blockers are fixed in core (zero-filled Sharpe headline +
  `sharpe_trade_days` legacy field; live every-bar 2·R day-lock; calendar-aware sessions
  with phantom half-day bars filtered at load; MOC fills only on the session-final bar).
  The decision bar moved 15:55 → 15:40 (`decision_offset_minutes: 20`, offsets from the
  true session close — 12:40 on half-days) to respect Alpaca's ~15:45 MOC submission
  cutoff; isolation runs show the time shift itself is neutral (≤0.004 Sharpe, mixed
  sign). Re-judged suite (`experiments/overnight-long/2026-07-04-0923-t1540-*`, master
  verdict in `...-t1540-qqqgate-wf-evcost/notes.md`): IS 0.7749 zero-fill / 0.8420
  trade-days; **OOS 0.5516 / 0.6734 — still below the 0.7 bar, slightly weaker than v2
  because phantom fills were removed and half-days now trade (honest corrections, not
  tuning)**; walk-forward 2025-01→2026-07 **1.0749 / 1.1306, net +1.68%, DD −1.03%,
  still net-positive at the locked 7 bps** — the WF continues to carry the candidacy.
  Promoted to paper per the pre-registered gate below.
- **Result v2 — BORDERLINE OOS, WALK-FORWARD-CARRIED; qualified paper candidate, QQQ
  gated only (2026-07-03)**: The execution-cost study recommended below was run
  (pre-registered method: `experiments/execution-cost-study/2026-07-03-2319-spy-qqq-auction/`)
  and measured real MOC/MOO round-trip cost at **SPY 2.03 / QQQ 2.90 bps** vs the
  ~7 bps assumption. Re-judged on identical params/windows/bars. Quant-reviewer
  (TRUST-WITH-CAVEATS) then found the engine's Sharpe **excludes gate-flat days** from
  the denominator: QQQ-gated OOS reads 0.715 under the engine convention but **0.584
  zero-filled — below the 0.7 bar**; cost-vintage sensitivity brackets it further
  (0.65 at pre-WF costs / 0.82 at OOS-period-matched). **The OOS result is honestly
  BORDERLINE, not a pass.** What carries the candidacy is the untouched
  **2025-01→2026-07 walk-forward: Sharpe 1.14 engine / 1.08 corrected, net +1.7%,
  DD −1.0%, net-positive even at the old locked 7 bps** — robust across every check
  thrown at it (it ~ties, does not beat, QQQ B&H's 1.12 there, with −1.0% vs −22.8%
  DD; the B&H gate is OOS-only and passes: 0.584 vs 0.503). Other OOS bars pass:
  expectancy +1.5%, DD 1.6%, worst night ≈1.1·R, decay −15%, 498 cycles. No lookahead;
  no goalposts moved; SPY gated stays REJECTED (OOS 0.34). Full scorecard + caveats:
  `experiments/overnight-long/2026-07-03-2323-qqqgate-wf-evcost/notes.md` (verdict v2).
  **Blocking prerequisites before paper**: dead 2·R limit fix; calendar-aware sessions
  (incl. phantom half-day 16:00 bars found in the data); Alpaca MOC-cutoff (~15:50)
  vs 15:55 decision-bar fix + re-run; metrics.py zero-filled-Sharpe fix; explicit user
  sign-off. **Auto-reject tripwire in paper:** measured fill cost > ~4–5 bps RT or
  odd-lot auction ineligibility → back to REJECT.
- **Result v1 — REJECT on locked criteria, but GROSS-PROFITABLE & cost-gated (2026-07-03)**:
  Unlike the two retired siblings, the overnight premium is **real and gross-positive in
  all 8 runs** (+1.3% to +7.0%), with small drawdown (2–5%). Net is ~breakeven (IS ≈ 0,
  OOS negative) — the entire gap is the conservative ~7 bps auction-cost assumption. Fails
  the locked OOS net-Sharpe ≥ 0.7 bar, so **rejected at the locked cost — not tuned**.
  BUT the cost-sensitivity diagnostic shows **QQQ-gated clears 0.7 Sharpe in BOTH IS and
  OOS at ≤ 3 bps round-trip** (break-even ~6.5 bps both windows); SPY is weaker/decayed
  OOS. Quant-reviewer validated the premium is causal and reproduced outside the engine —
  no lookahead. **Recommended follow-up: a separately-specified execution-cost study** to
  measure real SPY/QQQ MOC/MOO slippage; if ≤ ~3 bps, this becomes a paper candidate.
  Runs: `experiments/overnight-long/2026-07-03-2105-*` (master verdict in `qqqgate-oos/`).

## Hypothesis

**Effect.** For major equity indices the close-to-open ("overnight") return has
historically been positive and has accounted for essentially all of the index's total
long-run return, while the open-to-close ("intraday") return has been flat-to-negative
over long samples. This is the documented "night effect" / overnight drift (Cliff,
Cooper & Gulen 2008; Lou, Polk & Skouras 2019; Bogousslavsky 2021). **This strategy
trades ONE leg of that decomposition: the long overnight leg only.** Buy the ETF at the
RTH close, hold through the closed market, sell at the next RTH open. No intraday leg, no
short, ever.

**Mechanism — why it exists and who is on the other side.** This is a market-level,
aggregate-flow effect, not stock-picking. The primary and most durable channel is an
**overnight risk premium**: the market is closed ~17.5 hours, during which macro news,
overseas moves, and after-hours earnings can gap the open. Leveraged, risk-averse, and
mandate-constrained intraday participants (day traders, some market makers, levered funds
carrying overnight margin/financing charges) systematically *shed* exposure into the close
and re-establish it after the open, to avoid holding the gap. Whoever *bears* that
close-to-open gap risk earns a premium for providing it. The counterparty de-risks on a
schedule / mandate, not on expected value, which is why the premium can persist rather
than being competed away — it is **compensation for a real, un-diversifiable tail
exposure** (fat left-tail gap-down days), not an arbitrage that arriving capital erases.
Secondary channels: documented buy-pressure absorbed by the opening auction (overnight
limit orders, pre-market news reactions, index-fund creation flow), and open-clustered
ETF/index rebalancing, dividend-reinvestment, and short-covering flows.

**Why this is a NEW, separately pre-registered hypothesis — NOT a tune of the parent.**
The retired `overnight-drift` strategy traded the *full* decomposition (long overnight +
short intraday) and was rejected on real Alpaca SIP data, both instruments and both
windows (net Sharpe −2.0 to −2.5). Its rejection notes
(`experiments/overnight-drift/2026-07-03-1826-spy-oos/notes.md`) established two
*independent, empirically-decomposed* facts:

1. The **overnight-long leg alone** was ~breakeven-to-slightly-negative under
   deliberately-conservative auction costs (gross close→open drift SPY +3–5 bps/day,
   QQQ +6 bps/day; net ~0 after ~7 bps/round-trip). Its per-leg dollar P&L was small
   (SPY OOS −$2,484, QQQ OOS −$939) — a rounding error next to the short leg.
2. The **intraday-short leg had no gross edge** (≈0 on SPY, *negative* on QQQ, whose
   intraday session drifted up 2018–2024) and was **the entire net loss** (SPY OOS
   −$10,606, QQQ OOS −$11,755).

Dropping the short leg is therefore justified by an **ex-ante mechanism argument, not
parameter-fishing**: the overnight risk premium is a genuine, theory-backed
risk-compensation channel; the intraday short had *no mechanism* offered at spec time and
*no gross edge* in the data. Removing a leg that has no hypothesized source of return and
that empirically carried the whole loss is not curve-fitting — it is deleting a component
that never had a hypothesis. **What is NOT inherited is any claim that this will pass.**
Everything else (the OOS bar, the cost floor, the pre-gating diagnostic) is
**pre-registered fresh** and must stand on its own.

**Adversarial note — this may, and honestly *should*, land as a mild reject.** The parent
finding is unambiguous: the overnight-long leg was **~breakeven under the locked
conservative auction costs on the two cleanest, most-arbitraged ETFs.** Removing the
short leg removes a *loss*, but it does not *manufacture* a premium that the data says is
already ~fully eaten by cost. So the base-rate expectation for this strategy is
**near-breakeven → mild reject**, and *a clean near-breakeven reject is a valid, honest,
useful result, not a failure to be tuned away.* The specific decay risk is severe and
must be stated plainly:

- The effect is **publicly documented since 2008** and heavily popularized; "buy-close /
  sell-open SPY" is among the most well-known retail anomalies and a prime decay candidate.
- Post-2018 studies find the SPY overnight premium **weak, absent, or negative** in
  sub-windows; it is stronger in QQQ/tech but still time-varying.
- The premium is compensation for tail risk, so backtest Sharpe *overstates* the lived
  experience unless drawdown and gap-day behavior are examined directly.

If net-of-cost OOS Sharpe does not clear the pre-locked bar, **the correct outcome is
reject-at-spec-validation — not tuning the SMA lookback, not softening the cost model,
not shopping across instruments.** The raw ungated overnight-premium decomposition
(below) is computed as a diagnostic *first*; if the raw close→open premium net of costs is
~0/negative in the OOS window, there is nothing to tune toward and the strategy is
rejected exactly as the sibling MIM and the parent overnight-drift were.

## Universe & timeframe

- **Instruments (LOCKED): BOTH SPY and QQQ** — two pre-registered instruments, no basket,
  no cross-sectional selection, **judged and reported SEPARATELY, never pooled, never run
  sequentially to cherry-pick a winner.**
  - **SPY** (S&P 500 ETF). Clean 5-min SIP data 2018–2024 already on hand
    (`data/SPY_5m.parquet`) plus daily bars from 2017-06 (`data/SPY_daily.parquet`) for
    the 200-SMA / gap-vol warm-up. Most liquid, tightest-spread vehicle; also where the
    overnight premium is most-arbitraged and recent studies find it weakest.
  - **QQQ** (Nasdaq-100 ETF). Data already on hand: `data/QQQ_5m.parquet` (2018–2024) and
    `data/QQQ_daily.parquet` (2017-06→2024). Literature generally finds the overnight
    premium **stronger and more persistent** in tech/growth (QQQ), consistent with the
    parent's per-leg gross (+6 bps/day QQQ vs +3–5 SPY) — at a modestly wider spread.
  - **Pre-registration discipline (LOCKED):** both instruments are declared and bar-set
    against the **same identical locked criteria before backtest #1.** QQQ is co-equal,
    **NOT a fallback to fish in after SPY fails.** Each must independently clear its own
    (identical) bar to count.
  - Execution path is **Alpaca** (equities/ETFs); both are directly paper-/live-tradeable.
    No futures vehicle in scope.
- **Bar size / data resolution**: Signals require only two daily prints per cycle — the
  RTH **closing** price and the next RTH **opening** price. 5-minute RTH bars are the
  canonical source (reuse the sibling schema): the close print is the close of the
  15:55→16:00 bar; the open print is the open of the 09:30→09:35 bar. Daily close/open
  bars are equivalent and may be used, but 5-min lets us model auction-adjacent slippage
  and inspect the last/first bar explicitly. Daily RTH bars are additionally required for
  the causal `SMA200(d)` gate and `σ_overnight_20d` sizing input.
- **Trading session (hours, timezone)**: US regular session, 09:30–16:00 ET; all
  timestamps ET. Only the two RTH auction prints are traded. Overnight (Globex /
  pre-market / after-hours) bars are **not** traded and **not** used for signals — the
  position is simply held flat through the closed market. Early-close days (half-days,
  13:00 ET close) use that day's actual RTH close print (see Data / calendar handling).
- **Holding period — ONE overnight leg per cycle (overnight allowed, by design):** enter
  long at the RTH close on day *d* (MOC); exit at the RTH open on day *d+1* (MOO). Hold
  ~17.5 hours through the closed market; over a 3-day weekend the hold is ~65 hours. This
  strategy **deliberately violates the lab's usual "flat by the close / intraday-only"
  convention** — holding overnight *is* the entire point, confronted head-on in Risk /
  Failure modes. One long position at a time per instrument; SPY and QQQ run as
  independent books. **No intraday position of any kind is ever held.**

## Signals

**A signal at time T uses only data timestamped strictly before T.** No same-bar fill, no
`.shift(-1)`, no use of the print we transact on to decide the transaction. Every fill is
a locked MOC/MOO auction fill (see Fill model), decided on data strictly before the print
it fills at.

**Definitions (per trading day d):**

- `Close(d)` = official RTH closing (auction) price of day *d*.
- `Open(d+1)` = official RTH opening (auction) price of the next trading day.
- **Overnight (long) return** per cycle: `Open(d+1) / Close(d) - 1`, gross, before costs.
- `SMA200(d)` = simple moving average of the **daily RTH closing prices** over the 200
  most recent completed trading days **up to and including day *d***, dividend/split
  adjusted (see Data). Computed causally from daily closes.

**Entry gate (LOCKED, pre-registered causal trend/regime filter — single fixed
parameter):**

- **Rule:** enter the overnight long **only when the most recent COMPLETED daily close
  (strictly before today) is at or above its 200-day SMA** — i.e., risk-on regime. When
  the most recent completed close is below its 200-day SMA (risk-off), **sit out
  entirely: no overnight long is entered that night.**
- **Single fixed parameter (200-day SMA). Pre-registered, will NOT be re-tuned** — no
  sweep over 50/100/150/200 and pick the best. 200 is a standard, widely-used long-trend
  threshold chosen a priori. Sweeping it converts the replication into a curve-fit and is
  explicitly disallowed.
- **Rationale:** the overnight premium is compensation for bearing equity gap risk, which
  is best rewarded in risk-on uptrends; the gate keeps the book out of confirmed
  downtrends where clustered gap-down opens hit a long-overnight book hardest.
- **Causality — MOC-cutoff argument (LOCKED):** the MOC order and the gate decision
  authorizing it are **committed before the exchange MOC submission cutoff (~15:50–15:59
  ET)**, using only data strictly before the cutoff; the closing print does not yet exist
  when the order is placed. Because the gate compares against `SMA200` computed on the
  **last COMPLETED daily close (day *d−1* or earlier) — strictly before today** — the
  gate value is fully known at the cutoff with zero dependence on the 16:00 print we fill
  at. The order is *placed* pre-cutoff and merely *fills* at the auction price. We do NOT
  read the 16:00 close to decide whether to submit; **any code path that evaluates the
  gate on the same-day 16:00 close before deciding to submit is a lookahead bug to be
  flagged in review.** (This is a deliberately stricter, cleaner causal definition than the
  parent's "cutoff-proxy price" formulation: gating on the *prior completed* close removes
  the proxy-drift ambiguity entirely.)

**Entry — overnight long (MOC at close of day *d*):**

- **Direction:** long. **Fill:** market-on-close (MOC) into day *d*'s closing auction,
  filling at auction-slippage-adjusted `Close(d)`.
- **No profit target, no discretionary early exit, and NO intraday stop** — the market is
  closed; the position cannot be reduced, hedged, or stopped for ~17.5h (~65h over a
  weekend). A gap-down open is realized in full. Overnight risk is controlled purely at the
  sizing / kill-switch level (see Risk), never by a stop that could not fill in reality.

**Exit — overnight long (MOO at open of day *d+1*):**

- **Fill:** market-on-open (MOO) into day *d+1*'s opening auction, filling at
  auction-slippage-adjusted `Open(d+1)`. **Always flat by ~09:30:05 ET; no intraday
  position is carried.**
- If the gate was risk-off at day *d*'s cutoff, no position was entered and there is no
  exit.

## Fill model (LOCKED: MOC / MOO auction fills)

All entries and exits transact in the **primary listing auctions**, never mid-session:

| Event | Order type | Fills at | Modeled auction slippage |
|---|---|---|---|
| Overnight long entry (close, day *d*) | **MOC** | `Close(d)` | heavier than a mid-session bar |
| Overnight long exit (open, day *d+1*) | **MOO** | `Open(d+1)` | heaviest (gappiest print) |

- **MOC submission cutoff & no-lookahead (LOCKED, restated):** every MOC order and the
  gate decision authorizing it are committed before the ~15:50–15:59 ET cutoff, gated on
  the **last completed daily close vs its 200-day SMA** (strictly before today), so no
  same-day closing print is used to decide the trade. See Signals → Entry gate.
- **Auction slippage modeled conservatively on both gappy prints** — heavier than the
  sibling's mid-session fills — because auction prints reflect accumulated imbalance and
  can print far from the prior indicative. Concrete bps are in Cost assumptions; the
  opening (MOO) leg is penalized hardest by design.
- **Cost model carried forward UNCHANGED from the parent (LOCKED, do not move
  goalposts):** identical auction-cost assumptions so this strategy's net numbers are
  **directly comparable** to the parent's overnight leg. See Cost assumptions.
- **Live-contingency fallback (NOT the scored baseline):** if MOC/MOO are unavailable
  live, a last-bar/first-bar fill is the degraded substitute, but the **scored backtest
  uses auction fills only**, and every run records which fill model it used.

## Risk

The overnight long has **no stop** (market closed) and is sized to a survivable gap
budget, inside book-level circuit breakers. Sizing is delegated to `core/risk`.

- **Baseline risk unit: `R = 0.5%` of equity per trade** (matches parent; flagged for a
  final glance).
- **Sizing — gap budget (LOCKED mechanism, baseline flagged):** size so a worst-plausible
  adverse overnight gap `G` costs `R` of equity, where
  `G = max(3 · σ_overnight_20d, 5%)` and `σ_overnight_20d` = trailing 20-day realized
  stdev of close-to-open returns (causal, from daily bars ≤ day *d*). Then
  `shares = floor( (R · equity) / (G · Close(d)) )`, capped so notional ≤ equity (**no
  leverage; `resting_stop = false`**). If the notional cap and the gap budget disagree,
  the **tighter (gap-budget) binds.**
- **Max concurrent positions**: 1 long position per instrument. SPY and QQQ are
  independent books.
- **Per-trade stop**: **NONE — impossible, the market is closed.** The effective loss cap
  is the gap budget `R` under a `G`-sized gap; a gap larger than `G` overshoots `R` and is
  a **real, explicitly-accepted tail risk** (see Failure modes), monitored only by the
  kill switches below. This is the single most important risk fact about this strategy and
  is confronted directly rather than papered over with an un-fillable "overnight stop."
- **Per-cycle loss limit**: a single realized cycle loss worse than **2 · R** (an
  overnight gap ~2× `G`) triggers **halt-and-review**: no new entries until manually
  inspected. Baseline flagged.
  - **CORE BUG FIXED (2026-07-04):** the `2·R` limit was historically dead for
    sparse-order strategies (`size()` ran only on order-emitting bars, so day-start
    equity was captured after the morning exit realized the overnight loss). Fixed in
    core: `RiskManager.on_bar()` now runs on **every** bar (backtest engine and live
    runner), and each day anchors at the **prior session's closing equity**, so an
    overnight gap loss realized at the open counts against that day's `2·R` lock.
    Covered by `core/tests/test_risk.py`. (It never fires in the judged windows — worst
    night ≈1.1·R — so the fix changes no backtest numbers.)
- **Max drawdown kill switch**: halt and require manual review if peak-to-trough equity
  drawdown exceeds **15%** (baseline, matches parent, flagged). Realistic path: a cluster
  of overnight gap-down opens in a still-risk-on tape (price above the 200-SMA when the
  gap hits), or repeated whipsaw entries at regime transitions.
- **Event nights**: baseline = **no event filter** (hold FOMC/CPI/NFP/election nights),
  but **tag event nights in reporting** so their contribution to the tail is isolable.
  Flagged for a final glance.
- **Reporting (LOCKED — decompose everything):** track P&L, hit rate, and the **full
  overnight-return distribution**; surface the **worst single-night overnight loss**, the
  left tail (worst 1% of nights), and behavior bucketed by regime (on/off), event-night
  tag, and long-weekend/half-day (~65h) tag. Because there is only one leg, the headline
  net Sharpe is the leg — but the **raw ungated overnight premium** (gross and net,
  regime-on vs all-days) is reported as the pre-gating diagnostic below.

## Data requirements

- **Data types**: RTH OHLCV bars sufficient to extract the official **close** print of
  day *d* and the **open** print of day *d+1* (closing/opening **auction prints**
  preferred over last/first 5-min bar for fill realism). Additionally **daily RTH bars**
  for the causal `SMA200(d)` gate and `σ_overnight_20d` sizing. No quotes/news/
  fundamentals, and no intraday high needed (no intraday stop). An exchange **market
  calendar with early-close days** is required so half-day closes (13:00 ET) use the
  correct close print and long-weekend (~65h) holds are identified and tagged.
- **History depth**: 2018–2024 for the trade windows (IS 2018–2021, OOS 2022–2024;
  walk-forward 2025→ when data arrives), **plus a ≥200-trading-day daily-close warm-up
  before the first tradeable day** so `SMA200` is fully populated on day 1 of IS — no
  partial-window SMA.
  - **SPY:** `data/SPY_5m.parquet` (2018–2024) + `data/SPY_daily.parquet` (2017-06→2024,
    warm-up). On hand.
  - **QQQ:** `data/QQQ_5m.parquet` (2018–2024) + `data/QQQ_daily.parquet` (2017-06→2024,
    warm-up). On hand. **Both instruments' data are present — QQQ is NOT a blocker for
    backtest #1** (unlike the parent, whose QQQ pull was a prerequisite).
- **Source**:
  - **Execution (paper → live): Alpaca.** Full SIP data (Algo Trader Plus tier). Alpaca
    supports MOC/MOO order types — the fill model **depends** on them; submission cutoffs
    and auction-fill behavior must be validated on the paper account before any live
    consideration.
  - **Backtest:** parquet already on hand (Alpaca SIP), loaded via `core/data`. Every
    experiment records vendor, symbol, adjustment method, data range, seed, and git commit.
  - **Dividend/split adjustment convention (LOCKED in intent, mechanism flagged, status
    UNCONFIRMED):** an ETF **ex-dividend date creates a mechanical overnight (close→open)
    price drop that is NOT overnight alpha and must NOT be counted as such.** On ex-div
    dates the overnight return must be computed on a **dividend-adjusted basis** (or the
    dividend added back to the raw gap) so the ex-div drop reads as ~0 economic move, not
    a loss; ex-div dates are additionally **tagged in reporting.** **The dividend-adjust
    status of the on-hand Alpaca parquet is UNCONFIRMED** — this must be verified before
    backtest #1, because on a long-only overnight strategy an unadjusted ex-div gap is a
    systematic negative bias on exactly the return we are measuring (~4 ex-div dates/year
    × the distribution's dividend, biasing the overnight premium *down*). Whether to
    adjust-in-place vs add-back is flagged; the requirement that ex-div gaps are neither
    credited nor debited as alpha is locked.

## Cost assumptions

Costs are mandatory and modeled on every backtest (commission + spread + slippage).
**Carried forward UNCHANGED from the parent overnight-drift so net results are directly
comparable** — the parent's overnight-long leg was **~breakeven under exactly these
costs**, so keeping them identical is the whole point of comparability and is explicitly
**not** to be softened to make this strategy pass.

Baseline for **SPY / QQQ on Alpaca** (in `core/backtest/costs.py`, configured in
`config.yaml`):

- **Commission**: **$0/share** — Alpaca ETFs are commission-free.
- **Half-spread**: **1.0 bps** per side (SPY and QQQ). Deliberately conservative vs the
  sub-1bp penny spread in liquid RTH.
- **Slippage — modeled higher at the auction than mid-session fills:**
  - **MOC (closing auction) entry: 2.0 bps** (`close_slippage_bps = 2.0`).
  - **MOO (opening auction) exit: 3.0 bps** (`slippage_bps = 3.0`). The opening print is
    the gappiest, least-certain fill of the session; penalized hardest by design. If the
    edge survives only with a generous open fill, it does not survive.
- **Round-trip cost ≈ 1 cycle**: order of **~6–7 bps/day** (half-spread both sides + 2 bps
  MOC + 3 bps MOO). This is **HALF the parent's ~12–18 bps/day**, because dropping the
  short leg removes one full round-trip (and the *double* open-auction cross). Lower
  turnover is the one honest mechanical improvement over the parent — but note the parent's
  overnight leg was *already* modeled at this ~6–7 bps and *still* came in ~breakeven, so
  the cost reduction does not by itself create an edge.
- Spread + slippage are pushed against trade direction in the fill price and tracked as
  explicit dollars, so `cost_drag`, `gross_return`, and `net_return` are reported per run.
  A result without these costs is not a valid result.
- **Cost-sensitivity DIAGNOSTIC (explicitly a diagnostic, NOT a pass/fail gate, NOT a knob
  to tune until green):** additionally report the **break-even auction-slippage level** —
  i.e., holding the model structure fixed, at what per-side MOO/MOC slippage does the net
  overnight premium cross zero. This tells us *where the line is* relative to the locked
  6–7 bps assumption and relative to plausibly-lower real Alpaca fills (the parent noted
  real MOC/MOO slippage is plausibly sub-bp). **It does NOT change the pass/fail verdict:**
  the strategy is scored at the locked costs above, full stop. The break-even level is
  reported to inform a *future, separately-specified* execution-cost study, not to rescue
  this spec.

## Success criteria (locked before first backtest)

Defensible fresh bars, **locked before backtest #1 and pending a final user sign-off** so
they cannot be moved afterward. **Applied identically and separately to SPY and QQQ** —
each must clear every bar on its own; results are never pooled or cherry-picked. Given the
parent's finding that this leg is ~breakeven under the locked costs, **a near-breakeven
reject is an expected and honest outcome, not a failure to be tuned away.**

- **Pre-gating decomposition diagnostic (run FIRST, before scoring the gated strategy):**
  compute the **raw ungated overnight premium** (close→open return, gross AND net of the
  locked auction costs, **regime-on vs all-days**) on each instrument, IS and OOS. If the
  raw close→open premium net of costs is ~0/negative in the OOS window, there is nothing
  for the gate to tune toward and the honest outcome is **reject-at-spec-validation** —
  exactly how the sibling MIM was rejected (raw correlation ~0) and how the parent
  overnight-drift was rejected (raw net premium ~0). This diagnostic is computed *outside*
  the engine on daily bars as an independent cross-check of the engine result.
- **Minimum OOS Sharpe (net of all costs)**: **≥ 0.7** annualized on 2022–2024, per
  instrument. (Flagged for sign-off; kept at the parent's level for comparability.)
- **Net-positive expectancy after costs**: mean net return per cycle > 0, per instrument.
- **Benchmark gate (LOCKED as a gate, level flagged):** must **beat buy-and-hold of the
  same ETF on net Sharpe** over the OOS window. A long-only overnight strategy that merely
  matches buy-and-hold's risk-adjusted return adds nothing for its operational and tail
  risk (and buy-and-hold captures the overnight premium *plus* the intraday return for
  zero turnover) — so this gate is especially demanding here and is deliberately kept.
- **Maximum drawdown tolerated (OOS)**: **≤ 15%** peak-to-trough, consistent with the kill
  switch. **Additionally**, the **worst single-night overnight loss (OOS) must be ≤ ~2·R**
  of equity in the realized path; a breach means gap sizing is under-provisioning even if
  Sharpe passes.
- **Minimum trade count**: **~NON-BINDING** — the strategy holds most nights (only risk-off
  stretches are skipped), so the OOS window retains **≥ 250 gated cycles** comfortably.
  Trade count is not the limiting statistical constraint here; the *effect size vs cost* is.
- **IS→OOS decay guard**: OOS Sharpe not more than ~50% below IS Sharpe (large decay = the
  effect is fading in real time).
- **In-sample window**: 2018–2021. **Out-of-sample window**: 2022–2024. **Walk-forward**:
  2025→present when data arrives; walk-forward numbers are the ones that count for a
  paper-trading decision. The 200-SMA gate, sizing, fills, and costs are **frozen** across
  all windows — no re-tuning between IS and OOS.

- **Pre-registered UNGATED variant (LOCKED as a scored diagnostic):** in addition to the
  200-SMA-gated baseline, a **hold-every-night** variant (identical in every other respect,
  regime gate disabled) is pre-registered and scored on SPY and QQQ, IS and OOS — **8 runs
  total** (2 variants × 2 instruments × 2 windows). Its purpose is to isolate how much the
  regime gate contributes vs. the raw unconditional premium; it is declared now so it cannot
  be introduced post hoc as an instrument-shopping escape hatch. The gated baseline remains
  the primary strategy; the ungated variant is diagnostic and held to the same locked bars.

## Paper-phase gate (PRE-REGISTERED 2026-07-04, before the first paper order — LOCKED)

Per workflow gate 6, the sample size and tolerances are fixed up front so the paper
verdict cannot be relitigated after the fills arrive.

- **What paper CAN and CANNOT measure (quant-review finding, stated up front).** Alpaca
  *paper* fills come from a **simulator**, not from participation in the real Nasdaq
  opening/closing crosses. The fill log therefore validates **operational mechanics**
  (MOC/OPG order acceptance incl. ~20-share odd lots, the 15:45/09:28 cutoffs, the
  overnight scheduler, crash recovery, logging) and the **signal path** (gate decisions
  matching the backtest), and it accumulates real official auction prints (SIP daily
  bars) for continued gross-edge monitoring. It **cannot CONFIRM the 2.90 bps
  round-trip cost hypothesis** (`experiments/execution-cost-study/2026-07-03-2319-*`),
  because simulated fills are not real auction executions. The tripwires below are
  therefore **asymmetric**: bad paper outcomes are real evidence and reject; good paper
  outcomes do NOT validate the cost hypothesis, which stays **UNVALIDATED** at the end
  of the paper phase and must be revisited with the user (e.g. a quote-based
  measurement study — official close print vs pre-cutoff NBBO mid — before any further
  promotion; live money is out of scope and never by default). **Profit judgment needs
  months of cycles and is explicitly NOT the goal of the first weeks.**
- **Sample (LOCKED): minimum 4 weeks or ~20 completed round-trip fills**, whichever
  comes later, before the mechanics verdict is judged.
- **Measurement**: every auction fill is appended to
  `experiments/overnight-long/paper-fills.QQQ.jsonl` (ts, side, qty, fill price, official
  auction print, diff in bps; degraded non-auction exits tagged `MKT`) by the paper
  runner. That log IS the measurement; no hand-collected numbers.
- **Auto-reject tripwire (LOCKED, no relitigation):**
  - **recurring MOC/OPG order rejections** (API-level rejections are real regardless of
    the fill simulator — odd-lot auction ineligibility included), or
  - simulated round-trip cost **> 4–5 bps** (a simulator this adverse, or one that
    cannot complete the cycle, is a real negative signal even though the converse
    proves nothing), or
  - recurring missed cutoffs / stranded positions / degraded `MKT` exits (mechanics
    failures)
  - → the strategy goes **back to REJECT**. The walk-forward carry was conditional on
    cheap, obtainable auction fills. No cost-model softening, no order-type
    workarounds, no re-argument.
- **Operational guardrails during paper**: `paper=True` hardcoded; per-session typed
  `paper` confirmation; ~$10k notional (~20 QQQ shares) on the $100k paper account;
  2·R daily lock and 15% drawdown kill switch enforced with state **persisted across
  the one-process-per-cycle lifetime** (`paper-risk-state.QQQ.json`); stale daily-gate
  data refuses to trade.
- **Data-feed policy (free-tier key, amended 2026-07-04 after preflight):** the
  account key has no real-time SIP entitlement, so the 15:40 **decision bar reads IEX
  real-time** — harmless, because the gate uses the *prior day's* completed close and
  the bar only timestamps the decision and prices the sizing. The **fill-log
  reference prints are always official SIP history**, fetched once >15 minutes old
  (free keys may query non-recent SIP), with a partial-day guard so a mid-day daily
  bar can never masquerade as the official close. `scripts/preflight_paper.py` is the
  read-only go/no-go check before any session.

## Known failure modes

Regimes where this should lose, and what limits the damage:

- **The un-stoppable overnight gap-down tail (the signature, un-removable risk).** A single
  overnight event (flash macro shock, geopolitical weekend, after-hours index-mover) can
  gap the open well beyond `G`, realizing more than `R` in one uncontrollable move that
  **cannot be stopped because the market is closed.** This is not a bug to mitigate away —
  it is the *risk the premium pays us to bear*, and it is precisely why the premium can
  persist. *Mitigation (bounding, not eliminating):* conservative gap-budget `G`,
  no-leverage cap, the worst-single-night ≤2·R criterion, 15% DD kill switch, and
  event-night tagging. Accept that this tail cannot be fully removed while holding overnight.
- **Bear markets / clustered gap-down opens.** The overnight premium is *supposed* to lose
  exactly when gap risk materializes — 2018 Q4, Mar 2020, 2022 bear. *Partial offset:* the
  200-SMA risk-on gate should sit the book out through much of a confirmed downtrend (price
  below SMA on the last completed close). *Residual exposure:* gap-downs that occur while
  still above the SMA, and whipsaw entries at regime transitions, remain fully exposed and
  un-stoppable.
- **Regime-gate whipsaw near the 200-SMA.** When price oscillates around its 200-day SMA
  the gate flips on/off across successive days, entering/exiting and paying the auction
  cost each time for little directional payoff. *Mitigation:* the gate is a single fixed
  rule — **no hysteresis band is added** (that would be a second tuned parameter). Cost
  drag from whipsaw is fully modeled and visible in regime-bucketed reporting. Accepted as
  a known weak spot, not tuned around.
- **Event-night gaps.** FOMC/CPI/NFP/elections concentrate overnight gap risk.
  *Baseline (flagged):* **hold + tag**, no filter — so their outsized tail contribution is
  isolable in reporting without adding a discretionary event-avoidance rule to v1.
- **Decayed / arbitraged premium (THE most likely quiet failure).** The parent already
  found the overnight-long net premium ~0/negative OOS on these exact instruments under
  these exact costs. Post-2018 studies find the SPY premium weak or absent; QQQ is stronger
  but time-varying. The single most probable outcome is that the raw net premium is ~0 OOS
  and this strategy is a **mild, pre-locked reject** — which the pre-gating decomposition
  diagnostic + the OOS Sharpe bar + the benchmark gate are specifically designed to force
  *honestly*, before any temptation to tune. The pre-lock exists to make honesty
  automatic: there is no green to fish for.
- **Auction-fill slippage worse than modeled.** The open print is genuinely uncertain; if
  real MOO fills are worse than 3 bps in stressed opens, the thin edge evaporates.
  *Mitigation:* intentionally heavy open-leg slippage; the cost-sensitivity *diagnostic*
  reports the break-even level; validate against Alpaca paper auction fills before trusting
  the backtest. (Conversely, if real fills are sub-bp, that is a *future* execution-cost
  study — not a reason to soften this spec's locked costs now.)
- **Dividend / distribution ex-dates corrupting the overnight stat.** An ETF ex-div date
  is a mechanical close→open drop that is *not* alpha; on a **long-only overnight** book
  this is a **systematic downward bias** on the exact return being measured (unlike the
  parent, whose short leg partially offset it). *Mitigation:* consistent dividend
  adjustment convention; ex-dates tagged; **the adjustment status of the on-hand data must
  be confirmed before backtest #1** (flagged below).
- **Early-close / half-day sessions and long weekends.** Non-standard sessions (13:00 ET
  closes) and ~65-hour long-weekend holds carry proportionally more gap risk.
  *Mitigation:* market-calendar-aware close/open prints; **baseline = hold these longer
  cycles normally, but TAG the ~65h long-weekend/half-day holds in reporting** so their
  gap contribution is isolable (flagged).
- **MOC/MOO mechanics failing in live.** If the MOC submission cutoff is missed or the
  auction rejects the order, the real fill diverges from the backtest's auction print.
  *Mitigation:* last-bar/first-bar fill is a degraded live substitute only (never the
  scored baseline), validated on Alpaca paper before any live consideration; paper-before-
  live per CLAUDE.md. Note the parent's `strategy.py` had a hardcoded-15:55/16:00 bug that
  skipped entry on early-close days — a re-implementation here must handle the calendar.

## Baselines pending a final user glance (do not block bar-setting)

These carry a stated baseline-with-rationale above and are pre-registered; listed here so
the user can veto/adjust *before* criteria are frozen for backtest #1. The LOCKED design
decisions (single overnight-long leg / both instruments SPY+QQQ, reported separately /
causal 200-SMA risk-on gate on the last completed close / MOC-MOO auction fills / cost
model carried forward unchanged from the parent) are **not** on this list — they are fixed.

1. **Sizing:** `R = 0.5%` equity per trade; overnight gap budget `G = max(3·σ_overnight_20d,
   5%)`; no leverage; `resting_stop = false`.
2. **Circuit breakers:** per-cycle `2·R` halt-and-review (**currently ineffective — known
   core sparse-order bug, fix before paper**); 15% peak-to-trough drawdown kill switch.
3. **Success bars:** OOS net Sharpe ≥ 0.7; net-positive expectancy; must beat buy-and-hold
   on net Sharpe; OOS max DD ≤ 15%; worst single-night loss ≤ ~2·R; ≥ 250 gated OOS cycles
   (non-binding); IS→OOS decay ≤ ~50%; IS 2018–2021 / OOS 2022–2024 / walk-forward 2025→.
4. **Event nights (FOMC/CPI/NFP/elections):** no filter (hold), but tag in reporting.
5. **Long-weekend / half-day (~65h) holds:** hold normally, but tag in reporting.
6. **Dividend adjustment mechanism:** adjust-in-place vs add-back — AND the unconfirmed
   dividend-adjust status of the on-hand parquet must be verified (a data check, not a
   judgment call; the requirement that ex-div gaps are not counted as alpha is locked).
7. **Ungated overnight-long variant as a separate pre-registered diagnostic instrument-run:**
   whether to *additionally* pre-register a no-200-SMA-gate version (hold every night) as a
   separate scored run — not to replace the gated baseline, but to measure how much of the
   result the gate actually contributes. Open question for sign-off.
