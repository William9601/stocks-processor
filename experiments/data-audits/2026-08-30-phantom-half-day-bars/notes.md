# Data audit — phantom half-day bars in the standalone diagnostic scripts (2026-08-30)

**Prompted by**: user question — "this repo has an issue where we are back testing on
non-tradable times." Read-only audit; no verdict is changed by it.

**Answer, short**: partly. The *catastrophic* form of the bug is **absent** — every
intraday parquet is strictly RTH, so there is no extended-hours trading in any backtest.
But a narrow form **is real and confirmed**: on half-days the vendor files carry bars
stamped after the official 13:00 close, and **all seven `scripts/pregate_*.py`
diagnostics (plus `scripts/phase0_rsi5050_brain.py`) read parquet directly and do not
filter them**. The engine path does filter them. No recorded verdict flips.

## 1. Extended hours — NOT present

| file | bars | first close | last close | bars/session (min/median/max) |
|---|---|---|---|---|
| DIA_5m | 167,736 | 09:35 ET | 16:00 ET | 48 / 78 / 78 |
| SPY_5m | 137,228 | 09:35 | 16:00 | 66 / 78 / 78 |
| QQQ_5m | 137,051 | 09:35 | 16:00 | 1 / 78 / 78 |
| DIA_3m | 279,583 | 09:33 | 16:00 | 76 / 130 / 130 |
| DIA_15m | 55,967 | 09:45 | 16:00 | 18 / 26 / 26 |

390 RTH minutes = 78 five-minute bars, which is the median everywhere. There are **no
pre-market or post-16:00 bars**. This is the opposite of the sibling `rsi-midline-bot`
repo, where intraday parquets covered 04:00–20:00 and roughly half of all backtest
trades fired at times live could never act.

## 2. Phantom half-day bars — CONFIRMED

On 13:00 ET early closes (July 3rd, day after Thanksgiving, Christmas Eve) the files
carry bars stamped **after** the close, built from thin after-hours prints. DIA_5m:

| date | official close | last bar in file | bars after close | volume after close |
|---|---|---|---|---|
| 2018-07-03 | 13:00 | **16:00** | 17 | 161,787 |
| 2018-11-23 | 13:00 | 15:15 | 10 | 237,875 |
| 2021-11-26 | 13:00 | **16:00** | 24 | 237,074 |
| 2024-11-29 | 13:00 | **16:00** | 18 | 198,373 |
| 2024-12-24 | 13:00 | 15:15 | 10 | 222,065 |

Prevalence across every intraday file:

| file | bars | phantom | % | sessions affected |
|---|---|---|---|---|
| DIA_5m | 167,736 | 231 | 0.14% | 18 |
| DIA_3m | 279,583 | 283 | 0.10% | 18 |
| DIA_15m | 55,967 | 129 | 0.23% | 18 |
| SPY_5m / _adj | 137,228 | 501 | 0.37% | 15 |
| QQQ_5m / _adj | 137,051 | 473 | 0.35% | 15 |

(The other sub-78-bar sessions are **legitimate**: 2020-03-09/12/16/18 are the COVID
circuit-breaker halts, where missing bars are correct. QQQ 2018-05-02/03 have 1 bar
each — a genuine vendor hole, unrelated.)

## 3. The lab already built the fix — and the engine already applies it

`core/data/calendar.py::filter_to_sessions` exists for exactly this and its docstring
names the same dates this audit rediscovered. Coverage:

| path | filters? |
|---|---|
| `core/data/feed.py:84` → `DataFeed.from_source` → **backtest engine** | **YES** |
| `core/execution/paper.py:59` → paper path | **YES** |
| `core/backtest/engine.py:78` → `session_closes` for MOC/decision times | **YES** |
| `scripts/pregate_{rsi5050,keltner,turtle_soup,spxswing,orb,fomc,tsmom}.py` | **NO** |
| `scripts/phase0_rsi5050_brain.py` | **NO** (flag added, see §5) |

So **engine-produced results are clean** — ORB's IS and OOS runs, overnight-long,
intraday-momentum, fomc-drift. **Pregate-produced verdicts are not filtered.**

Corroboration that the exposure is small: ORB's unfiltered pregate and its filtered
engine run agreed on **1,251 of 1,251 trades** (one differing only in stop-vs-EoD
classification, no effect on the mean). If phantom bars mattered materially on QQQ
5-min, those two runs could not have matched.

## 4. Impact on the affected verdicts — none flip

**rsi-5050 pregate** (the 3.5 bps gate): 4 of 767 IS trades fall on half-days, and
**zero have a signal after the official close**. Removing them moves the headline from
**+0.304 → +0.3215 bps** against a 3.5 bps bar. Rejection stands, untouched.

One of the four is genuinely contaminated: `2020-12-24 12:50 ET` long, exit type EOD,
10-bar hold — the market closed at 13:00, so the forced-flat exit booked a fill on a
post-close print. That is the real bug, in one trade.

**rsi-5050-brain Phase 0** (the 2.0 bps gate), re-run with `--filter-sessions`
(231 phantom bars dropped, 765 trades instead of 767):

| | as recorded | filtered | bar |
|---|---|---|---|
| CV mean gross of selected | +0.007 bps | **+0.411 bps** | ≥ 2.0 |
| selected trades | 301 | 294 | ≥ 150 |
| EOD precision | 0.2060 (1.56×) | 0.2211 (1.69×) | needs 1.92× |
| **verdict** | **FAIL** | **FAIL** | |

The FAIL is robust. The time-of-day artifact that killed it is also unchanged
(`f07_minutes_since_open` remains the top feature at corr +0.255).

## 5. Two latent traps that did NOT bite, but would

1. **Arm-cutoff derivation.** `pregate_rsi5050.py` computes
   `arm_cutoff = idx_et[last_i] − 30min` where `last_i` is the last bar *present on
   that date*. On an unfiltered half-day that is a post-close bar, so on 2018-07-03 the
   cutoff becomes 15:30 — two and a half hours after the market shut. No IS trade
   actually armed there, but nothing prevented it.
2. **Forced-flat exit.** The same `last_i` is the EOD exit bar, which is how the
   2020-12-24 trade got a post-close fill.

Both vanish under `filter_to_sessions`, because the last bar on the date then *is* the
official close.

## 6. Applied 2026-08-30 (after the audit above)

**Opt-in flag on the three intraday pregates.** `pregate_rsi5050`, `pregate_orb` and
`pregate_keltner` now accept `--filter-sessions`, **default OFF** so every recorded
verdict still reproduces byte-for-byte. Verified before and after the patch — all three
produce JSON identical to their committed `results.json` (keltner differs only in an
absolute-vs-relative path string when run without `--bars`).

The other four pregates (`fomc`, `spxswing`, `tsmom`, `turtle_soup`) consume **daily**
bars, which are midnight-ET-stamped one-per-session; `filter_to_sessions` drops 0 from
them by construction, so no flag was added rather than adding a misleading no-op.

**Effect of the flag on each verdict — nothing flips:**

| script | trades | mean gross | verdict |
|---|---|---|---|
| pregate_rsi5050 | 767 → 765 | +0.304 → +0.301 bps | FAIL → FAIL |
| pregate_orb | 1251 → **1251** | +4.668 → +4.667 bps | PASS → PASS |
| pregate_keltner | 638 → 638 | −0.839 → −0.842 bps | REJECT → REJECT |

ORB's trade count is **completely unchanged** — it anchors to the session open and is
flat by the close, so phantom bars never enter a trade. That independently explains the
1,251/1,251 pregate-vs-engine agreement noted in §3.

**Hard rule 7 added to `CLAUDE.md`**: load bars through `DataFeed.from_source` (which
applies the filter) rather than `pd.read_parquet`, and derive session closes from
`session_closes`/`session_close_et` rather than from the last bar present on a date.
Rule 2 (no lookahead) now cross-references it. Full test suite passes (85 passed).

## Recommendation (the seven pregate scripts were NOT rewritten)

Do **not** silently rewrite the seven pregate scripts: each is the recorded evidence for
a committed rejection, and editing them would decouple the code from the numbers in
`experiments/`. Instead:

- **New diagnostics load bars through `DataFeed.from_source`** (or call
  `filter_to_sessions` explicitly), so the fix is inherited rather than remembered.
  Worth promoting to a hard rule in `CLAUDE.md` alongside the no-lookahead rule.
- `scripts/phase0_rsi5050_brain.py` now takes **`--filter-sessions`**; without it the
  recorded result reproduces byte-for-byte, with it you get the corrected run above.
- If any pregate verdict is ever revisited, re-run it filtered first.
