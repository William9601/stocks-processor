# Strategy: spx-swing

- **Status**: draft
- **Created**: 2026-07-04
- **One-liner**: Multi-day swing trades on the S&P 500 (traded via SPY), holding roughly 2–10 sessions — long-only short-term mean reversion: buy a 2-day-oversold pullback while the index is above its 200-day SMA, exit on strength or a time stop, all decisions on daily bars after the close, all fills at the next opening auction.

## Hypothesis

**Effect.** Since roughly the late 1990s the S&P 500's short-horizon (1–5 day) return
autocorrelation has been **negative**: sharp multi-day sell-offs inside an intact
uptrend are, on average, followed by a multi-day rebound. This is the documented
short-term index mean-reversion effect (the autocorrelation regime flip is described in
the academic literature on index return dynamics; the tradeable formulation — RSI(2)-style
pullback buying above the 200-day SMA — was popularized by Connors & Alvarez, 2004–2009).
This strategy buys SPY after a 2-day-oversold reading in a confirmed uptrend and sells
into the rebound within ~2–10 sessions.

**Mechanism — why it exists and who is on the other side.** The sellers during a sharp
2–3 day index pullback are largely **mechanical, not informational**:

- **Vol-targeting and risk-parity funds** de-lever on schedule when short-term realized
  vol spikes — they sell *because vol rose*, not because expected return fell.
- **Trend/CTA overlays and retail stop-losses** sell into short-term weakness by rule.
- **Margin and risk-limit liquidations** are forced, price-insensitive flows.

Whoever takes the other side of forced, schedule-driven selling supplies liquidity into
a temporary demand/supply imbalance and earns a **liquidity-provision premium** — the
rebound when the mechanical flow exhausts. The counterparties keep "losing" because they
are not maximizing expected return on that trade; they are satisfying a vol target, a
stop rule, or a margin call. That is a real, persistent reason for the edge to survive
public documentation — though in decayed form (see the adversarial note).

**Diversification vs the existing book — addressed explicitly, not hand-waved.**
The live paper strategy (`overnight-long`) is long QQQ **every risk-on night**,
harvesting the unconditional close→open premium. `spx-swing` is a different exposure on
three axes: (1) **conditional, not always-on** — in the market only ~20–25% of calendar
days, only after pullbacks; (2) **different horizon** — multi-day holds capturing the
*intraday plus overnight* rebound, not the overnight leg alone; (3) **different
instrument** — SPY, not QQQ. **The honest caveat:** when both books are on
simultaneously, they are *both long a US equity index overnight*, and spx-swing's
holding periods cluster in exactly the high-vol pullback tapes where overnight gap risk
is largest — so the **conditional correlation in stress is high even though the
unconditional daily-return correlation is low.** Reporting must therefore tag
**overlap nights** (both strategies holding) and report the daily-return correlation vs
the overnight-long book, so the portfolio-level exposure is measured, not assumed
(see Known failure modes).

**Adversarial note — this is a well-known, partially decayed anomaly.** RSI(2)
pullback-buying is one of the most published retail systems in existence. Backtests of
the original rules show strong pre-2010 results and visibly weaker (though in most
studies still positive on *index ETFs*, unlike single stocks) results after. The honest
base-rate expectation is a **modest edge, well below the historical headline numbers**.
Two structural facts keep it worth testing at spec level rather than rejecting outright:
(1) the mechanical-seller mechanism above still operates — vol-targeting AUM is larger
today than when the effect was documented; (2) **turnover is low** (~15–25 round trips
per year), so the total cost drag is ~0.1–0.2%/yr — this strategy is *not* cost-gated
the way overnight-long was, and a thin gross edge survives costs largely intact. If the
pre-scoring diagnostic (below) shows the conditional rebound is ~0 net in the OOS
window, the correct outcome is **reject-at-spec-validation** — no threshold sweeps, no
instrument shopping, no exit-rule fishing.

## Universe & timeframe

- **Instruments (LOCKED): SPY only.** Single pre-registered instrument, no basket, no
  fallback. SPY is the S&P 500 vehicle the idea names; it is the deepest, tightest-spread
  US ETF; and choosing SPY (not QQQ) reduces instrument overlap with the paper
  `overnight-long` QQQ book. **No second instrument is declared** — if SPY fails, the
  strategy is rejected, not re-run on QQQ/IWM to fish for a pass.
- **Bar size / data resolution**: **daily RTH bars only** (official open, high, low,
  close; dividend+split adjusted). No intraday bars, no quotes, no real-time feed —
  by design, so the Alpaca **free data tier (IEX, no real-time SIP) is fully
  sufficient**: signals are computed from official SIP *historical* daily bars fetched
  after the close (free keys may query SIP data older than 15 minutes), and all orders
  are next-day opening-auction orders submitted the prior evening.
- **Trading session (hours, timezone)**: US regular session, 09:30–16:00 ET; all
  timestamps ET. Signal computation happens once per day, after ~16:20 ET, from the
  completed official daily bar. The only transacted print is the next day's **opening
  auction** (Alpaca OPG order, submitted before the 09:28 ET cutoff — in practice
  queued the prior evening). Early-close days (13:00 ET) use that day's actual official
  daily bar; the market calendar from core is reused.
- **Holding period**: multi-day swing, **minimum 1 session, maximum 10 sessions**
  (time stop), overnight and over-weekend holds allowed and expected — typical hold
  2–6 sessions. One position at a time; long-only; never short.

## Signals

**A signal at time T uses only data timestamped strictly before T.** All indicators are
computed on **completed daily bars** after the close of day *d*; the resulting order
transacts at the **open of day *d+1*** — a print that does not exist at decision time.
There is no same-bar fill anywhere in this spec.

**Definitions (all prices dividend+split adjusted; per completed trading day *d*):**

- `C(d), O(d), H(d), L(d)` = official adjusted close/open/high/low of day *d*.
- `SMA200(d)` = simple mean of `C` over the 200 most recent completed sessions up to
  and including *d*. Requires a ≥200-session warm-up before the first tradeable day.
- **`RSI2(d)`** — Wilder's RSI with period n = 2, defined exactly:
  - `U(d) = max(C(d) − C(d−1), 0)`, `D(d) = max(C(d−1) − C(d), 0)`
  - Wilder smoothing: `AvgU(d) = (AvgU(d−1)·(n−1) + U(d)) / n` with n = 2 (i.e., decay
    ½ per bar), same for `AvgD`. Seed: simple mean of the first n values at series
    start. With the mandated ≥250-session warm-up, the seed's influence is < 2⁻²⁴⁸ —
    two independent implementations agree to machine precision.
  - `RSI2(d) = 100 − 100 / (1 + AvgU(d)/AvgD(d))`; edge cases: if `AvgD(d) = 0`,
    RSI2 = 100; if `AvgU(d) = 0`, RSI2 = 0.
- **`ATR14(d)`** — Wilder's ATR, period 14: `TR(d) = max(H(d)−L(d), |H(d)−C(d−1)|,
  |L(d)−C(d−1)|)`; `ATR14` = Wilder smoothing of TR with n = 14, seeded with the simple
  mean of the first 14 TRs (again converged far beyond the warm-up).

**Entry (evaluated once, after the close of day *d*):**

- **Condition (all must hold):**
  1. `C(d) ≥ SMA200(d)` — uptrend/risk-on filter (same fixed 200-day parameter as the
     house overnight-long gate; **pre-registered, never swept**);
  2. `RSI2(d) ≤ 10` — 2-day-oversold trigger (**fixed threshold, pre-registered, never
     swept** — no 5/10/15/25 shopping);
  3. no open position, no pending exit from this same close (see cooldown), and no
     risk halt active.
- **Action:** submit a **buy OPG (market-on-open)** order for day *d+1*; fill at
  `O(d+1)` plus modeled slippage. Entering at the *next open* rather than the same-day
  close is a deliberate, causality-clean choice: it forfeits part of the classic
  same-close entry edge, and the strategy must pass anyway. No scale-in, no pyramiding.

**Exits (evaluated after each close while a position is open; all exits fill MOO at the
next open; if multiple conditions trigger on the same close, the action is the same
single OPG sell):**

- **Exit (profit / strength):** `RSI2(d) ≥ 65` → sell OPG at `O(d+1)`. Fixed threshold,
  pre-registered, never swept.
- **Exit (stop — daily-close-evaluated disaster stop):** let *e* = entry-signal day and
  `S = FillEntry − 3 · ATR14(e)` (stop distance frozen at entry). If `C(d) ≤ S` → sell
  OPG at `O(d+1)`. There is **no intraday stop** — free-tier data cannot monitor
  intraday, and intraday stops demonstrably degrade this effect by selling the lows.
  Consequence stated honestly: the realized stop loss can **overshoot** 1·R because the
  breach is observed at a close and filled at the next open (gap risk between stop
  check and fill).
- **Exit (time):** if the position is still open after the close of the **9th session
  following the entry-fill session**, sell OPG at the next open — maximum holding
  period 10 sessions. Fixed, pre-registered.
- **Re-entry cooldown (LOCKED):** on any close where an exit order is generated, entry
  evaluation is suppressed; the earliest next entry signal is the close of the
  exit-fill day. This prevents same-open exit-and-re-enter churn after stop-outs.

## Risk

- **Baseline risk unit: `R = 0.5%` of equity per trade** (house standard; flagged for
  sign-off).
- **Position sizing (stop-distance based):**
  `shares = floor( (R · equity) / (3 · ATR14(e) ) )`, capped so notional ≤ 100% of
  equity (**no leverage**). With SPY ATR ≈ 1% of price, this puts ~15–20% of equity in
  the position; a stop-out costs ≈ R (plus gap overshoot, see above).
- **Max concurrent positions:** 1 (SPY only, long only).
- **Per-trade stop:** the daily-close-evaluated `3·ATR14(e)` disaster stop above —
  expected loss at trigger ≈ 1·R; overshoot beyond R on a gap is an accepted,
  reported tail.
- **Daily loss limit:** realized+unrealized day loss worse than **2·R** (anchored at
  the prior session's closing equity, per the fixed core `RiskManager.on_bar()`)
  → no new entries until manually reviewed. Reuses the core fix landed 2026-07-04.
- **Max drawdown kill switch:** halt and require manual review at **12%**
  peak-to-trough equity drawdown (tighter than overnight-long's 15% because this book
  is in the market only ~20–25% of the time; flagged for sign-off).
- **Reporting (LOCKED):** per-trade P&L distribution, hit rate, avg win/loss, holding
  period distribution, exit-reason breakdown (strength/stop/time), **worst single
  trade in R units**, and — for the portfolio question — **overlap-night count and
  daily-return correlation vs the overnight-long book** over the same dates.

## Data requirements

- **Data types:** daily adjusted OHLC bars for SPY (Close for SMA/RSI, High/Low for
  ATR, Open for fills). Market calendar with early closes (already in core). No
  quotes, no news, no fundamentals, no intraday bars.
- **History depth:** warm-up of ≥250 sessions before the first tradeable day, plus the
  full IS window. Recommended windows (below) start IS at 2005, so daily data from
  **~2003-01 → present** is needed.
- **Source:** Alpaca SIP daily bars (`--adjustment all`) cover 2016→present and are the
  execution-matched source. **Pre-2016 daily bars require a supplementary EOD source**
  (e.g., Stooq/Tiingo free EOD, dividend-adjusted) — **ASSUMPTION, flagged:** the two
  sources must be spliced and cross-checked on the 2016–2017 overlap (adjusted-close
  divergence < 5 bps) before backtest #1. If the user declines a second source, the
  fallback windows in Success criteria apply.
- **Free-tier compatibility (LOCKED design constraint):** the strategy must never need
  real-time data. Signal run happens ≥15 minutes after the close (free keys may query
  historical SIP); orders are OPG, queued the prior evening. `scripts/preflight_paper.py`
  conventions from overnight-long carry over if this ever reaches paper.
- Every experiment records vendor, adjustment method, data range, seed, git commit
  (house rule 5).

## Cost assumptions

Costs are mandatory (house rule 3), modeled in `core/backtest/costs.py`, configured in
`config.yaml`. Consistent with the house convention for opening-auction fills:

- **Commission:** $0/share (Alpaca ETFs commission-free).
- **Half-spread:** 1.0 bps per side (conservative vs SPY's sub-bp penny spread).
- **Slippage:** **3.0 bps per side** on both legs — entry and exit are *both* opening
  auction (MOO/OPG) fills, the gappiest print of the session, penalized at the house
  MOO rate.
- **Round trip ≈ 8 bps.** At ~15–25 round trips/year this is ~0.12–0.20%/yr of drag —
  materially easier to clear than overnight-long's per-night cost hurdle. Costs are
  pushed against trade direction in the fill price; `cost_drag`, `gross_return`,
  `net_return` reported per run.
- **Cost-sensitivity diagnostic (NOT a gate):** report the break-even per-side
  slippage level, for information only.

## Success criteria (locked before first backtest)

Applied to SPY only; **pending final user sign-off, then frozen** — no adjustment after
results exist.

- **Pre-scoring decomposition diagnostic (run FIRST, outside the engine):** on daily
  bars, compute the mean net forward return of the exact entry condition
  (`RSI2 ≤ 10` and `C ≥ SMA200`, entry at next open, exit per the rules) vs the
  unconditional same-horizon return, IS and OOS separately. If the conditional edge is
  ~0 or negative net of the locked 8 bps in the OOS window, **reject at
  spec-validation** — nothing to tune toward.
- **Minimum OOS Sharpe (net of all costs): ≥ 0.7 annualized, zero-filled convention**
  (flat days count as 0 in the denominator — the house headline convention since the
  overnight-long v2 finding). Trade-days Sharpe reported as secondary, never as the
  verdict number.
- **Benchmark gate:** OOS net zero-filled Sharpe must **beat SPY buy-and-hold net
  Sharpe over the identical OOS window**. A long-only SPY strategy that can't beat
  holding SPY on risk-adjusted return adds only complexity.
- **Net-positive expectancy after costs:** mean net return per trade > 0.
- **Maximum drawdown tolerated (OOS): ≤ 12%** peak-to-trough, consistent with the kill
  switch. **Additionally:** worst single trade ≤ **2.5·R** in the realized path (a
  breach means the stop/gap overshoot is under-provisioned even if Sharpe passes).
- **Minimum trade count: ≥ 60 OOS trades.** This is the binding statistical
  constraint (unlike overnight-long) — the entry fires ~10–20×/yr, so the OOS window
  must be long enough. If the realized OOS count is < 60, the verdict is
  **inconclusive-reject** (insufficient evidence), not a pass on a good-looking small
  sample.
- **IS→OOS decay guard:** OOS Sharpe not more than ~50% below IS Sharpe.
- **Windows (recommended — flagged, depends on pre-2016 data decision):**
  - **In-sample: 2005-01 → 2017-12.** **Out-of-sample: 2018-01 → 2024-12** (contains
    2018 Q4, the 2020 crash, and the 2022 bear — a demanding, honest OOS).
    **Walk-forward: 2025-01 → present.**
  - **Fallback if only Alpaca 2016→ data is approved:** IS 2016–2021, OOS 2022–2024,
    WF 2025→ — but expected OOS trade count is then ~40–50, likely **failing the ≥60
    bar by construction**; this is why the longer history is recommended.
  - All parameters (200/10/65/3·ATR/10-session) are frozen across all windows; there
    is nothing to re-tune between IS and OOS because **every parameter is
    pre-registered and none may be swept.**

## Known failure modes

Regimes where this should lose, and what limits the damage:

- **The falling knife above the 200-SMA.** The signature loss: a pullback that keeps
  falling (Feb 2018, Aug 2015, the first legs of Mar 2020) while price is still above
  the SMA at entry. Mean reversion is short a crash, structurally. *Bounding:* the
  3·ATR daily-close disaster stop, sizing to R, the 2·R day lock, and the 12% kill
  switch — none of which prevent the loss, only cap it.
- **Momentum-regime flips.** In cascading liquidations (2008-style), short-term
  autocorrelation turns positive — oversold begets more selling. *Partial offset:* the
  200-SMA filter keeps the book out of confirmed downtrends; the residual exposure is
  the transition itself, which is exactly where the stop and R-sizing earn their keep.
- **Stop-check-to-fill gap overshoot.** The stop is evaluated at a close and filled at
  the next open; an overnight gap can push the realized loss well past 1·R. Accepted,
  measured (worst-trade ≤ 2.5·R criterion), not hidden.
- **Stress-correlated overlap with overnight-long (portfolio-level).** When spx-swing
  holds, it holds through nights — often the same high-vol nights the QQQ
  overnight-long book is long. Unconditional correlation is low (~20–25% time in
  market); **conditional correlation in sell-offs is high**, and a single bad
  macro-gap night can hit both books at once. *Mitigation:* overlap nights and
  cross-book return correlation are mandatory reporting outputs; any future
  portfolio-level risk budget must treat the two as one overnight-gap exposure on
  overlap nights, not two independent strategies.
- **Decayed public anomaly (the most likely quiet failure).** RSI(2) buying is
  20-year-old public knowledge; post-2010 the edge is visibly thinner. The pre-scoring
  diagnostic, the zero-filled 0.7 bar, the B&H gate, and the ≥60-trade minimum exist
  to force an honest reject if the rebound is no longer there net of costs.
- **Drought regimes (opportunity cost, not loss).** Low-vol grinding bulls
  (e.g., 2017) produce almost no signals; the book sits flat for months. Zero-filled
  Sharpe accounting makes this cost visible in the headline number instead of hiding
  it.
- **Ex-dividend distortion.** All indicator and return math is on adjusted prices
  (house convention from overnight-long); ex-div dates tagged in reporting. The
  adjustment status of any spliced pre-2016 source must be verified in the same data
  check.
- **OPG mechanics.** Alpaca OPG orders must be accepted and fill at the official open
  print; odd-lot auction eligibility and the 09:28 cutoff were already exercised by the
  overnight-long paper path, but must be re-verified for evening-queued orders before
  any paper phase.

## Baselines pending user sign-off (do not block bar-setting)

The LOCKED design (SPY only / long only / RSI2 ≤ 10 entry above 200-SMA / RSI2 ≥ 65,
3·ATR daily-close stop, 10-session time stop / next-open OPG fills / no parameter
sweeps) is fixed. The following baselines carry a stated rationale and can be vetoed
before criteria freeze:

1. **Sizing:** `R = 0.5%` per trade, stop-distance sizing, no leverage.
2. **Kill switch:** 12% (vs house 15%) given ~20–25% market exposure.
3. **Windows:** IS 2005–2017 / OOS 2018–2024 / WF 2025→ — **requires approving a
   supplementary pre-2016 EOD data source with a splice cross-check.**
4. **Entry execution:** next-open OPG baseline. A pre-registered *diagnostic* variant —
   limit-buy at `C(d)` working day *d+1* (fill iff `L(d+1) ≤ C(d)`, at
   `min(O(d+1), C(d))`) — could be declared now or dropped; it is NOT the scored
   baseline either way.
5. **Shorting:** excluded entirely (no short-side mean reversion below the 200-SMA).
   Confirm this matches account intent.
