# Strategy: rsi-5050-brain

- **Status**: **retired — REJECTED at Phase 0 (spec validation) 2026-08-30** by the
  pre-registered separability gate: CV mean gross of selected trades **+0.007 bps** vs
  the locked 2.0 bps bar (n=301 selected of 767, 5 chronological folds). EOD precision
  did lift 1.56× (0.1317 → 0.2060) but did not convert to return — the EOD label is
  partly a clock, not a regime. Evidence and post-mortem:
  `experiments/rsi-5050-brain/2026-08-30-phase0/`. **No LLM arm was built.** OOS
  (2022-2024) and WF (2025→) were never read and are returned unspent.
  History: spec approved/FROZEN 2026-08-30 with all 17 features and the gate written
  down before the script existed; rejected the same day.
- **Created**: 2026-08-30
- **One-liner**: Re-run the retired `rsi-5050` mechanical signal unchanged, and insert a
  single **veto-only** discretionary layer (an LLM "brain") at the signal-bar close that
  decides whether each armed breakout is taken — testing whether the untranscribed
  trade-selection overlay, named in rsi-5050's own post-mortem, is where the edge lived.

> **Provenance.** `strategies/rsi-5050/SPEC.md` (retired 2026-07-05) formalized the
> user's own discretionary Dow method. It was REJECTED at the pregate: IS mean gross
> **+0.304 bps** vs a 3.5 bps cost bar (n=767, t=0.64). Its post-mortem recorded the
> hypothesis this spec now tests:
>
> *"the mechanical rules as written carry no edge — any edge in the user's remembered
> discretionary experience lived in the untranscribed overlay (trade selection,
> timing), not in these rules."*
>
> This is **not** a revival of rsi-5050 and **not** a tuning campaign on its parameters.
> The mechanical layer is inherited byte-for-byte and is not a free variable. The only
> new object under test is the decision layer.

## Hypothesis

**Effect.** The rsi-5050 trade population is a **mixture of two populations**, and the
mechanical rules take both indiscriminately. From `experiments/rsi-5050/2026-07-05-pregate/results_5min.json`
(IS 2018–2021, n=767):

| Exit type | n | share | mean gross | hit rate |
|---|---|---|---|---|
| **EOD** (RSI never recrossed; rode to the close) | 101 | **13.2%** | **+23.50 bps** (t=12.19) | **1.00** |
| **recross** (chop; stopped or recrossed out) | 666 | 86.8% | **−3.21 bps** (t=−11.59) | 0.16 |
| blend (what the mechanical strategy earns) | 767 | 100% | +0.30 bps | 0.27 |

Every EOD trade was a winner. The claim is that **trend sessions and chop sessions are
distinguishable ex ante** from context available at the signal bar's close, and that the
ATR(5) band — a single variable read on a single bar — is too crude an instrument to do
it. A richer contextual judgment should raise the EOD share of taken trades.

**Mechanism — who is on the other side?** Honestly: **this layer is not a new source of
edge and no new counterparty is claimed.** The mechanical hypothesis (order-flow
persistence after a regime flip, plausible only in elevated-vol directional sessions)
is inherited unchanged and remains weakly-motivated. What is claimed is narrower and
falsifiable: *the conditional distribution of that effect varies with observable
session context, and the mechanical rules discard that context.* If the mixture is not
separable ex ante, this spec fails at Phase 0 and no LLM is built.

**The arithmetic target (LOCKED — this is the whole experiment).** With `p` = the share
of taken trades that are EOD-exit trades:

```
mean(taken) = p·23.50 + (1−p)·(−3.21)

p = 13.2%  →  +0.30 bps   base rate — the mechanical strategy today
p = 25.1%  →  +3.50 bps   break-even against the locked 3.5 bps cost bar
p = 31.7%  →  +5.25 bps   clears 1.5× costs (house sensitivity bar)
```

**The brain must roughly double EOD precision (13.2% → ~25%) to break even, and reach
~32% to pass with margin.** Any result is scored against these numbers, which were
computed and written down before any Phase 0 code existed.

**Adversarial notes — read before falling in love:**

1. **The base rate for this lab is rejection.** 13 candidates, 13 deaths. The prior
   here is a 14th. This spec is written to make that outcome cheap and fast (Phase 0
   is one session) rather than to avoid it.
2. **The overlay may be a memory artifact.** Remembered discretionary success is
   systematically biased — losses are forgotten, wins are narrativized. The user's
   recalled edge may never have existed at the size recalled. This spec cannot
   distinguish "the overlay was real" from "the overlay is misremembered"; it can only
   test whether *a* separating overlay exists in the data now.
3. **Multiple-testing risk is the main methodological threat.** Screening features
   against a 767-row outcome invites finding one that separates by chance. Mitigations
   are locked below: the feature list is frozen in this spec before any code is
   written, every feature is reported (not just survivors), the primary metric is
   cross-validated rather than in-sample, and the verdict is spent on an unread window.
4. **The `by_tod` open bucket is a known post-hoc finding and is NOT evidence.** The IS
   run showed the open bucket (n=36) at +4.21 bps (t=1.88, hit 0.444) vs midday +0.10
   (n=457) and close +0.13 (n=274). rsi-5050's spec correctly forbade using it to revive
   the strategy. It is admissible here **only** as one pre-registered feature among many
   in a Phase 0 screen whose verdict is taken on a window never read. It may not be
   promoted to a standalone rule, and n=36 is not a result.
5. **An LLM that cannot beat a logistic regression is not worth deploying.** Phase 1
   runs three arms and the LLM must beat the simple-rule arm to proceed (user decision,
   2026-08-30).
6. **A veto layer cannot rescue a population with no separable structure.** If Phase 0
   finds nothing, the honest outcome is reject-at-spec-validation — no LLM arm, no
   prompt engineering, no "the model might see what regression can't." That escape
   hatch is closed here, in advance.

## The inherited mechanical layer (NOT a free variable)

Everything in `strategies/rsi-5050/SPEC.md` under *Universe & timeframe*, *Signals*,
and *Risk* is inherited **unchanged and unabridged**: DIA 5-min RTH bars; RSI(21)
Wilder; ATR(5) Wilder with first-bar-of-session `TR = H−L`; band 4.5–6.8 bps;
`buffer = max(0.04·ATR5, $0.02)`; buy/sell-stop at the signal bar's extreme ± buffer;
protective stop at the opposite extreme ∓ buffer, fixed, never trailed; pending-order
cancellation on adverse recross / 10 bars / 15:30 cutoff; exits on RSI recross at next
bar's open, protective stop, 3-consecutive-bar vol collapse below 4.5 bps, and forced
flat at 15:55 ET; entry window 09:45–15:30 ET; one position at a time, no pyramiding,
re-entry requires a brand-new cross; indicators run continuously across sessions with
250-bar warm-up; worst-case intrabar convention (entry-then-stop in the same bar takes
the full loss).

**No parameter of the mechanical layer may be changed by this spec, at any phase, for
any reason.** Changing one makes the inherited IS result non-comparable and re-opens
every multiple-testing question this design exists to control. If the mechanical layer
turns out to need a change, that is a different candidate with a different spec.

## The decision layer (the only new object)

- **Decision surface**: exactly one binary decision per **armed** signal — the 1,112 IS
  signals that passed the ATR band and time window. `TAKE` or `SKIP`.
- **Veto-only** (user decision, 2026-08-30). The brain may **not**: create signals the
  mechanical layer did not arm; alter entry, stop, or exit levels; alter position size;
  re-enter after a stop; or revise a decision once the order is armed. Sizing stays with
  `core/risk` under the inherited rule. This keeps the mechanical population an exact
  baseline, so lift is a difference of two means over the same signal set.
- **Decision time**: the close of signal bar *s*, using only completed-bar data at or
  before *s*. Any feature reading bar *s+1* or later is a lookahead bug and voids the run.
- **Latency budget**: the order must be armed before bar *s+1* opens — a 5-minute
  window (300 s). Locked budget: **≤ 60 s** per decision end-to-end. A decision that
  times out is recorded as `SKIP` with reason `timeout` and counted in the results;
  it is never retried or silently dropped.
- **Output contract** (every decision, every phase, whether taken or skipped):
  `verdict` (TAKE/SKIP), `confidence` (0–100), `thesis` (prose), `invalidation`
  (what would make this wrong), `features` (the frozen vector), `prompt_version`
  (file hash), `model_id`, `latency_ms`.
- **Skips are logged as first-class rows.** They are the mechanical arm's trades and
  supply the counterfactual; a run that logs only taken trades is void.

## Data requirements

- **Bars**: `data/DIA_5m.parquet` (Alpaca SIP, raw, RTH close-stamped,
  2017-12-01 → 2026-07-02) — already on disk. Context features additionally require
  SPY and QQQ 5-min bars over the same range, and a daily VIX series.
- **Data-verification cell (pre-declared, must run before any scoring)**: record
  sha256 of every parquet consumed; confirm full non-null OHLCV over the range;
  confirm the rebuilt per-trade log reproduces the inherited aggregate exactly —
  **n = 767, mean_bps = 0.304, EOD n = 101, recross n = 666**. A mismatch halts the
  phase; it means the mechanical layer was perturbed and nothing downstream is valid.
- **No new data vendor, no news feed, no fundamentals.** Deliberately: the hypothesis
  is that context *already in the price/vol state* separates the mixture. Adding an
  outside data source would be a different hypothesis and would confound the test.

## Windows (LOCKED)

| window | range | status |
|---|---|---|
| **IS** | 2018-01-01 → 2021-12-31 | already read by rsi-5050's pregate; used for Phases 0–1 |
| **OOS** | 2022-01-01 → 2024-12-31 | **UNREAD** — one look, spent at Phase 2 |
| **WF** | 2025-01-01 → present | **UNREAD** — reserved; not read by any phase of this spec |

rsi-5050 died on IS alone and no engine code was ever written, so both later windows are
uncontaminated. **This is the scarcest asset in the lab and the entire phase structure
exists to protect it.** Phases 0 and 1 may read IS without limit. OOS is read once,
after Phase 2's bars are frozen. WF is not read by this spec at all.

## Frozen feature set (Phase 0 and Phase 1 both draw from exactly this list)

All computed from completed bars at or before signal bar *s*. Frozen now so the Phase 0
screen cannot be tuned after seeing results. Every feature is reported in the results
table whether or not it separates.

**Signal-bar geometry**
1. `atr5_bps` — position within the 4.5–6.8 band
2. `atr5_slope_3` — ATR(5) change over the prior 3 bars (regime expanding or collapsing)
3. `bar_range_over_atr` — signal bar's range ÷ ATR(5)
4. `rsi_jump` — RSI(21) at *s* minus RSI(21) at *s−1* (how decisively 50 was crossed)
5. `rsi_bars_since_last_cross` — bars since the previous midline cross (chop frequency)
6. `buffer_over_range` — required breakout buffer ÷ signal-bar range (how far price must travel)

**Session context**
7. `minutes_since_open` — and the `by_tod` bucket (open / midday / close) as a categorical
8. `ret_since_open_bps` — session return to *s*, signed to the signal direction
9. `dist_from_vwap_bps` — signed distance from session VWAP
10. `session_range_over_adr` — session range so far ÷ 20-day average daily range
11. `overnight_gap_bps` — signed gap, prior close → session open

**Cross-sectional / macro**
12. `spy_align` — sign agreement of SPY's concurrent 5-bar return with the signal direction
13. `qqq_align` — same for QQQ
14. `spy_dia_corr_20` — 20-bar rolling correlation of DIA and SPY 5-min returns (is the tape one-way?)
15. `vix_level`, `vix_chg_1d`
16. `is_fomc_day`, `days_to_fomc` — from the existing `strategies/fomc-drift/fomc_calendar.csv`
17. `day_of_week`

**Prohibited**: anything derived from bars after *s*, realized outcome, exit type,
same-session later prints, or any aggregate computed over the full sample (e.g.
z-scoring against IS-wide statistics rather than a trailing window).

## Phase gates (LOCKED before any code)

### Phase 0 — separability audit (IS only, no LLM)

Rebuild the per-trade log from `scripts/pregate_rsi5050.py` with per-trade CSV output
(same params, same window; must satisfy the data-verification cell), attach the frozen
feature set, and test whether the EOD/recross mixture is separable ex ante.

- **Method**: 5-fold cross-validation **within IS only**. Primary model: logistic
  regression on the frozen features predicting `EOD vs recross`, with a selection
  threshold set per fold to retain **40% of trades — LOCKED, single value, no sweep**
  (Q1). Report out-of-fold results only.
- **Primary gate**: cross-validated **mean gross of selected trades ≥ 2.0 bps**
  (vs +0.304 bps for all 767), retaining **≥ 150 trades**.
- **Secondary (diagnostic, not gating)**: cross-validated EOD precision (base rate
  13.2%); full univariate table for all 17 features with Benjamini–Hochberg correction;
  breakdown by side and by time-of-day bucket.
- **Threshold rationale (recorded now)**: 2.0 bps sits below the 3.5 bps cost bar on
  purpose. Phase 0 uses deliberately crude linear tools; it asks "is there separable
  structure at all", not "is this tradeable". If a plain logistic already clears 3.5 bps,
  that is a finding in its own right and the LLM's necessity is in question (see Phase 1).
- **On FAIL**: **reject at spec validation.** No LLM arm, no feature additions, no
  threshold relaxation, no "try a tree model". Status → retired, post-mortem in this file.

### Phase 1 — retrospective LLM adjudication (IS only)

Only if Phase 0 passes. Replay the 1,112 armed IS signals through three arms:

| arm | description |
|---|---|
| **A — mechanical** | take everything (the inherited baseline, +0.304 bps) |
| **B — simple rule** | the Phase 0 logistic, out-of-fold |
| **C — brain** | LLM verdict on the frozen feature vector **plus the last 40 completed bars** (Q2: both, LOCKED — chart-shape reading is part of the overlay under test; the widened contamination surface is accepted and is why Phase 1 is directional only) |

- **Contamination control**: prompts are anonymized — no ticker, no date, no absolute
  price levels; instrument described only as "a large US equity index ETF". Contamination
  is materially lower here than for single-name catalysts (an ordinary DIA session is not
  a memorable event) but is **not zero**. Phase 1 is therefore **directional evidence for
  building the rubric, never a verdict.** No promotion decision rests on it.
- **Gate**: arm C mean gross > arm B mean gross, out-of-fold, on the same retained
  count (± 10%). **If the LLM cannot beat the logistic, stop** (user decision,
  2026-08-30) — ship the logistic as a cheap mechanical filter under its own spec, or
  retire, but do not build an LLM pipeline that adds cost and non-determinism for nothing.
- **Also recorded (not gating at Phase 1)**: confidence calibration curve, cost per
  decision, latency distribution, the rate of `timeout` skips, and the **repeat-run
  agreement rate** on a 100-signal subsample (reporting reference 95%, Q4).
- **Confidence threshold (Q3, LOCKED)**: the TAKE threshold is **calibrated on IS at
  Phase 1 and then frozen as a single number** before Phase 2. It is not fixed at 50 a
  priori, and it may not be re-derived after the OOS window is read.
- **Determinism**: `temperature = 0`, `model_id` pinned and logged per decision. A model
  change invalidates every calibration number and requires a re-run — the same
  vintage discipline the execution-cost study had to learn the hard way.

### Phase 2 — the one pre-registered OOS look (2022–2024)

**Entry precondition (Q4, LOCKED — hard gate).** Phase 2 may not begin unless the
Phase 1 repeat-run agreement rate is **≥ 90%**. Rationale: the OOS look is spendable
exactly once, and a decision stream that does not reproduce cannot support a verdict.
Failing this is an **operational stop, not a strategy rejection** — the correct response
is to fix determinism (or report the strategy as non-reproducible) with OOS still unread.

Everything frozen and committed before the window is touched: prompt file (hashed),
model id, feature set, the calibrated confidence threshold, and the arm to be scored.
Then one run.

| # | Locked bar | Threshold |
|---|---|---|
| 1 | Mean gross per taken trade | **> 3.5 bps** (the locked cost bar) |
| 2 | Net-positive at 1.5× costs | **> 0** at 5.25 bps |
| 3 | EDGE vs the mechanical arm on the identical signal set | **> 0** |
| 4 | Both sides positive separately | long **and** short |
| 5 | Taken-trade count | **≥ 100** |
| 6 | Decay guard | OOS lift ≥ 50% of IS lift |
| 7 | EOD precision of taken trades | **≥ 25.1%** (the break-even `p`) |

**No-rescue clause (binds on FAIL):** no threshold shopping, no prompt revision, no
model swap, no re-run on the same window, no instrument shopping, no bar-size variant,
no "the OOS regime was unusual" carve-out. One look, one verdict. WF stays unread.

### Phase 3 — paper (only on a Phase 2 PASS)

- **Blocking prerequisite — data feed.** Free-tier Alpaca serves SIP only for windows
  **ending > 15 minutes ago**; a 5-min strategy must act on a bar that closed ~5 minutes
  ago, and DIA on IEX (ADV 3–4M) is both thin and mismatched against consolidated fills.
  **Paper operation requires re-subscribing to Algo Trader Plus.** Do not subscribe
  before Phase 2 passes; Phases 0–2 use historical bars and cost nothing.
- Run **both arms live in parallel** on separate paper accounts (mechanical and
  brain-gated, identical signals and sizing) so lift is measured, not inferred.
- Inherited risk limits apply unchanged: daily halt after 3 full stops or −0.5% of
  equity; 10% drawdown kill switch requiring manual review.
- Live never by default (hard rule #4); a live promotion needs its own explicit sign-off.

## Cost assumptions

Inherited from rsi-5050 unchanged: **3.5 bps modeled round trip** on DIA 5-min, with the
1.5× sensitivity companion at 5.25 bps pre-registered as a gating bar (#2 above). The
brain adds an operating cost (LLM inference, ~1,100 decisions/yr on IS scale, ~278/yr
live) which is **reported in Phase 1 but not charged against per-trade bps** — it is a
fixed operating expense, not an execution cost, and conflating them would flatter or
punish the strategy depending on book size. Record it in dollars per year.

## The learning loop (Phase 3+ only, specified now to prevent scope creep)

Logging trades does not by itself improve a model. Only these are in scope, in order:

1. **Confidence calibration** — map stated confidence to realized EOD rate; use the
   calibrated value for the threshold. Pure statistics, no model change.
2. **Retrieval of precedents** — embed each setup; inject the 5 most similar past
   setups *with outcomes* into the prompt. Within-model-version experience accumulation.
3. **Rubric evolution** — monthly, proposals generated from the worst decisions,
   **human-approved only**, each version a new hashed file. Mirrors the gated `tune`
   discipline: automated proposal, evidence-gated adoption.
4. **Fine-tuning** — explicitly **out of scope** below 500 labeled outcomes.

Any of 1–3 changes the system and therefore requires a fresh out-of-sample window
before it can claim credit. There is no free re-scoring on data already read.

## Known failure modes

- **Chop regimes with elevated ATR** — the band passes, the tape reverses, and the brain
  has no reason to veto. This is the −3.21 bps population and is where the strategy
  bleeds; limited by the fixed stop and the daily loss limit.
- **The brain vetoes the tail.** EOD trades are 13.2% of trades and 100% of the profit.
  A cautious brain that skips ambiguous setups may preferentially skip the very trades
  that pay — this is the inverse-selection risk, and Phase 2 bar #7 exists to catch it.
- **Over-selection.** Retaining too few trades raises mean bps while destroying
  significance; bar #5 (≥100 trades) is the guard.
- **Model drift** — a silent provider-side model change alters the decision stream
  without any code change. Mitigated by pinning `model_id` per decision and treating a
  change as a re-run trigger.
- **Non-determinism** — even at temperature 0, identical prompts may not yield identical
  verdicts. Two-tier control (Q4): Phase 1 **reports** repeat-run agreement on a
  100-signal subsample against a 95% reference; Phase 2 **cannot start** below 90% (see
  its entry precondition). A stream that does not reproduce cannot justify spending the
  one OOS look.

## Open questions — ALL RESOLVED 2026-08-30 (spec frozen)

1. **Phase 0 retention fraction** → **40%, single value, no sweep.** Alternatives
   (30%/50%) rejected: sweeping the retention fraction is itself a tuning dimension and
   would reintroduce the multiple-testing risk this design exists to control.
2. **Does arm C see raw bars?** → **Yes — 40 completed bars plus the frozen feature
   vector.** Chart-shape reading is part of the discretionary overlay under test, so
   withholding bars would test a different hypothesis. Accepted cost: a wider
   contamination surface, already the reason Phase 1 is directional-only.
3. **Phase 2 confidence threshold** → **calibrated on IS at Phase 1, then frozen** as a
   single number before the OOS window is read. Never re-derived afterwards.
4. **Repeat-run agreement floor** → **two-tier.** 95% is a Phase 1 *reporting*
   reference; ≥90% is a **hard entry gate on Phase 2**. Refined from the original
   either/or: reporting alone is too weak to protect the one look, while a hard Phase 1
   gate would kill the candidate for an operational defect rather than absence of edge.

## Decisions record

- 2026-08-30 — brain is **veto-only**, not sizing (user).
- 2026-08-30 — Phase 1 arm C must beat arm B, else stop (user).
- 2026-08-30 — mechanical layer inherited unchanged; not a free variable at any phase.
- 2026-08-30 — WF (2025→) is not read by any phase of this spec.
- 2026-08-30 — Algo Trader Plus re-subscription deferred until a Phase 2 pass.
- 2026-08-30 — Q1 resolved: Phase 0 retention fixed at 40%, no sweep (user took
  recommendation).
- 2026-08-30 — Q2 resolved: arm C sees 40 raw bars + the frozen feature vector (user
  took recommendation).
- 2026-08-30 — Q3 resolved: Phase 2 TAKE threshold calibrated on IS, then frozen (user
  took recommendation).
- 2026-08-30 — Q4 resolved: repeat-run agreement is a 95% reporting reference at Phase 1
  and a ≥90% hard entry gate on Phase 2 — refined from the two options offered, since
  reporting alone does not protect the one look and a Phase 1 hard gate would reject the
  candidate for an operational defect rather than absence of edge (user took recommendation).
- 2026-08-30 — **SPEC APPROVED AND FROZEN by user.** Phase 0 implementation authorized;
  it must satisfy the data-verification cell (n=767, +0.304 bps, EOD 101 / recross 666)
  before any scoring is reported.

## Post-mortem (2026-08-30)

Phase 0 ran once, on IS only, and failed the locked gate. Full numbers and the
diagnostic tables are in `experiments/rsi-5050-brain/2026-08-30-phase0/notes.md`.

**What was tested and what happened.** The data-verification cell reproduced the
inherited pregate exactly (767 trades, +0.304 bps, EOD 101 / recross 666), so the
mechanical layer was intact and the result is a statement about the hypothesis. A
logistic regression on the frozen 17-feature set, 5 chronological folds, threshold
taken from the training fold only, selected 301 trades averaging **+0.007 bps** —
against a 2.0 bps bar, and *below* the +0.495 bps of the trades it rejected. No fold
exceeded +0.7 bps; two were negative.

**Why it failed — the Hypothesis section contained a design error.** This spec framed
the population as a mixture of "trend sessions" (EOD exits) and "chop sessions"
(recross exits) and made EOD precision the object of selection. That framing is
wrong, and the run proves it: `corr(minutes_since_open, hold_bars) = −0.971`, so a
signal fired late in the session is *mechanically* more likely to be labelled EOD
simply because fewer bars remain in which RSI can recross. Those trades also have
less time to run — late-session EOD trades pay +16.43 bps over a 12-bar median hold
versus +35.72 bps over 30 bars at midday. The classifier duly found the clock
(`f07_minutes_since_open` and `tod_close` were the two strongest univariate features)
and precision rose without returns following.

**The gate design is what saved this from being a false positive.** Had the gate been
written on EOD precision — the metric the Hypothesis section emphasised — this would
have registered a 1.56× lift and passed to an LLM arm on a pure artifact. It was
written on mean gross bps instead, which is what pays, and it caught the divergence.
Recorded for future specs: **score the money, never the label.**

**On the brain hypothesis itself.** This is a rejection of *one operationalisation* on
*one instrument at one bar size*: DIA 5-min, target = exit type, IS 2018-2021. It is
not a general finding that discretionary overlays are worthless. But it is a genuine
negative on the specific claim rsi-5050's post-mortem raised — that the untranscribed
overlay lived in observable session context — because the cross-sectional, macro, and
signal-geometry features that overlay would be built from (`spy_align` p=0.99,
`qqq_align` p=0.89, `rsi_jump` p=0.75, `overnight_gap` p=0.58, `ret_since_open`
p=0.57) are indistinguishable from noise against this target.

**Cost of the test: one session, no LLM spend, no data subscription, both later
windows unspent.** That was the point of gating Phase 0 ahead of any AI plumbing.
