# intraday-momentum — oos

- sample: oos
- synthetic data: False
- data: data/SPY_5m.parquet (Alpaca SIP, 2018-2024, 137,228 bars, RTH close-stamped)
- trades: 325
- net return: -0.1460
- sharpe: -2.695

## Verdict: REJECTED

The strategy fails every success criterion and loses money in every window, on
both long and short sides. Paired IS run: `2026-07-03-1720-is` (net -13.5%,
Sharpe -2.81) — so this is not an OOS-only artifact.

| criterion            | locked bar | IS (18-21) | OOS (22-24) |
|----------------------|-----------|-----------|-------------|
| net Sharpe           | >= 0.7    | -2.81     | -2.70       |
| net return           | > 0       | -13.5%    | -14.6%      |
| max drawdown         | <= 15%    | 15.1%     | 15.0%       |
| edge on both sides   | yes       | no        | no          |
| trade count          | >= 200    | 311       | 325         |

## Why (not a bug — the signal has no edge)

Even **gross of costs** the return is negative (-0.5% IS, -2.6% OOS), so this is
not a cost problem masking a real edge. A direct diagnostic of the raw effect,
computed outside the trading engine (per session: morning = 09:30->10:00 return,
afternoon = 15:00->15:55 return):

- corr(morning, afternoon) = -0.035 (ALL), -0.037 (IS), -0.032 (OOS)
- momentum edge sign(morning)*afternoon: -0.17 bps/day (ALL), +0.18 (IS, noise),
  -0.65 (OOS); hit rate ~50% (coin flip)
- threshold gating makes it worse (-0.50 bps/day)

The market-intraday-momentum effect is **absent in SPY at this formulation over
2018-2024** — if anything the tape is mildly mean-reverting intraday. Cost drag
(~13%, amplified because the tight intraday stop sizes positions near full
notional) then compounds the loss.

## Decision

Reject at spec-validation, per SPEC's adversarial note. Do NOT tune `k` to
rescue it — the raw correlation is ~0/negative, so there is nothing to tune
toward, and doing so would be overfitting. Strategy status -> retired.

## Observation for a *future, separately-specified* idea

The faint negative correlation hints at intraday mean-reversion / afternoon fade
on SPY in this period. That is a different hypothesis and, if pursued, needs its
own SPEC and its own IS/OOS discipline — not a pivot of this one.
