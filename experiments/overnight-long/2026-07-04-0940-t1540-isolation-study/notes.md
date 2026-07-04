# overnight-long — isolation study: attribution of the v2→v3 deltas (2026-07-04)

Committed after the quant-review of verdict v3 flagged that its two load-bearing
claims were not reproducible from committed artifacts (repo rule 5). This entry
makes claim (b) fully reproducible and documents the honest limits of claim (a).

## (b) The 15:40 decision-bar shift is neutral — REPRODUCIBLE

`run_isolation.py` (this directory; run from the repo root) executes each judged
config at `decision_offset_minutes` 5 (== the old 15:55 decision bar on a full
day) and 20 (the 15:40 variant) on identical code/data/windows. Output captured
in `output.txt`:

| window | offset 5 | offset 20 | delta |
|---|---|---|---|
| evcost IS | 0.7719 | 0.7749 | +0.0030 |
| evcost OOS | 0.5546 | 0.5516 | −0.0030 |
| evcost WF | 1.0718 | 1.0749 | +0.0031 |
| locked WF | 0.2268 | 0.2279 | +0.0011 |

≤0.004 zero-fill Sharpe, mixed sign → the decision-time move is neutral, as the
causal structure predicts (the gate uses the prior day's completed close; the
MOC fill is the same closing print either way).

Therefore the full v2→v3 deltas (OOS 0.5843→0.5516 zero-fill) are attributable
to the calendar fixes: removal of ~2/yr phantom half-day MOC fills and half-days
now trading.

## (a) The v2 anchor reproduction — LIMITED REPRODUCIBILITY, stated honestly

The claim "zero-fill metrics reproduce the review's anchors exactly (OOS
0.715→0.5843/752, WF 1.141→1.0845/375, IS 0.843→0.7747/1008)" was verified on an
**uncommitted intermediate state**: commit `e20db86` (v2 behavior) plus ONLY the
`core/backtest/metrics.py` zero-fill change, before any calendar/engine change.
That state was not committed separately (the fixes landed together in
`6d4c718`), so exact re-verification requires applying the metrics.py diff onto
`e20db86`. Corroboration that requires no reconstruction:

- the `sharpe_trade_days` values at that state (0.7150 / 1.1409 / 0.8433) equal
  the committed v2 `metrics.json` `sharpe` fields exactly (old convention,
  unchanged trades), and
- the zero-fill values matched the independently derived anchor numbers in the
  2026-07-03 quant-review (recorded in HANDOFF/SPEC) to 4 decimals, including
  session counts.

Process lesson recorded: intermediate verification states should be committed
(or the verification script should pin the base commit) so anchors are
re-runnable without archaeology.

## Provenance

- code: commit `6d4c718` backtest path (this study runs unchanged on the
  subsequent paper-path commit; the engine/strategy/data code is identical)
- data: `data/QQQ_5m_adj.parquet`, `data/QQQ_5m_adj_wf.parquet` + daily sources
  per the four configs; windows per config (IS 2018–2021, OOS 2022–2024,
  WF 2025-01→2026-07)
- no seed (deterministic), costs per config (evcost 2.90 bps RT study / locked)
