# orb — pre-scoring gate, 2026-07-05 — PASS

**Verdict: PASS** — the first pregate pass in the lab (rsi-5050 and spx-swing failed
theirs). Both locked conditions clear on IS 2018-01-01 → 2022-12-31 (OOS 2023–2024 and
WF 2025→ remain unread):

| Gate condition | Bar | Result |
|---|---|---|
| Mean gross per trade | > 2.0 bps (locked cost bar) | **+4.67 bps** (n=1,251, t=2.22) |
| vs unconditional long O2→final-open | must exceed | **+1.19 bps** → edge **+3.47 bps** |

Structure matches the spec's hypothesis, which is the encouraging part:

- **Payoff shape as predicted**: hit rate 23.9%; 74.8% of trades stop out (avg
  −28.0 bps, median 2 bars to stop); the 25.2% that ride to the close average
  **+101.8 bps**. Right-tail carried, exactly the claimed profile.
- **Both sides positive** — long +4.83 bps (n=644, t=1.68), short +4.50 bps (n=607,
  t=1.47). Not a beta artifact; the spec's both-sides OOS gate looks reachable.
- **Every IS year positive**: 2018 +8.4, 2019 +3.1, 2020 +0.6, 2021 +3.7, 2022 +7.7
  bps/trade. Vol-rich years strongest (consistent with the mechanism); 2020's ~0 is
  the honest wobble — whipsaw crash tape, not trend-friendly at the 5-min scale.
- **Effect size ≈ published**: the spec's arithmetic predicted ~3.5–4.5 bps gross if
  the paper's ~0.1–0.2R effect is real; measured 4.67 bps. No excess to be suspicious
  of, no shortfall to explain away.
- **10R diagnostic (never the verdict)**: mean +4.40 bps, target reached on 2.2% of
  trades — confirms the EoD-only baseline choice; the target variant is effectively
  identical.
- **Sizing reality check**: the 100%-notional cap binds on 88% of trades; median
  realized risk 0.247% of equity (half the nominal R=0.5%). Carried into the engine
  phase: net expectancy per trade ~2.7–3.7 bps of notional after the 1.0–1.6 bps
  modeled costs — the OOS Sharpe ≥ 1.0 and beat-QQQ-B&H bars (locked) remain a high
  hurdle in a 2023–2024 bull window. The pregate proves gross edge exists in IS; it
  does not promise the OOS verdict.

Skips: 1,259 IS sessions → 5 doji, 2 short sessions, 1 born-stopped, 0 missing bar-1
→ 1,251 trades (250.2/yr, matching the spec's ~245–248 estimate).

**Next per the spec's Implementation scope**: build the core intrabar-stop extension
(touch / gap-through / worst-case ordering semantics as locked in the SPEC), then the
engine backtest IS → OOS with costs, then quant-review before any verdict is trusted.

## Reproducibility

- Data: `data/QQQ_5m_adj.parquet` (Alpaca SIP 5-min RTH, close-stamped, 2018-01-02 →
  2024-12-30; the spec's data section note on adjustment immateriality applies).
- Script: `scripts/pregate_orb.py` (frozen params in-file), output `results.json`
  (same dir), git commit 7d53c19.
