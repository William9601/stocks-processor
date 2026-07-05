# orb — OOS engine run (2023-01-01 → 2024-12-31) — THE one pre-registered look

- sample: oos, locked costs (0.1 / 0.4 / 1.0 bps). The 1.5×-cost sensitivity
  companion (pre-registered, SPEC sign-off #2) is `2026-07-05-1639-oos-cost150`.
- window is almost entirely post-publication of the April 2023 paper — the
  binding test, by design.
- WF (2025→) remains **unread**.

## Headline

- trades: 499 · net return: **+1.57%** over 2 years · net zero-filled Sharpe:
  **0.153** · max DD: −9.04%
- mean per trade: **+1.90 bps gross / +0.43 bps net** — the OOS gross edge is
  *below the 2.0 bps locked cost bar on its own*: the pregate gate, applied to
  this window, would have failed.

## Verdict vs the frozen bars (recorded fully in SPEC.md)

| locked bar | value | verdict |
|---|---|---|
| OOS net zero-filled Sharpe ≥ 1.0 | 0.153 | **FAIL** |
| beat QQQ B&H net Sharpe, identical window | 0.153 vs **2.002** (QQQ +97.5%) | **FAIL** |
| net-positive expectancy after costs | +0.43 bps/trade | pass (marginal) |
| net-positive at 1.5× costs | −2.03% total, Sharpe −0.069 | **FAIL** |
| both sides net-positive separately | long **−$1,488** (−5.6/trade), short +$3,062 | **FAIL** |
| max OOS drawdown ≤ 10% | −9.04% | pass |
| worst trade ≤ 2.0·R realized | −1.45 R (2024-12-10) | pass |
| ≥ 400 filled OOS trades | 499 | pass |
| decay guard: OOS Sharpe ≥ 50% of IS | 0.153 vs 0.789 (−81%) | **FAIL** |

**REJECT** — five hard fails. No tuning, no duration/instrument shopping, per
the locked adversarial defenses.

## Locked reporting detail

- per-year net bps/trade: 2023 **−2.17** (n=249), 2024 **+3.02** (n=250)
- exit split: 386 stop / 113 EoD · hit rate 0.216
- realized-R quartiles: −1.07 / −1.05 / −1.02 (stops dominate); median
  realized risk 0.197% of equity (notional cap binding, as designed)
- max consecutive losses: 17 (SPEC declared 10–15 "normal"; 17 observed)
- daily P&L correlation vs the overnight-long paper book, identical dates
  (n=501): **0.008** — genuinely uncorrelated, as hypothesized. Basis:
  `experiments/overnight-long/2026-07-05-1640-corr-basis-for-orb`.

## Reading

The IS edge (+4.67 bps gross, every year positive) decayed to +1.90 bps gross
in the post-publication window and inverted on the long side — the
published-then-gone pattern that killed spx-swing, now confirmed on a second
famous published effect. The 2024 rebound (+3.02 net) is one diagnostic
column, not a gate; the SPEC's own honest expectation ("rejection at the
engine stage is a live outcome and fine") is the outcome.
