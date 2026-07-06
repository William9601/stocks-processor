# fomc-drift — OOS 2016-2024 — the ONE pre-registered look — 2026-07-06

**Verdict: REJECT.** The pre-FOMC drift does not clear its frozen bars out of
sample. The IS edge (EDGE=30.35 bps, the pregate) does NOT survive the
post-publication window: the 2016–2019 dead zone (pre-registered inside the OOS)
exactly cancels the 2020–2024 revival, leaving a blend edge of ~zero. Sixth
candidate death in the lab; failure is at the gross/conditional-edge level, not
execution. This look is spent — WF 2025→ stays unread.

## Scorecard vs the frozen SPEC bars (net of 2.0 bps; companion at 3.0 bps)

| # | Frozen bar | Result | |
|---|---|---|---|
| 1 | OOS net zero-filled Sharpe ≥ 0.7 | **0.109** (0.087 @ 3.0×) | **FAIL** |
| 2 | EDGE(OOS) ≥ 2.0 bps gross | **1.87 bps** (net conditional −0.13) | **FAIL** |
| 3 | beat SPY B&H | WAIVED at sign-off | — |
| 4 | net-positive/event, and at 1.5× costs | −0.13 / −1.13 bps | **FAIL** |
| 5 | Max OOS drawdown ≤ 6·R (3.0%) | 0.69% (realized and MTM) | PASS |
| 6 | Worst single event ≤ 2.5·R | 0.57·R (2024-12-18) | PASS |
| 7 | ≥ 64 filled OOS events | 71 | PASS |
| 8 | IS→OOS decay ≤ 50% | IS Sharpe 0.728 → OOS 0.109 = **−85%** | **FAIL** |

Four bars fail (1, 2, 4, 8). Any one of #1/#2/#4 is sufficient for REJECT; the
conditional net edge is negative (−0.13 bps) — the drift no longer pays for its
own round trip out of sample.

## The numbers (OOS 2016-01 → 2024-12, n = 71 scheduled events, gross)

- `FOMC(OOS)` mean close(T-1)→close(T) = **7.77 bps**
- `BASE(OOS)` mean non-event day (close-to-close) = **5.90 bps**
- **`EDGE(OOS)` = 1.87 bps** (SE/event 13.57, t ≈ 0.57 — indistinguishable from
  zero, exactly the SPEC's pre-stated ~14 bps OOS SE / thin-power warning)
- hit rate 49.3%, median event −2.25 bps
- worst event −298 bps (2024-12-18, the hawkish Dec-2024 cut — the signature
  acute loss the SPEC named; 0.57·R realized, inside the gap budget)
- best event +305 bps (2022-05-04, the 50 bps hike meeting)

Engine metrics (config.yaml, 2.0 bps): net_return +0.29% over 9 years, zero-filled
Sharpe 0.109, max DD 0.69% (realized) / 0.69% (MTM), kill switch never tripped
(`risk_halted=false`), 71 trades. Companion (config.cost150.yaml, 3.0 bps):
net_return +0.23%, Sharpe 0.087.

## Per-era diagnostic (DIAGNOSTIC-ONLY — the no-rescue clause binds)

| Era | n | FOMC | BASE | EDGE | net @2.0 |
|---|---|---|---|---|---|
| Dead zone 2016–2019 | 32 | −9.75 | 6.15 | **−15.90** | −17.90 |
| Revival 2020–2024 | 39 | 22.15 | 5.70 | **+16.44** | +14.44 |
| **Full OOS blend** | 71 | 7.77 | 5.90 | **+1.87** | −0.13 |

This is the pre-registered hypothesis confirmed *as a description* and rejected
*as a strategy*. The uncertainty-state-dependence is real — the ZLB dead-zone
edge is negative (worse than Kurov's +9.2 bps insignificant), the 2020–2024
revival edge is strongly positive (+16.4 bps, matching QuantSeeker). But the
strategy trades **unconditionally** by design, so it is judged on the blend, and
the blend is ~zero. Per the LOCKED no-rescue clause, the strong revival is **not**
a promotion path and the negative dead zone is not a separate failure — the
unconditional book earns the average, and the average does not clear the bars.
Adding a VIX/uncertainty gate to harvest only the revival would be a new tuned
parameter and a sweep the SPEC forbids; it is not on the table.

Per-year gross means (bps): 2016 −10.9, 2017 +11.0, 2018 −41.4, 2019 +2.3,
2020 +68.0, 2021 +6.1, 2022 +51.8, 2023 +4.2, 2024 −13.6.

## Why this is trustworthy (not an execution artifact)

The engine IS cross-check reconciled to the standalone pregate **event-by-event,
max |gross diff| 0.00000 bps** (scripts/crosscheck_fomc_is.py, 176/176 events) —
the fills are provably close(T-1) → close(T), zero lookahead (the signal is a
calendar known in advance; decision days verified session-for-session vs the
splice, 259/259). The rejection is a genuine absence of edge in the blend, mirror
of ORB and spx-swing: published, then gone (or here, present only in the
uncertainty regime the unconditional book can't isolate).

## Reproducibility

- Bars `data/SPY_daily_moc.parquet` sha256 e636779b671f73e8… (recorded in
  metrics.json `data_sha256`; re-stamped from the audited splice by
  `scripts/build_spy_daily_moc.py`). Calendar committed (pinned by git commit).
- Configs `strategies/fomc-drift/config.yaml` (2.0 bps) + `config.cost150.yaml`
  (3.0 bps), `--sample oos`. Companion run:
  `experiments/fomc-drift/2026-07-06-2011-oos-cost150/`.
- WF 2025→ NOT read. No re-runs, no tuning, no per-era rescue.
