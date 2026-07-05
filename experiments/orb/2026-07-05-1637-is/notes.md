# orb — IS engine run (2018-01-01 → 2022-12-31)

- sample: is (development window; no locked bar applies here except the
  pregate cross-check)
- data: `data/QQQ_5m_adj.parquet`, Alpaca SIP 5-min RTH, close-stamped
- costs: locked model (0.1 half-spread / 0.4 slippage / 1.0 stop slippage bps)
- trades: 1251 · net return: +47.6% · net zero-filled Sharpe: 0.789 · max DD: −10.78%

## Pregate cross-check — PASSED (the reason this run exists)

Engine vs `experiments/orb/2026-07-05-pregate/results.json`:

| metric | engine | pregate |
|---|---|---|
| trades | 1251 | 1251 |
| mean gross bps/trade | 4.667 | 4.668 |
| per-year mean bps | 8.367 / 3.081 / 0.575 / 3.706 / 7.651 | 8.356 / 3.056 / 0.616 / 3.706 / 7.651 |
| long / short n | 644 / 607 | 644 / 607 |
| long / short mean bps | 4.855 / 4.467 | 4.830 / 4.495 |
| exit split stop / eod | 935 / 316 | 936 / 315 |
| hit rate | 0.240 | 0.239 |

Zero cross-day exits (never-overnight holds). One trade in 1251 differs in
exit classification (stop vs EoD) with no effect on the aggregate mean —
sub-rounding disagreement between two independent implementations of the
locked intrabar semantics.

## Kill-switch note (honest, carried to the verdict)

At realized-R sizing the mark-to-market equity path crossed −10% from peak on
**2021-03-16**. Run with `halt_on_drawdown: false` so the full-window drawdown
the locked ≤10% OOS criterion judges is *measured*, not censored (a permanent
mid-simulation halt made the first attempt untrustworthy: it froze the book in
2021-03 and silently dropped 453 trades). In live/paper operation the switch
trips and halts for manual review — IS behavior says that event is plausible
in a bad stretch, exactly as the SPEC's kill-switch paragraph anticipated.

## Decay-guard baseline

IS net zero-filled Sharpe **0.789** → the OOS decay guard (not more than 50%
below IS) sits at 0.394 — weaker than the absolute OOS bar of 1.0, so the
binding OOS constraint is the 1.0 Sharpe bar itself. Note the honest tension
recorded in the SPEC: IS at 0.789 is *already below* the 1.0 the OOS window
must clear.

## Provenance

- git commit in config.yaml; engine + strategy at `20796a5` (+ risk
  halt_on_drawdown measurement flag, committed with the OOS milestone)
- windows read so far: IS only. OOS opened next (one look); WF stays unread.
