# Strategy: fomc-drift

- **Status**: approved (user sign-offs 2026-07-06; criteria FROZEN)
- **Created**: 2026-07-06
- **One-liner**: Hold SPY long over the ~24 hours before each scheduled FOMC announcement (buy the close of the day before, sell the close of the announcement day) to harvest the pre-FOMC announcement drift.

> **Provenance.** Lucca & Moench (2015, Journal of Finance; NY Fed staff report
> sr512): +49 bps average excess return per scheduled FOMC announcement,
> Sept 1994 → March 2011 — ~80% of the annual equity premium earned on ~8 scheduled
> days/yr. The adversarial record, on file before this spec was drafted
> (`docs/strategy-candidates.md` entry #6, the source of record): Kurov, Wolfe &
> Gilbert (Finance Research Letters 2021, sample to Dec 2019) find the drift
> "essentially disappeared after 2015" — Jan 2016–Dec 2019 mean ≈ **9.2 bps,
> statistically insignificant** — attributing it to reduced uncertainty in the ZLB
> era; Ben Dor & Rosa (2019) dispute (no change found); Boguth, Grégoire & Martineau
> (2019, to Sept 2017) find the drift concentrated in press-conference meetings with
> onset migrated to the prior day's open; QuantSeeker (2025; SPY EOD close-to-close
> windows, 1993–2024 — **our exact implementable window**) finds the
> FOMC-vs-other-days difference strongly significant full-sample, confirms the flat
> 2016–2019 stretch, and shows renewed performance 2020–2024 (after-cost Sharpe
> ~0.5–0.6 trading ~5% of days). **The falsifiable working hypothesis this spec
> tests: the drift is uncertainty-state-dependent, not monotonically decayed** — it
> faded in the ZLB calm and returned with policy uncertainty.

## Hypothesis

**Effect.** US equities earn abnormally large returns in the ~24 hours before
scheduled FOMC announcements. This strategy holds SPY over the one implementable
daily-bar window: long from the close of the last trading day before the
announcement day to the close of the announcement day — one close-to-close daily
return per event, ~8 events/yr, flat the other ~97% of days.

**Mechanism — who is on the other side and why do they keep paying?**

- **Deliberate insurance payers.** VaR-limited, vol-targeting, and
  mandate-constrained institutions systematically de-gross ahead of the single most
  important scheduled macro event of the cycle, buying exposure back afterward. They
  sell before the announcement *because the event is coming*, not because expected
  return fell — the same schedule-driven, non-EV-maximizing counterparty class that
  underwrites the overnight-long book's premium. Hu, Pan, Wang & Zhu (2019) frame
  the drift as compensation for bearing heightened uncertainty ahead of
  pre-scheduled announcements as it resolves.
- **The honest puzzle, stated plainly.** Lucca & Moench themselves show the drift
  accrues *before* the announcement with *low* realized volatility during the drift
  window, and roughly nothing on average after — returns without commensurate
  contemporaneous risk. Simple risk-compensation is therefore contested in the
  literature; "pre-FOMC drift puzzle" is the accepted name for a reason. The
  mechanism is plausible but not settled, and this spec does not pretend otherwise.
- **The state-dependence claim is what makes this testable rather than mush.** If
  the premium is payment for policy-uncertainty resolution, it should be ~absent
  when there is nothing to resolve (2016–2019: telegraphed 25 bps moves, dot-plot
  forward guidance — exactly Kurov's dead zone) and present when the path is
  genuinely uncertain (2020 COVID, the 2022–2023 hiking cycle — exactly
  QuantSeeker's revival). The strategy itself stays **unconditional** — trade every
  scheduled meeting, no uncertainty gate, no VIX filter (that would be a new tuned
  parameter and a sweep). The pre-registered OOS era deliberately contains the full
  dead zone; if the blend of dead zone + revival cannot clear the frozen bars, the
  premium is not harvestable as specified and the verdict is REJECT — **no
  uncertainty-gating rescue run.**

**Deviation from Lucca–Moench's window, stated before anyone backtests.** LM measure
2pm(T−1) → 2:15pm(T), i.e., *up to* the announcement. The daily-bar implementable
window (close T−1 → close T) additionally holds **through the 14:00 ET statement,
the press conference, and the 14:00→16:00 reaction** — high-variance, ~zero-mean
per LM. The direct evidence for our exact window is QuantSeeker's practitioner EOD
test (1993–2024), which is weaker-grade evidence than the refereed LM result. This
is a real dilution of the documented effect, accepted because the lab's
infrastructure is daily bars and MOC fills — **no intraday machinery will be
proposed or built for this strategy.**

**Diversification vs the existing book — quantified, not hand-waved.** The live
paper book (`overnight-long`) holds QQQ close→open on 200-SMA risk-on nights. Every
fomc-drift hold spans exactly one overnight (T−1 → T) plus the announcement day —
so on every FOMC event night where the QQQ gate is risk-on, **both books are long
US index beta over the same closed-market hours**, and FOMC nights are precisely
the event nights overnight-long's spec chose to hold-and-tag. Unconditional
daily-return correlation between the books will be mechanically near zero (this
book is flat ~97% of days); the honest number is conditional: on overlap nights the
two overnight legs are one trade at SPY/QQQ overnight beta ≈ 0.9. Bounded by
construction at ≤ ~8 overlap nights/yr. See Risk → Overlap policy for the required
reporting and the acceptance threshold.

**Adversarial notes — read before falling in love:**

1. **The lab base rate is five rejections, and "published-then-gone" is confirmed
   four times in-house** (intraday-momentum, spx-swing, ORB, ToM at research
   screen). Lucca–Moench is one of the most famous anomaly papers of its decade
   (WSJ front-page coverage before journal publication). The OOS era here is
   **entirely post-publication** — deliberately the binding test, and the expected
   outcome is a borderline result or an honest reject.
2. **The decay claim is in refereed print.** Kurov et al.'s 9.2 bps insignificant
   2016–2019 mean sits inside our OOS window on purpose. If the revival isn't
   strong enough to lift the 9-year blend over the frozen bars, the strategy fails
   — that is the design, not a flaw in it.
3. **Statistical power is thin and the spec says so with numbers.** ~8 events/yr;
   per-event return SD ≈ 120 bps (SPY daily close-to-close, fat-tailed on
   announcement days). SE of the per-event mean: IS (~176 events) ≈ **9 bps**; OOS
   (~72 events) ≈ **14 bps**. The OOS can distinguish an LM-sized (~45 bps) edge
   from zero (t ≈ 3) but **cannot** distinguish a 10 bps edge from zero (t ≈ 0.7).
   SE of the annualized OOS Sharpe over 9 years ≈ **±0.35–0.40**. One −4% event
   day moves the 72-event OOS mean by ~−5.5 bps. These are the error bars the
   verdict will carry; nobody gets to be surprised by them later.
4. **Onset migration is a real threat to this exact window.** Boguth et al. find
   the drift's onset moved to the *prior day's open* in the later sample. If the
   drift now completes before our close(T−1) entry, we capture nothing even if
   "the drift exists." The close(T−2)→close(T−1) diagnostic column (below) measures
   what we miss — as a diagnostic only, never as a promotion path to an earlier
   entry.
5. **Even at full hypothesis strength this is a small overlay.** At baseline
   gap-budget sizing (~10% of equity in the position), 8 events × ~30 bps net ≈
   **~25 bps of equity per year**. The Sharpe-based verdict is sizing-invariant,
   but the user should size-off knowing the dollar contribution is modest (signed
   off 2026-07-06: R = 0.5% confirmed with this arithmetic on the table).

## Universe & timeframe

- **Instruments (LOCKED): SPY only.** The literature's instrument (LM use SPX/SPY;
  QuantSeeker's EOD test is SPY). Single pre-registered instrument — if SPY fails,
  the strategy is rejected, not re-run on QQQ/IWM/ES to fish for a pass. SPY also
  keeps instrument-level separation from the QQQ overnight-long book.
- **Bar size / data resolution**: **daily RTH bars only** (official open/high/low/
  close, self-adjusted splice — see Data). No intraday bars, no quotes, no
  real-time feed required; the signal is a calendar, not a market observable.
- **Trading session**: US regular session, 09:30–16:00 ET; all timestamps ET. The
  only transacted prints are **closing auctions** (MOC both legs). Exchange
  calendar from core handles holidays and early closes (scheduled FOMC
  announcements fall on regular Tue/Wed sessions; the calendar rules below are
  written generally anyway).
- **Holding period**: exactly **one close-to-close daily return per event** (~28
  hours wall-clock), overnight hold included by construction; ~8 events/yr, ~3% of
  trading days in the market; one position at a time (meetings never overlap);
  long-only; never short.

## Signals

**The signal is a calendar, known in advance — zero lookahead by construction.**
The Federal Reserve publishes its scheduled meeting calendar roughly a year or more
ahead; historical scheduled dates are public record. A signal at time T uses only
the calendar as it stood at T and completed daily bars strictly before T. No market
data enters the entry/exit decision at all; market data enters only position sizing
(completed bars only).

**Definitions:**

- **Announcement day `T`** = the **final day** of a scheduled FOMC meeting (the day
  the statement is released, ~14:00 ET in the modern era, 2:15pm earlier —
  irrelevant at daily resolution). For one-day meetings (common in the 1990s),
  `T` = that day.
- **Entry day `T−1`** = the last trading session strictly before `T` per the
  exchange calendar.
- **Scheduled meetings only (LOCKED).** Unscheduled/emergency meetings, intermeeting
  actions, and conference calls (e.g., the 2020-03-03 and 2020-03-15 emergency
  cuts, 2008 intermeeting actions) are **excluded**: they are not knowable in
  advance, therefore not tradeable by a pre-announcement strategy, and not part of
  the documented effect (the literature pre-registered scheduled announcements).
- **Point-in-time cancellation rule (LOCKED):** if, by the entry decision time on
  `T−1`, the Fed has publicly cancelled or superseded the scheduled meeting (March
  2020: the scheduled Mar 17–18 meeting was superseded by the Mar 15 emergency
  action, announced before the would-be entry), **no entry**. The exception list is
  built from Fed press releases, committed alongside the calendar file, and
  auditable. If a cancellation were ever announced *after* entry, the exit below
  fires unconditionally anyway.

**Entry (MOC, day T−1):**

- At **15:40 ET on day T−1** (house MOC decision-cutoff convention, from
  overnight-long: Alpaca MOC submission cutoff ~15:45), submit a **buy MOC**
  order. Backtest fill: `Close(T−1)` plus modeled costs, via the core
  `FillTiming.NEXT_CLOSE` path (order emitted on the prior bar; **no core
  extension needed — verified**).
- Condition: `T` is on the committed scheduled calendar, not cancelled per the
  rule above, no risk halt active. Nothing else — no trend gate, no vol gate, no
  press-conference filter.

**Exit (time — the only exit, LOCKED):**

- At **15:40 ET on day T**, submit a **sell MOC** order; fill at `Close(T)` plus
  modeled costs. Unconditional — fires regardless of P&L, news, or what the Fed
  said at 14:00.
- **Exit (profit): none. Exit (stop): none — stated honestly.** The hold spans a
  closed market overnight and a full announcement day on a daily-bar book: there
  is no print to stop out on. A −5% announcement day is realized in full. Risk is
  controlled entirely by sizing and the kill switches (Risk section), never by an
  un-fillable stop.

**Pre-registration of the window (LOCKED — the single most important discipline in
this spec).** The window close(T−1) → close(T) is pre-registered **once, from the
literature, before looking at our data**. There will be **no window sweeps, no
onset sweeps, no press-conference-only conditioning, no "T−2 entry" or "exit at
open(T)" variants as promotion paths — ever.** Rejected means rejected.

**Diagnostic-only columns (pre-registered now so they cannot be introduced post
hoc; never gates, never verdict numbers, never promotion paths):**

1. **Decomposition**: close(T−1)→open(T) vs open(T)→close(T) — where does the
   return live (overnight drift vs announcement reaction)?
2. **Missed-onset check**: close(T−2)→close(T−1) — the Boguth migration diagnostic.
3. **Press-conference vs non-PC meeting tag** (pre-2019 only; all meetings have
   press conferences since 2019).
4. Per-year and per-era means (2016–2019 dead zone vs 2020–2024 separately, OOS);
   median and 10%-trimmed mean (outlier visibility — **no outlier removal in any
   scored number, ever**); ex-div-spanning event tags; worst event.

## Risk

- **Baseline risk unit: `R = 0.5%` of equity per event** (house standard; flagged
  for sign-off, see the small-overlay arithmetic in Adversarial note #5).
- **Sizing — overnight-long's gap-budget mechanism, reused verbatim:** size so a
  worst-plausible adverse move `G` costs `R`, where
  `G = max(3 · σ_20d, 5%)` and `σ_20d` = trailing 20-day realized stdev of SPY
  daily close-to-close returns, computed causally from completed bars strictly
  before the entry decision. `shares = floor((R · equity) / (G · Close_ref))` with
  `Close_ref` = last completed daily close before the decision; notional capped at
  100% of equity (**no leverage**). The 5% floor binds in normal vol (σ ≈ 1%) →
  **typical notional ≈ 10% of equity.** The event being held is exactly where SPY's
  fat tails live; the floor is deliberate.
- **Max concurrent positions**: 1 (SPY only, long only; scheduled meetings never
  overlap).
- **Per-trade stop**: **none — impossible** (see Signals). Loss cap per event is
  `R` under a `G`-sized move; overshoot beyond that is an accepted, measured tail
  (worst-event criterion below).
- **Daily loss limit**: realized+unrealized day loss worse than **2·R**, anchored
  at the prior session's closing equity per the fixed core `RiskManager.on_bar()`
  → halt-and-review. With one position at ~10% notional this binds only on a
  >2G announcement-day move — kept as the house invariant.
- **Max drawdown kill switch: 5%** peak-to-trough equity (much tighter than the
  house 15%: this book is in the market ~3% of days at ~10% notional; 5% of equity
  ≈ 10 consecutive full-R losses ≈ more than a year of maximally bad events —
  hitting it means the book is far outside its own expected behavior). Flagged for
  sign-off.
- **Overlap policy vs the overnight-long paper book (LOCKED reporting, threshold
  flagged):**
  - Mandatory reporting: (a) count of overlap nights (FOMC event nights where the
    QQQ gate was risk-on) per era; (b) daily-return correlation between the two
    books' zero-filled equity curves over the common window; (c) combined
    index-overnight notional on each overlap night.
  - Acceptance: unconditional daily correlation **< 0.15** over the common window
    (expected to hold mechanically) **and** overlap bounded at ≤ ~8 nights/yr (true
    by construction). The real control is a portfolio rule: **on overlap nights the
    two books' overnight index exposure is treated as ONE gap exposure against a
    single shared 2·R overnight budget** — at baseline sizes (fomc-drift ~10%
    notional; overnight-long's paper book ~$10k) this is comfortably inside budget.
    The overlap is not accidental: if the hypothesis is right, pre-FOMC nights are
    the *best* overnights of the cycle, and the doubling is deliberate, capped, and
    reported. Threshold and framing flagged for sign-off.
- **Reporting (LOCKED)**: per-event P&L in bps of notional and in R; per-year and
  per-era means; the four diagnostic columns above; hit rate; worst event in R;
  full event-return distribution; overlap metrics; ex-div tags; cost drag, gross
  and net per run.

## Data requirements

- **SPY daily adjusted OHLC, 1994-01 → present — the audited self-adjusted splice,
  extended.** Base file: `data/SPY_daily_adj_spliced.parquet` (raw prints — Yahoo
  pre-2016, Alpaca SIP after — with uniform CRSP back-adjustment from the dividend
  record; built by `scripts/build_spy_eod_splice.py` for spx-swing; audit in
  `experiments/spx-swing/2026-07-05-pregate/splice_report.json`). **Never** use
  Alpaca `adjustment=all` unaudited — it is missing the 2016-03-18 and 2018-06-15
  SPY dividends (house finding 2026-07-05), and FOMC holds sometimes span ex-dates
  (meetings cluster mid-Mar/Jun/Sep/Dec, near SPY's third-Friday ex-div dates), so
  an adjustment error lands directly on measured event returns.
  - **Required data task (pre-declared):** the splice as built covers
    **2002-09-03 → 2026-07-02** — the candidates-doc claim that it reaches 1994 is
    wrong as-built. Re-run the splice build from **1993-06** (SPY inception
    1993-01; ~6-month buffer) with the **same audit**: per-ex-date dividend-step
    corroboration, dividend-event count (~4/yr), print-divergence checks where a
    comparison series exists. Known caveat inherited from spx-swing: the Yahoo
    segment carries Yahoo print quality (crisis-day prints can be off); the
    1990s segment gets the same audit before use. **OOS and WF windows contain
    zero Yahoo data** — the era that decides the verdict is on SIP prints.
  - **Pre-declared fallback (so the window cannot be renegotiated after results
    exist):** if the pre-2002 extension fails its audit, IS becomes
    **2003-01 → 2015-12** (~104 events, per-event-mean SE ≈ 12 bps) on the
    existing audited splice. OOS/WF are unaffected either way.
- **Scheduled FOMC announcement calendar, 1994 → present (new input).** Source:
  Federal Reserve website (current calendars published ~a year+ in advance;
  historical meeting materials back decades). Built as a committed CSV at
  `strategies/fomc-drift/fomc_calendar.csv` (committed to git — it is not market
  data and reproducibility demands it), columns: meeting start date, end date
  (= `T`), scheduled/cancelled flag, press-conference flag, source note.
  - **Calendar audit (blocking, before the pregate):** events/yr must be ~8 for
    every year 1994–2025 (any year ≠ 8 gets a documented explanation); spot-check
    ≥ 20 dates against the Lucca–Moench appendix and QuantSeeker's list; every `T`
    should be a Tuesday or Wednesday (any exception manually verified); every
    `T−1` mapping verified against the exchange calendar. A calendar error is
    silent systematic garbage — this audit is not optional.
  - Unscheduled/emergency actions and the March 2020 cancellation are recorded in
    the same file per the Signals rules.
- **Exchange calendar** with early closes: already in core.
- **No intraday data, no quotes, no fundamentals.** The strategy is free-tier
  compatible by design (signal is a calendar; fills are MOC orders queued
  pre-cutoff), though the account holds Algo Trader Plus anyway.
- **Reproducibility (house rule 5 + orb reviewer follow-up):** every run records
  vendor, data range, adjustment method, **data file hashes**, calendar file
  version, seed, git commit.

## Cost assumptions

Costs are mandatory (house rule 3), modeled in `core/backtest/costs.py`. Both legs
are **SPY closing-auction MOC fills** — the deepest single liquidity event in world
equities. Calibration anchors: SPY spread ≈ 1 cent on ~$560 ≈ 0.18 bps full spread;
the lab's own execution-cost study measured **SPY MOC+MOO round trip at 2.03 bps**
(`experiments/execution-cost-study/2026-07-03-2319-*`), and this book replaces the
gappy MOO leg with a second MOC.

- **Commission**: $0/share (Alpaca).
- **Half-spread**: 0.5 bps/side (conservative vs the observed ~0.1 bps).
- **MOC auction slippage**: 0.5 bps/side.
- **LOCKED cost bar: 2.0 bps round trip** — at or above the *measured* MOC+MOO
  round trip despite the easier print pair. Not renegotiable after the pregate
  prints.
- **Pre-registered 1.5× companion: 3.0 bps round trip** — the OOS result must
  survive it (bar below).
- **Annual drag**: 8 round trips × 2.0 bps = **16 bps/yr of deployed notional** —
  this strategy is not cost-gated; the binding gate is the benchmark edge.

**The arithmetic the result will be judged against (LOCKED framing):**

- LM-strength (+49 bps gross/event → ~47 net): 8 × 47 ≈ +3.8%/yr on notional;
  zero-filled Sharpe ≈ **1.1**. Passes everything.
- Kurov dead-zone strength (+9.2 bps gross → ~7 net; edge vs the ~+4–5 bps
  unconditional day ≈ +5 gross): Sharpe ≈ **0.2**. Fails everything — as it should.
- The 0.7 Sharpe bar (below) requires **≈ 30 bps net per event** on the full OOS
  blend — roughly LM-two-thirds-strength sustained across 9 years that include the
  documented 4-year dead zone. That is the honest height of the bar, stated before
  anyone runs anything.

## Success criteria (locked before first backtest)

Signed off by the user 2026-07-06 — **now immovable.** Every parameter
(the window, the calendar rules, MOC fills, sizing, costs, eras) is pre-registered;
**nothing is ever swept**, so there is nothing to re-tune between IS and OOS.

### Benchmark-gate arithmetic (the spx-swing convention — stated explicitly)

For an era `E`:

- `FOMC(E)` = mean **gross** close(T−1)→close(T) return over scheduled events in `E`.
- `BASE(E)` = mean **gross** close-to-close return over **all non-event trading
  days** in `E` (non-event, so the baseline is not contaminated by the effect
  itself — the QuantSeeker FOMC-vs-other-days convention).
- **Conditional edge** `EDGE(E) = FOMC(E) − BASE(E)`.

A pre-FOMC "drift" that does not beat an ordinary SPY day by at least the round
trip cost is index drift plus a calendar story — the arithmetic that honestly
killed spx-swing (OOS edge −14.6 bps) and ToM at the research screen.

### PREGATE — pre-scoring gross-edge diagnostic (run FIRST, outside the engine)

Standalone script (`scripts/pregate_fomc.py`, following `pregate_spxswing.py` /
`pregate_orb.py`), run on the extended splice + audited calendar, **IS window only;
OOS and WF stay unread.** Computes per-event gross returns, `BASE(IS)`, `EDGE(IS)`,
t-stats, and the diagnostic columns. Cheap and decisive: one session, no engine
code.

**Gate rule (LOCKED before the script is written) — REJECT at spec validation if:**

- `EDGE(IS) ≤ 2.0 bps` (the locked cost bar — the conditional edge must at least
  pay for its own round trip), **or**
- `EDGE(IS) < 20 bps` — the **reproduction bar**: the IS era is the literature's
  own sample, where the documented edge is ~+45 bps over baseline with SE ≈ 9 bps.
  An IS edge under 20 bps (t < ~2.2) means our data does not contain the documented
  effect at even half strength, and reading the OOS would be spending an
  out-of-sample look on a hypothesis already dead. (Flagged for sign-off — it is a
  judgment call, but the alternative is proceeding to OOS on a non-reproduced
  effect.)

t-stats are reported for honesty; the threshold rules are binding (house
convention). On PASS: implement against core (no core extension needed), engine IS
run must reproduce the pregate to rounding (the orb cross-check pattern), then the
**one** pre-registered OOS look plus its 1.5×-cost companion. On FAIL: reject, no
tuning, post-mortem in this file.

### Backtest bars (engine, net of the locked 2.0 bps; OOS 2016-01 → 2024-12)

| # | Frozen bar |
|---|---|
| 1 | **OOS net zero-filled Sharpe ≥ 0.7** annualized (house bar; flat days count 0 — with ~8 event-days/yr the zero-fill discipline is doing real work here) |
| 2 | **Benchmark edge gate**: `EDGE(OOS) ≥ 2.0 bps` gross, i.e., net conditional edge > 0 over the identical window |
| 3 | ~~Beat SPY buy-and-hold net Sharpe over the identical OOS window~~ **WAIVED at sign-off 2026-07-06.** Recorded rationale: for a ~3%-exposure overlay the B&H comparison double-counts the fixed zero-filled 0.7 bar (SPY B&H OOS Sharpe ≈ 0.8) and even the documented revival-strength effect (~0.5–0.6) would fail it; house precedent is overnight-long (also an overlay), which used a fixed Sharpe bar, not the orb B&H convention (a full-time book). The conditional-edge gate (#2, #4) remains the binding beats-the-index economics. Waived before any data was read. |
| 4 | **Net-positive expectancy per event** after costs; **and still net-positive at 1.5× costs (3.0 bps)**, equivalently `EDGE(OOS) ≥ 3.0 bps` |
| 5 | **Max OOS drawdown ≤ 6·R of equity** (= 3.0% at baseline sizing), consistent with the 5% kill switch |
| 6 | **Worst single event ≤ 2.5·R realized** (a breach means the gap budget `G` under-provisions announcement-day tails even if Sharpe passes) |
| 7 | **Minimum OOS event count: ≥ 64 filled events** (9 yrs × 8 = 72 scheduled; a handful of legitimate cancellations/skips allowed; below 64 means calendar or data bugs → verdict is **inconclusive-reject** regardless of Sharpe) |
| 8 | **IS→OOS decay guard**: OOS net zero-filled Sharpe not more than 50% below IS (house convention) |

**No-rescue clause (LOCKED):** the per-era splits (2016–2019 dead zone vs
2020–2024 revival) are mandatory diagnostics and **never gates in either
direction** — a full-OOS fail cannot be rescued by a strong 2020–2024 sub-era, and
a Kurov-consistent ≈0 dead zone does not fail an otherwise-passing full-OOS result.
The strategy is judged unconditionally on the blend, because it trades
unconditionally.

### Windows (pre-registered)

- **In-sample: 1994-01 → 2015-12** (~176 scheduled events; SE of the per-event
  mean ≈ 9 bps). Boundary justification, fixed before any data is read: (a) 1994
  is when the Fed began announcing policy decisions after meetings — the
  literature's own start; (b) Lucca–Moench was published in 2015, so everything
  after is post-publication; (c) Kurov's claimed structural break is end-2015. The
  IS/OOS boundary aligns publication and the claimed break at once.
  **Pre-declared fallback** (only if the pre-2002 splice extension fails its
  audit): IS 2003-01 → 2015-12, ~104 events.
- **Out-of-sample: 2016-01 → 2024-12** (~72 events). **Contains the full
  2016–2019 dead zone (~32 events) by construction** — no cherry-picking the
  2020–2024 revival (~40 events). Entirely post-publication, entirely on SIP
  prints.
- **Walk-forward: 2025-01 → present, unread until the OOS verdict.** ~12 events to
  date; WF numbers are the ones that would count for any paper decision.
- **What "working" looks like (declared now):** most events small moves either
  way, P&L carried by a modest positive mean; hit rate ~55–65%; an occasional
  −1R to −2.5R announcement-day loss is *normal operation*, not failure — failure
  is defined by the locked bars above, nothing else.

## Known failure modes

Regimes where this should lose, and what limits the damage:

- **Low-uncertainty / telegraphed-policy regimes (the documented quiet failure).**
  When the outcome is fully priced (ZLB forward-guidance era, long unchanged-rate
  stretches), there is no uncertainty to be paid for resolving and the premium
  should be ~0 while costs still accrue. This is not a hypothetical — it is
  Kurov's refereed 2016–2019 finding, and that era sits inside the OOS on purpose.
- **Hawkish-surprise announcement days (the signature acute loss).** The window
  holds *through* the 14:00 statement and press conference; a hawkish surprise in
  a hiking cycle (2022-style) can close the day −2% to −3%, realized in full with
  no stop possible. Structurally, this book is short hawkish surprises for the
  final two hours of every hold. *Bounding:* gap-budget sizing (`G` ≥ 5%), the
  worst-event ≤ 2.5R bar, the 2R day lock, the 5% kill switch.
- **Onset migration / crowding (the most likely quiet failure post-publication).**
  If front-running has pushed the drift into T−2 or the T−1 morning (Boguth's
  finding), the close(T−1) entry buys after the move is done. The
  close(T−2)→close(T−1) diagnostic makes this visible; **it is never a license to
  move the entry.** Fourth-published-then-gone-confirmation risk is priced in via
  the fully post-publication OOS.
- **Small-sample outlier dominance.** 72 OOS events; one crisis-adjacent event
  (COVID-era meetings, a CPI-shock coincidence) moves the mean by ~±5 bps and the
  Sharpe by ~±0.15. Median/trimmed diagnostics expose it; scored numbers never
  exclude anything.
- **Stress clustering with the rest of the book.** The hypothesis says the premium
  is largest when uncertainty is high — i.e., P&L (and tail risk) concentrates in
  exactly the tapes where the overnight-long book's gap risk is largest, and on
  shared nights. *Bounding:* the overlap policy (one shared gap exposure on
  overlap nights), overlap reporting, capped notional.
- **Calendar construction errors (silent systematic garbage).** A wrong `T` on
  two-day meetings, a missed cancellation, or an off-by-one `T−1` mapping corrupts
  every event silently. *Bounding:* the blocking calendar audit (events/yr,
  Tue/Wed check, spot-checks vs published lists, exchange-calendar mapping
  verification) before the pregate.
- **Ex-div coincidence.** FOMC meetings cluster near SPY's quarterly third-Friday
  ex-dates; an unadjusted or mis-adjusted series books the mechanical ex-div drop
  as event P&L. *Bounding:* the self-adjusted audited splice is mandatory;
  ex-div-spanning events tagged in reporting.
- **Yahoo-era print quality (IS only).** The 1994–2015 segment rides Yahoo raw
  prints; crisis-day prints can be off (house finding: up to 279 bps divergence on
  2020-03-12 where both vendors exist). *Bounding:* the extension audit; and the
  verdict-deciding OOS/WF eras contain zero Yahoo data.
- **MOC mechanics.** Missed 15:45 cutoffs or rejected MOC orders would make live
  fills diverge from auction prints — already exercised by the overnight-long
  paper path; re-verified in any paper phase (out of scope for this spec's
  verdict).

## Sign-offs (resolved 2026-07-06 — criteria frozen from this point)

All nine pending decisions were put to the user 2026-07-06, before any data was
read, and resolved as follows. The LOCKED design (SPY only / long only /
close(T−1)→close(T) window, pre-registered once with no sweeps ever / scheduled
meetings only with the point-in-time cancellation rule / MOC both legs /
unconditional — no uncertainty gate / diagnostics never promotion paths) was never
on the list — it was fixed at drafting.

1. **Sizing — SIGNED OFF: `R = 0.5%`** with gap budget `G = max(3·σ_20d, 5%)`
   (typical ~10% notional; ~25 bps of equity/yr honest contribution at full
   hypothesis strength — accepted with that arithmetic on the table).
2. **Cost bar — SIGNED OFF: 2.0 bps round trip LOCKED** + the pre-registered
   **1.5× companion (3.0 bps)** the OOS must survive.
3. **Windows — SIGNED OFF:** IS **1994-01 → 2015-12** / OOS **2016-01 → 2024-12**
   (dead zone mandatorily inside) / WF **2025-01 →, unread until the OOS verdict**;
   **fallback IS 2003-01 → 2015-12** pre-declared if the splice extension fails
   its audit.
4. **Pregate reproduction bar — SIGNED OFF: REJECT if `EDGE(IS)` < 20 bps/event**
   (in addition to the ≥ 2.0 bps cost-bar rule).
5. **Benchmark gates — SIGNED OFF:** conditional-edge gate kept (`EDGE(OOS) ≥ 2.0
   bps`, ≥ 3.0 at 1.5× costs); the **beat-SPY-B&H net-Sharpe gate WAIVED** with
   recorded rationale (see the struck bar #3 in the table above) — the fixed
   zero-filled 0.7 bar and the conditional-edge gates carry the strictness.
6. **Success bars — SIGNED OFF as a set:** OOS net zero-filled Sharpe ≥ **0.7**;
   max OOS DD ≤ **6·R**; worst event ≤ **2.5·R**; ≥ **64** filled OOS events else
   inconclusive-reject; decay guard ≤ 50%; no-rescue clause on per-era splits.
7. **Kill switch — SIGNED OFF: 5%** peak-to-trough equity.
8. **Overlap policy vs overnight-long — SIGNED OFF:** ≤ ~8 overlap nights/yr
   treated as one shared gap exposure against a single 2·R overnight budget;
   unconditional daily-correlation acceptance **< 0.15**; mandatory reporting.
9. **Data tasks — SIGNED OFF as blocking, before the pregate:** (a) extend the
   audited splice to 1993-06 with the same audit (existing file starts
   2002-09-03); (b) build and commit `strategies/fomc-drift/fomc_calendar.csv`
   (1994 → present) with the blocking calendar audit (events/yr, Tue/Wed check,
   ≥20 spot-checks vs published lists, T−1 mapping verification).

**Next step per the funnel:** blocking data tasks (9a, 9b) → `scripts/pregate_fomc.py`
on the IS window only, outside the engine; OOS and WF stay unread. Expected outcome
per the lab's base rate: reject at the reproduction bar or the cost bar — a fine
outcome that costs one session.
