# spx-swing — pre-scoring gate, 2026-07-05 — REJECT at spec validation

**Verdict: REJECT.** The binding gate (frozen in SPEC.md Decisions record before the
diagnostic ran: OOS mean net per trade > 0 AND OOS net edge over the unconditional
same-horizon open→open baseline > 0) fails on the second condition:

|                              | IS 2005–2017 | OOS 2018–2024 |
|------------------------------|:---:|:---:|
| trades                       | 103 | 60 |
| mean net / trade (8 bps RT)  | **+44.5 bps** (t=3.03) | **+5.5 bps** (t=0.21) |
| edge vs unconditional drift  | **+30.2 bps** (t=2.03) | **−14.6 bps** (t=−0.56) |
| hit rate (net)               | 0.70 | 0.65 |
| stops (n, avg)               | 8, −322 bps | 9, −388 bps |
| strength exits (n, avg)      | 95, +75 bps | 51, +75 bps |

Reading: the effect was genuinely there in the IS era and is **gone as an edge in the
OOS era** — not because winners degraded (strength exits average +75 bps in both
windows, hit rate held) but because (a) the unconditional drift itself rose (3.9 →
5.8 bps/day open→open), raising the bar, and (b) the left tail got heavier (avg stop
−322 → −388 bps, worst single trade −578 bps). Post-2018, buying the 2-day pullback in
an uptrend earns *less* than simply holding SPY over the same days, before even
considering the risk profile. The distribution shape (median +65 bps vs mean +5 bps
OOS) is the classic mean-reversion signature — steady pennies, occasional steamroller —
with the pennies no longer covering the steamroller.

The pre-registered **limit-at-C(d) diagnostic variant** (never the verdict number)
tells the same story: OOS mean net +12.6 bps (t=0.36), edge vs unconditional −9.7 bps.
Entry mechanics are not the problem; the conditional premium is absent.

This matches the external research base rate recorded in `docs/strategy-candidates.md`
(RSI(2)-style mean reversion decayed post-2010, notably weak 2021–2025). Rejected
without tuning, without window shopping, without instrument shopping, per the
adversarial note in the spec. **No engine code was written.** The OOS window has now
been read once for this formulation; the WF window (2025→) was not read.

## Reproducibility

- Data: `data/SPY_daily_adj_spliced.parquet` — raw official prints (Yahoo pre-2016,
  Alpaca SIP 2016→2026-07-02) + uniform CRSP dividend back-adjustment, built by
  `scripts/build_spy_eod_splice.py`; evidence in `splice_report.json` (same dir).
  Note the audit finding recorded there: **Alpaca's vendor `adjustment=all` series is
  missing the 2016-03-18 and 2018-06-15 SPY dividends** (and double-applies the
  2022-09-19 QQQ dividend) — the vendor adjusted series was abandoned for this reason.
  User-approved deviation on the 5 bps level check recorded in SPEC.md.
- Diagnostic: `scripts/pregate_spxswing.py` (frozen params in-file), output
  `results.json` (same dir), git commit ccab57d.
