# Live auction-fill mechanics test — PRE-REGISTERED PROTOCOL

> **DECISION 2026-07-07: NOT PROCEEDING — protocol shelved, no build, no live
> order.** After quant-review clarified that this test measures broker *fill-vs-
> print* fidelity (≈0 by construction) and CANNOT touch the *print-vs-mid premium*
> that shelved overnight-long (a market property, identical paper vs live), the user
> decided the narrow, lot-size-bounded "can Alpaca fill odd-lot auctions" capability
> was not worth the ~$800 + live-broker build + second review — since it does not
> revive the strategy it was aimed at. Overnight-long stays SHELVED on market
> structure. The live-broker path is NOT built; `paper.py` remains paper-only.
> Protocol kept for the record (reusable if a future auction strategy ever needs the
> capability validated). Effort redirected to a fresh candidate.

**Status: method locked before any live order is placed.** This document is the
plan; nothing runs until (a) quant-reviewer signs off on this protocol AND the
live-broker code diff, (b) the account is funded, and (c) the user gives the
per-session live confirmation (hard rule #4). Written first; results appended
afterwards and the pass/fail bar is not edited to fit them.

- parent git commit: `3839a6e`
- author: locked 2026-07-07 11:34 CEST
- **quant-review 2026-07-07: SIGN OFF WITH CHANGES — all 7 required edits (#1
  firewall/orthogonality, #2 odd-lot FAIL scoping, #3 exact PASS counts, #4 half-day
  schedule, #5 cash account, #6 stuck-position path, #7 separate live class)
  incorporated below; observation added as the open design choice. Cleared to build
  the live-broker + harness diff for a SECOND review; no live order until that diff
  is reviewed.**
- thread parent: `../2026-07-07-0914-quote-validation/notes.md` (study #2) and its
  post-review addendum — read that first; this protocol exists *because* of its
  conclusion.

## Scope — what this is, and (louder) what it is NOT

This is a **de-minimis execution-MECHANICS test**. It answers one infrastructure
question that no backtest, no paper run, and no offline quote study can:

> **Can our broker stack actually execute in the closing/opening auction, and at
> what realized deviation from the official consolidated print?**

Paper answered half of it by failing: Alpaca **paper** returned the QQQ MOC
`expired / qty:0` at the 16:00 close (study #2, 2026-07-06). The open question is
whether a **real-money** Alpaca CLS/OPG order fills in the auction at all, and if
so, how close to the official print.

**Explicitly OUT of scope (quant-reviewer 2026-07-07, binding):**

- This is **NOT** a reopening of the overnight-long edge verdict. Overnight-long
  stays **SHELVED**. Nothing measured here can un-shelve it.
- Success is measured in **fill-vs-print basis points and fill reliability — never
  in P&L.** At one share the P&L is meaningless and sits entirely inside the cost
  CI; the reviewer already rejected the "tiny P&L proves the edge" framing as
  motivated reasoning. We do not repeat it.
- The **product of this test is a validated (or invalidated) execution
  capability** for the lab — "can our broker fill an odd-lot MOC/MOO order in the
  auction" — reusable by any future auction-based strategy. It is not a rescue
  mission for one strategy.
- **CRITICAL (quant-review #1) — this test measures a DIFFERENT AXIS than the cost
  that shelved overnight-long, and cannot inform that verdict.** What we measure is
  *fill-vs-print* (broker execution fidelity): does our order land at the official
  cross? A real MOC fills *at* the closing cross by construction, so this number is
  ≈ 0 and the only real content is the binary "did it fill at all." What shelved
  overnight-long was *print-vs-mid* — Measurement A, the auction **premium** (the
  official print itself sitting off the pre-auction NBBO mid;
  `../2026-07-07-0914-quote-validation/notes.md:43-53`). That premium is a **market
  property, identical on paper and live** — this live test does not and cannot
  measure it. **Therefore no result here — pass or fail, tight fills or wide — moves
  the overnight-long edge verdict one inch.** It stays SHELVED on market structure,
  not on broker mechanics.
- Any future decision to revisit whether overnight-long's edge survives *realized*
  cost would be a **separate, independently pre-registered** study grounded in the
  print-vs-mid premium, not folded into this one and not informed by it.

## Instrument & sizing

- **QQQ, exactly 1 whole share.** Auction (MOC/MOO) orders require whole shares —
  fractional shares are not auction-eligible, so a fractional order cannot test the
  mechanism. QQQ closed **~$712.60** (2026-07-06), so:
  - **$300 is insufficient** — it cannot hold even one share.
  - **Fund ≈ $800**: one share (~$713) + buffer for the overnight mark and fees.
  - Overnight dollar risk ≈ one QQQ share's overnight move (~±$4–11 on a typical
    night; a 3σ gap ≈ ±$30). This is the de-minimis exposure the carve-out permits.
- Optional: **2 shares (~$1,500)** gives two independent fill datapoints per night
  and halves the per-night measurement variance. Not required; 1 share is a valid
  datapoint because the auction is deep enough that 1 share has zero market impact,
  so the fill *price* is representative regardless of quantity.
- **Hard cap = 1 share (or 2 if chosen)** enforced in the harness AND as an Alpaca
  account-level constraint. The book can never scale beyond the funded share count.
- **Account type: CASH account — no margin, no shorting, no PDT (quant-review #5).**
  The real exposure cap here is *funding*, not the risk engine: the mechanics
  harness places a fixed 1 share unconditionally and **bypasses
  `RiskManager.size()`**, so the 15% kill switch and 2R daily lock
  (`core/risk/sizing.py:117`) are nominal — they never fire on a fixed 1-share book.
  A cash account makes the funding cap real (≈$800 = 1 share max) and structurally
  prevents the sell leg from ever opening an accidental short. This is stated
  plainly so no one mistakes the breakers for the guardrail: **the guardrail is the
  cash balance.**

## Order path (reuses existing code; the live endpoint is the only new capability)

Already implemented and unit-tested against a fake broker — the mechanics test does
not invent new order plumbing, it points the existing plumbing at a live endpoint:

- **Buy MOC:** `submit_market(QQQ, 1, is_buy=True, tif="cls")`
  (`core/execution/paper.py:76`), submitted by **~15:40 ET** (decision bar closes
  15:40; Alpaca rejects CLS after 15:50 ET per its docs — 15:40 leaves margin).
- **Sell MOO next morning:** `submit_market(QQQ, 1, is_buy=False, tif="opg")`,
  submitted before **~09:28 ET** (OPG cutoff).
- **Official prints:** `broker.auction_prints(QQQ, day)` → `(official_open,
  official_close)` from the SIP daily bar (`paper.py:112`) — the exact consolidated
  auction print a `cls`/`opg` order settles at. Already SIP-only and
  entitlement-aware (real-time SIP since 2026-07-05).
- **Fill capture:** `wait_fill(order_id)` → `filled_avg_price` (`paper.py:164`),
  PLUS the raw order object's `status` / `filled_qty` to detect the paper failure
  mode (`expired`, `qty:0`, odd-lot rejection).

## Measurement (per night; appended to a dedicated live fill log, JSONL)

The **primary datum is binary** (see next section). The bps below are a
**broker-fidelity diagnostic that is ≈ 0 by construction** (a filled MOC settles at
the cross it is measured against) — logged for completeness, not to produce a cost
number. Per leg, deviation of the **actual live fill** from the **official print**,
in bps (sign: positive = fill worse than the print for us):

- **MOC leg:** `close_fill_bps = 1e4 · (filled_avg_price − official_close) / official_close`
- **MOO leg:** `open_fill_bps  = 1e4 · (official_open − filled_avg_price) / official_open`

**No round-trip "mechanics cost" is computed** (quant-review #1): summing the two
fill-fidelity legs into a cost figure invites comparison against the print-vs-mid
premium that shelved overnight-long, which is a different axis. Fees are irrelevant
to a fidelity check and are omitted here.

Logged per night: `date`, both `order_id`s, submit timestamps, **order status +
filled_qty per leg** (the binary mechanics datum — the point of the test),
`filled_avg_price`, `official_print`, per-leg fidelity bps, and any
rejection/odd-lot/partial event verbatim.

## Pass/fail bar (PRE-REGISTERED, mechanics-scoped — locked now)

The test is about mechanics, so the primary bar is binary (does it fill in the
auction), not a cost threshold.

1. **PRIMARY — binary odd-lot auction availability (the real go/no-go). Exact
   counts, no wiggle room (quant-review #3).** Over N = 10 sessions (20 auctions:
   10 MOC + 10 MOO):
   - **Clean PASS** = **0 expiries / 0 `qty:0` / 0 odd-lot rejections** across all
     20 auctions; every order returns `status: filled` with full `filled_qty`.
   - **Any single expiry/rejection** = **not a clean PASS**: investigate the cause
     and stop; do not average it away or reclassify it after the fact.
   - **Early-abort:** stop immediately on **the first expiry within the first 3
     sessions** — do not burn two weeks confirming a dead mechanism.
   - **Interpretation is LOT-SIZE-BOUNDED (quant-review #2).** 1 share is an *odd
     lot*, and odd-lot auction ineligibility is a known, code-acknowledged mode
     (`core/execution/live_runner.py:384`). A round-lot (≥100 sh ≈ $71k) test is
     outside the de-minimis cap, so:
     - **PASS** proves *odd-lot* MOC/MOO auctions fill on Alpaca live — exactly what
       a 1–13-share strategy needs. Valid, useful.
     - **FAIL** proves only that **odd-lot auction execution is unsupported on
       Alpaca live.** It **does NOT** license "Alpaca live can't do auctions" or
       "we need IBKR" — that conclusion is confounded with lot size and is
       explicitly out of reach of this test.

2. **SECONDARY — fill-fidelity diagnostic (NOT a decision input of any kind).**
   Computed only if PRIMARY passes, and near-vacuous by construction (fill-vs-print
   ≈ 0). Report per leg: signed mean + 95% CI, `abs_p75`, N, outliers named. **It is
   logged for completeness only.**
   - **Do NOT contextualize it against the offline cost estimates** (fill-reference
     or quote-premium) or against the ~1–3 bps RT range (quant-review #1). Those
     measure the print-vs-mid *premium* — a different axis this test cannot touch.
     Juxtaposing a ~0-bps fidelity number against them manufactures the false
     inference "realized cost beats the estimate, so the edge might survive," which
     is the exact motivated-reasoning trap already rejected once.
   - This section **cannot** re-decide overnight-long. Any edge revisit is a
     separate, independently pre-registered study on the *premium*, not here.

## Run schedule

- **N = 10 trading sessions** (~2 weeks) for ~10 independent fill datapoints, or ~5
  sessions at 2 shares. Early-abort clause above overrides the count.
- **Calendar-aware submission (quant-review #4).** Submit MOC relative to *that
  session's actual close* (≈20 min before), MOO before ~09:28 ET, on consecutive
  full sessions regardless of the regime signal. **Early-close (half) days are
  either handled by submitting relative to the 13:00 close or excluded from N** — a
  hard-coded 15:40 submit would land *after* a 13:00 close and manufacture a
  spurious expiry/FAIL. This is a **fixed-schedule mechanics harness, not the
  strategy** (unconditional placement keeps it clearly infra, not alpha, and
  guarantees a datapoint every session).

## Code + governance BEFORE the first order (build gated on quant-review)

Not built yet — flagged here, to be reviewed as a diff before anything runs:

1. **A SEPARATE live broker class (quant-review #7) — not a flag flip.** `paper.py`
   hard-codes `paper=True` (`:38`, "Live trading is intentionally not implemented
   here"). Build a distinct `AlpacaLiveBroker` with its own live endpoint and
   banner; **do NOT** add a `paper=False` path to `AlpacaPaperBroker` — the shared
   class must remain physically unable to reach the live endpoint, so paper code can
   never silently go live.
2. **A dedicated mechanics harness** (not `run_paper.py`'s strategy path): places
   the fixed 1-share MOC/MOO schedule (calendar-aware, per the schedule section),
   hard 1-share cap, live-specific confirmation banner, writes a separate live fill
   log (`experiments/execution-cost-study/live-mechanics-fills.QQQ.jsonl`).
3. **Stuck-position failure path (quant-review #6).** If the MOC fills but the
   next-morning MOO rejects (or the process is down), we hold a share unbounded —
   the exposure this test is meant to bound. The harness **must** replicate
   `OvernightAuctionRunner._exit_leg`'s fallback (`live_runner.py:441`): on OPG/MOO
   failure, flatten with a plain market sell and alert; and it must **never re-enter
   while a prior position is open.**
4. **Separate live credentials** in `.env` (`ALPACA_LIVE_API_KEY` /
   `ALPACA_LIVE_SECRET_KEY`), gitignored, never committed; distinct from the paper
   keys so a wrong key can't silently point paper code at the live account.
5. **CASH account** (no margin/short/PDT) so funding is the real cap (see Sizing).
6. **quant-reviewer sign-off** on this protocol AND the live-broker diff before the
   first live order. Then, and only then, the user funds ~$800 and gives the
   per-session live confirmation each run.

## Open design choice — overnight hold vs zero-overnight (quant-review observation)

The buy-MOC → hold → sell-MOO structure is overnight-long's exact trade shape, which
(a) carries a small overnight gap risk the mechanics question does not require and
(b) visually replicates a shelved strategy. The identical binary datum is obtainable
with **zero overnight exposure**: to test the close, buy intraday at market then
**sell-MOC**; to test the open, **buy-MOO** then sell intraday at market. Same
"did the odd-lot auction leg fill" answer, strictly lower risk, no resemblance to
overnight-long. The only reason to keep the overnight version is fidelity to the
exact path a *future* overnight auction strategy would use — but this test is scoped
as generic infra, so the zero-overnight design is the more consistent default.
**This is the one item left for the user to decide before the build.**

## Risk summary

Max exposure 1 QQQ share (~$713) — overnight if the hold design is chosen, intraday
only under the zero-overnight design. Cash-balance cap (risk engine bypassed;
breakers nominal — see Sizing). Regulatory fees ~pennies. The genuine cost of this
test is the live-broker code and the review, not the market risk.

---

## Results (appended after the run; see metrics.json)

_(pending sign-off + funding + first live session)_
