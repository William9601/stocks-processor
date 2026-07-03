# Strategy: intraday-momentum

- **Status**: implemented
- **Created**: 2026-07-03
- **One-liner**: Trades an index instrument in the direction of its early-session return, entering late in the day and flat by the close (market intraday momentum).
- **Implementation**: `strategies/intraday-momentum/strategy.py` (+ `config.yaml`,
  `tests/`), running on the shared core. Backtestable via `scripts/run_backtest.py`;
  paper-tradable on Alpaca via `scripts/run_paper.py` (`core/execution/live_runner.py` +
  `paper.py`). Unit-tested on synthetic data (backtest + live loop). **Not yet validated
  on real data**, and the paper path awaits a credentialed smoke test — success criteria
  below remain locked and unmet until a real-data OOS run.

## Hypothesis

**Effect.** The signed return over the first 30 minutes of the regular session
predicts the sign of the return over the last ~55 minutes of the same session. Trading
in the direction of the early-session move, entered late in the day, should earn a
positive expectancy. This is the "market intraday momentum" (MIM) effect documented by
Gao, Han, Li & Zhou (2018, *Journal of Financial Economics*, "Market intraday
momentum") on S&P 500 futures, and replicated across major international index futures
and ETFs.

**Mechanism — why it exists and who is on the other side.** This is a market-level,
non-cross-sectional effect, so the story must be about aggregate flow, not
stock-picking:

1. **Late-day rebalancing / trend-following flow.** Leveraged and inverse ETFs must
   rebalance their exposure toward the close to maintain constant leverage; the
   required rebalancing trade is *in the direction of the day's move* and is
   mechanically concentrated in the last 30–60 minutes. Volatility-target funds, CTAs,
   and delta-hedgers of option books add flow with a similar late-day, same-direction
   footprint. These participants trade on a schedule, not on price, so they are
   effectively price-insensitive and predictable — they are (part of) the counterparty
   paying our edge.

2. **Slow information diffusion / underreaction.** Information and order flow arriving
   in the morning are not fully impounded by midday; the market continues to drift in
   the established direction into the close as slower participants react. The morning
   return is a proxy for the day's dominant flow direction.

3. **Infrequent-rebalancing investors.** Institutions splitting large parent orders
   across the session (VWAP/TWAP execution) create autocorrelated intraday flow: a
   morning buyer is often still buying in the afternoon.

**Why it plausibly persists.** The dominant contributors (leveraged-ETF rebalancing,
vol-target and option-hedging flows) are structural and mandate-driven, not
discretionary alpha-seekers, so they do not "learn" to stop. However, the effect is
*publicly documented since 2018* and has almost certainly been partially arbitraged
away in the most liquid instrument (ES). We should expect a decayed, weaker signal than
the original paper's Sharpe and treat any strong in-sample result with suspicion.

**Adversarial note.** MIM in ES is a known, published, decayed effect — this is a
replication-and-survival test, not a novel edge. The bar for OOS significance should be
set accordingly (see Success criteria). If the OOS Sharpe net of costs is not
meaningfully positive, the correct outcome is to reject at spec-validation stage rather
than tune the signal until it works.

## Universe & timeframe

- **Instruments**: One instrument only in v1 — no basket, no cross-sectional selection.
  - **Primary (v1): SPY** (S&P 500 ETF). Chosen because execution/paper trading goes
    through **Alpaca**, which trades equities/ETFs but **not futures** — so SPY is what
    we can actually paper- and live-trade end to end. RTH session (no Globex/overnight),
    per-share tick/cost model. The leveraged-ETF-rebalance mechanism (the core of the
    hypothesis) is unchanged on SPY.
  - **Deferred: ES/MES** (E-mini / Micro E-mini S&P 500 futures). The academically
    cleaner vehicle, but needs a futures-capable broker + a futures data vendor with roll
    handling — out of scope for v1. Revisit once a futures path exists. Results on SPY and
    ES are **not** directly comparable and must be labeled by instrument.
- **Bar size / data resolution**: 5-minute bars, regular session.
- **Trading session (hours, timezone)**: US regular session, 09:30–16:00 ET. All
  timestamps in the spec are ET. Signal and trade times are defined on the regular
  session only; Globex/overnight bars are not used for signals in v1.
- **Holding period**: Intraday only. No overnight positions. Position is opened no
  earlier than 15:00 ET and is fully flat by 15:55 ET every trading day.

## Signals

All quantities use only data timestamped strictly before the decision bar. No signal
uses the bar it acts on (no same-bar fill, no `.shift(-1)`).

**Definitions (per trading day d):**

- Let `P(t)` be the price at the *close* of the 5-min bar ending at time `t`.
- **Reference window return**: `r_ref = P(10:00) / P(09:30_open) - 1`, i.e., the return
  from the 09:30 session open to the close of the 10:00 bar (the first 30 minutes =
  six 5-min bars). Use the true session open print for the 09:30 anchor. `r_ref` is
  fully known at 10:00 ET.
- **Opening volatility scale `σ_open`**: standard deviation of the six 5-min
  log-returns inside the 09:30–10:00 reference window, for the current day. This is a
  same-day, causal measure of morning volatility used to normalize the signal.
  - *Open question:* whether to instead/also use a trailing N-day realized-vol estimate
    for a more stable threshold (see Open Questions). Baseline uses same-day `σ_open`.
- **ATR (for sizing and stop)**: `ATR_open` = average true range of the six 5-min bars
  in the 09:30–10:00 window (Wilder or simple mean of true ranges), expressed in price
  points. Known at 10:00 ET, before entry. Used by both the risk sizing rule and the
  stop.

**Entry (single entry per day):**

- **Decision time**: 15:00 ET. Evaluate the rule using values known at/before 15:00.
- **Threshold gate**: trade only if `|r_ref| > k · σ_open` with baseline `k = 0.5`.
  `k` is a tunable parameter to be optimized **on the in-sample window only**. If the
  gate is not met, no trade that day (skip flat/choppy mornings).
- **Direction**: `sign(r_ref)`. Positive morning → go long; negative morning → go
  short. Long and short are symmetric in rule, but P&L is tracked separately per side
  (see Risk / reporting).
- **Fill**: enter at the **open of the next bar after the 15:00 decision** (the bar
  opening 15:00→15:05), never the same bar that triggers. Model entry slippage per Cost
  assumptions.
- One position per day, no pyramiding, no re-entry after an exit.

**Exit (profit)**: None in v1. No profit target — deliberately, to keep the test clean
and let the late-day drift run to the time exit.

**Exit (stop)**: Hard stop at **2 · ATR_open** from entry price, in the adverse
direction. Stop level is fixed at entry (not trailing). If the stop is touched
intrabar, model the fill at the stop level plus slippage (assume stop becomes a market
order; conservative slippage per Cost assumptions). *Open question:* intrabar
touch detection on 5-min bars requires an assumption about intrabar path — baseline
assumes stop can fill at the stop price if the bar's range crosses it, with added
slippage; this is optimistic and flagged.

**Exit (time)**: Force flat at **15:55 ET** (fill on the 15:50→15:55 bar close, or the
15:55 open — must be fixed; baseline: exit on the open of the 15:55 bar). No position is
carried past 15:55 ET under any circumstance. Time exit takes precedence — if neither
stop is hit, the position is closed at the time exit.

## Risk

- **Position sizing rule**: Volatility-targeted, constant risk per trade, delegated to
  `core/risk`. Size so that a move of `2 · ATR_open` (the stop distance) equals a fixed
  fraction `R` of account equity. For SPY (shares): `shares = floor( (R · equity) /
  (2 · ATR_open) )` since one share loses `2·ATR_open` dollars if stopped
  (`point_value = $1`); capped so notional ≤ equity (no leverage in v1). For a future
  futures path, `point_value` = $50 (ES) / $5 (MES). Baseline `R = 0.5%` of equity
  (**locked**). Round down; if size is 0 (stop too wide for account), skip the trade.
- **Max concurrent positions**: 1 (single instrument, single daily entry).
- **Per-trade stop**: `2 · ATR_open` hard stop (as above). This is the risk unit the
  sizing rule targets.
- **Daily loss limit**: With one trade/day and a `2·ATR` stop sized to `R` of equity,
  the structural worst case per day is ~`R` (plus slippage). Set an explicit daily loss
  kill switch at **2 · R** (covers gap/slippage overshoot on the stop); if breached, no
  new entry for the rest of the day. **Needs sign-off.**
- **Max drawdown kill switch**: Halt the strategy and require manual review if
  peak-to-trough equity drawdown exceeds **15%** (baseline, **needs sign-off**). This is
  a strategy-level circuit breaker, distinct from the per-trade stop.
- **Reporting**: track P&L, win rate, and expectancy **separately for long and short**
  trades, and separately by market regime (see Failure modes) to detect a one-sided or
  regime-dependent edge.

## Data requirements

- **Data types**: OHLCV bars (5-min) for the regular session, plus the true session
  open print. No quotes/news/fundamentals needed for signals in v1. For a realistic
  spread/slippage model, top-of-book quote or historical spread stats for ES are
  desirable (see Cost assumptions) but not strictly required for a first pass.
- **History depth**: 2018–present at minimum, to cover in-sample (2018–2021),
  out-of-sample (2022–2024), and walk-forward (2025→). Continuous, roll-adjusted futures
  series for ES (back-adjusted for continuity but with un-adjusted prices retained for
  realistic tick/cost modeling). Include the futures **roll calendar** so signals are
  not corrupted on roll days.
- **Source**: Split by stage.
  - **Execution (paper → live): Alpaca.** The user has an Alpaca paper account; the
    strategy runs live against Alpaca's data + paper broker. Full SIP data (Algo Trader
    Plus tier) is required for trustworthy 5-min bars — the free IEX feed (~2–3% of
    volume) is prototype-only.
  - **Backtest: a historical bar provider** (Alpaca SIP export, Polygon, or Databento —
    confirm) exported to parquet/CSV and loaded via `core/data`. Provider swaps don't
    touch the strategy (canonical UTC/OHLCV schema).
  - Every experiment records vendor, symbol, and adjustment method in its config for
    reproducibility. *Open: which historical vendor for the backtest.*

## Cost assumptions

Costs are mandatory and modeled on every backtest (commission + spread + slippage).
Baseline for the v1 primary instrument, **SPY on Alpaca** (implemented in
`core/backtest/costs.py`, configured in `config.yaml`):

- **Commission**: **$0/share** — Alpaca equities are commission-free.
- **Half-spread**: **1.0 bps** per side. SPY's penny spread on a ~$4–600 price is
  well under 1 bp in liquid RTH; 1.0 bps is a deliberately conservative crossing cost.
- **Slippage**: **1.0 bps** per side on market entries/time exits; **3.0 bps** on stop
  exits (stops are more adverse — gap-through risk). Spread + slippage are pushed
  against the trade direction in the fill price and tracked as explicit dollars, so
  `cost_drag`, `gross_return`, and `net_return` are all reported honestly.
- **Deferred — ES/MES**: ~$2.50/side commission (MES ~$0.50), 1-tick ($12.50)
  half-spread, 1-tick slippage ≈ ~$55 round-trip. Applies only if/when the futures path
  is built; not comparable to SPY results — label separately.

A result reported without these costs is not a valid result. Note SPY's per-trade edge
must clear a small but nonzero cost floor; a demo run on synthetic bars already shows
cost drag dominating when the signal is weak — exactly the regime the threshold gate
exists to avoid.

## Success criteria (locked before first backtest)

These are proposed defensible bars and **must be signed off by the user before the
first backtest** so they cannot be moved afterward. Given MIM in ES is a known, decayed
effect, the OOS bar is intentionally modest but must clear costs.

- **Minimum out-of-sample Sharpe (net of all costs)**: **≥ 0.7** annualized on the
  2022–2024 OOS window. (**Proposed — needs sign-off.** Rationale: a decayed public
  effect on a single liquid instrument should not be expected to match the original
  paper's headline numbers; anything below this is not worth the operational risk.)
- **Maximum drawdown tolerated (OOS)**: **≤ 15%** peak-to-trough. Consistent with the
  kill switch.
- **Minimum trade count for significance**: MIM trades at most once per session and the
  threshold gate skips days. With ~252 sessions/year and an expected gate pass rate of
  ~40–60%, the 3-year OOS window yields roughly **300–450 trades**. Require a minimum of
  **200 OOS trades** for the Sharpe estimate to be taken seriously; if the gate is so
  strict that fewer than 200 trades occur, the result is inconclusive regardless of
  Sharpe.
- **Additional gates (proposed)**: net positive expectancy per trade *after* costs;
  edge present on **both** long and short sides (not driven by a single directional
  regime); OOS Sharpe not more than ~50% below the in-sample Sharpe (large IS→OOS decay
  = overfit `k`).
- **In-sample window**: 2018–2021.  **Out-of-sample window**: 2022–2024.
  **Walk-forward**: 2025→present, re-estimating `k` on a rolling basis; walk-forward
  numbers are the ones that count for a paper-trading decision.

## Known failure modes

Regimes where this should lose, and what limits the damage:

- **Choppy / range-bound days.** When the morning move is noise, the afternoon mean-
  reverts and the trade whipsaws into the time exit or stop. *Mitigation:* the
  `|r_ref| > k · σ_open` threshold gate is designed to sit out low-conviction mornings;
  losses on days that pass the gate but chop are capped by the `2·ATR` stop.
- **Low-volatility drift / trendless tape.** Small morning returns produce small,
  cost-dominated afternoon moves; the edge can be entirely eaten by the ~$55 round-trip
  cost. *Mitigation:* threshold gate (skips low-`|r_ref|` days) and vol-targeted sizing
  (won't over-size a tiny-ATR day into cost drag); still a genuine weak regime to expect
  in reporting.
- **Intraday mean-reverting sessions (fade regimes).** In regimes where afternoon
  reverses morning (e.g., some high-vol panic-then-bounce days, or persistent
  short-vol/dip-buying regimes), MIM has negative expectancy. *Mitigation:* stop caps
  per-trade loss; regime-tagged reporting exposes if a sustained reversal regime is
  bleeding the book, which should trigger the drawdown kill switch.
- **Scheduled macro events (FOMC, CPI, NFP) in the 15:00–15:55 window.** FOMC
  statements at 14:00 ET and the 14:30 press conference land inside/near the trade
  window and can violently reverse the morning trend. *Open question:* baseline v1 does
  **not** filter event days — flag for a decision (skip FOMC days vs. trade them). At
  minimum, tag event days in reporting.
- **Late-day gap/stop-jump risk.** A fast move can blow through the `2·ATR` stop,
  realizing more than the intended `R`. *Mitigation:* conservative stop-exit slippage in
  the cost model and the `2·R` daily loss limit.
- **Decayed / arbitraged-away edge.** The most likely failure: the effect is simply too
  weak net of costs in ES post-2018. *Mitigation:* pre-locked OOS Sharpe/trade-count
  bars force an honest reject rather than post-hoc tuning.
- **Roll-day contamination.** A futures roll inside the signal or trade window can
  inject a spurious return. *Mitigation:* use the roll calendar; either skip roll days
  or compute returns on a single contract per day.
```
