"""Pre-scoring gross-edge diagnostic for fomc-drift (SPEC.md, Success criteria +
Sign-offs, frozen 2026-07-06 before this ran).

Computes, OUTSIDE the backtest engine and on the IS WINDOW ONLY, the conditional
edge of the pre-registered window (MOC buy close(T-1) -> MOC sell close(T),
scheduled meetings only) against the unconditional non-event baseline:

  FOMC(IS) = mean GROSS close(T-1)->close(T) return over scheduled events, T in IS
  BASE(IS) = mean GROSS close-to-close return over all NON-event trading days in IS
  EDGE(IS) = FOMC(IS) - BASE(IS)                         (the spx-swing convention)

Binding gate (frozen in SPEC.md before this ran) — REJECT at spec-validation if:
  * EDGE(IS) <= 2.0 bps   (locked cost bar: the edge must pay its own round trip), OR
  * EDGE(IS) <  20.0 bps  (reproduction bar: IS is the literature's own sample, where
                           the documented edge is ~45 bps, SE ~9 bps; an IS edge under
                           half strength means our data does not contain the effect and
                           reading the OOS would waste an out-of-sample look).

**OOS (2016-01 -> 2024-12) and WF (2025->) are NOT read here.** The bars are sliced to
<= 2015-12-31 before any computation so nothing post-IS can leak into this number.

Diagnostics (pre-registered DIAGNOSTIC-ONLY in the SPEC; never gates, never verdict):
overnight/announcement-day decomposition, close(T-2)->close(T-1) Boguth missed-onset
check, press-conference tag (pre-2019), per-year means, median + 10%-trimmed mean,
worst event, ex-div-spanning tag count.

    uv run python scripts/pregate_fomc.py \
        --bars data/SPY_daily_adj_spliced.parquet \
        --calendar strategies/fomc-drift/fomc_calendar.csv \
        --out experiments/fomc-drift/2026-07-06-pregate
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
ET = ZoneInfo("America/New_York")

# --- frozen spec parameters (SPEC.md 2026-07-06; never swept) ---
IS_END = "2015-12-31"          # OOS starts 2016-01-01 and is NOT read here
IS_START = "1994-01-01"        # Fed began announcing decisions in 1994
COST_RT_BPS = 2.0              # locked cost bar (two SPY MOC auction fills)
COST_BAR_BPS = 2.0            # gate: EDGE(IS) must exceed the round trip
REPRO_BAR_BPS = 20.0          # gate: EDGE(IS) must reproduce >= half the documented edge


def file_sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def tstat(x: np.ndarray) -> float | None:
    x = np.asarray(x, float)
    return round(float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))), 2) if len(x) > 1 else None


def trimmed_mean(x: np.ndarray, frac: float = 0.10) -> float:
    x = np.sort(np.asarray(x, float))
    k = int(len(x) * frac)
    return float(x[k : len(x) - k].mean()) if len(x) - 2 * k > 0 else float(x.mean())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", type=Path, default=REPO / "data/SPY_daily_adj_spliced.parquet")
    ap.add_argument("--calendar", type=Path,
                    default=REPO / "strategies/fomc-drift/fomc_calendar.csv")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    bars_full = pd.read_parquet(args.bars)
    dates_full = pd.DatetimeIndex(bars_full.index.tz_convert(ET).date)

    # --- HARD IS SLICE: nothing after IS_END is read. OOS/WF stay unread. ---
    is_mask = dates_full <= pd.Timestamp(IS_END)
    bars = bars_full[is_mask]
    dates = dates_full[is_mask]
    pos_of = {d: i for i, d in enumerate(dates)}
    o = bars["open"].to_numpy(float)
    c = bars["close"].to_numpy(float)

    # daily gross close-to-close return in bps, at slot i = C(i)/C(i-1)-1
    dcc = np.full(len(c), np.nan)
    dcc[1:] = 1e4 * (c[1:] / c[:-1] - 1.0)

    cal = pd.read_csv(args.calendar, parse_dates=["start_date", "end_date"])
    sched = cal[cal["type"] == "scheduled"].copy()
    # events with T inside the IS window (and, by the hard slice, T <= IS_END)
    sched = sched[(sched["end_date"] >= pd.Timestamp(IS_START))
                  & (sched["end_date"] <= pd.Timestamp(IS_END))]

    events = []
    event_T_slots = set()
    unmapped = []
    for _, row in sched.iterrows():
        T = row["end_date"]
        i = pos_of.get(T)
        if i is None or i < 2:
            unmapped.append(str(T.date()))
            continue
        event_T_slots.add(i)
        gross = dcc[i]                                  # close(T-1) -> close(T)
        overnight = 1e4 * (o[i] / c[i - 1] - 1.0)       # close(T-1) -> open(T)
        intraday = 1e4 * (c[i] / o[i] - 1.0)            # open(T) -> close(T)
        onset = dcc[i - 1]                              # close(T-2) -> close(T-1), Boguth
        events.append({
            "T": str(T.date()),
            "year": int(T.year),
            "gross_bps": float(gross),
            "net_bps": float(gross - COST_RT_BPS),
            "overnight_bps": float(overnight),
            "intraday_bps": float(intraday),
            "onset_prevday_bps": float(onset),
            "press_conference": bool(row["press_conference"]),
        })

    ev = pd.DataFrame(events)
    if unmapped:
        raise SystemExit(f"IS events not mapped to sessions (should not happen): {unmapped}")

    # --- BASE(IS): all non-event trading days, gross close-to-close ---
    nonevent_slots = [i for i in range(1, len(c)) if i not in event_T_slots]
    base_bps = float(np.nanmean(dcc[nonevent_slots]))

    fomc_bps = float(ev["gross_bps"].mean())
    edge_bps = fomc_bps - base_bps
    se_event = float(ev["gross_bps"].std(ddof=1) / np.sqrt(len(ev)))

    gate_pass = (edge_bps > COST_BAR_BPS) and (edge_bps >= REPRO_BAR_BPS)
    if gate_pass:
        verdict = ("PASS pre-scoring gate — the documented edge reproduces in-sample; "
                   "proceed to implementation, engine IS cross-check, then ONE OOS look")
    else:
        why = []
        if edge_bps <= COST_BAR_BPS:
            why.append(f"EDGE(IS)={edge_bps:.2f} bps <= cost bar {COST_BAR_BPS}")
        if edge_bps < REPRO_BAR_BPS:
            why.append(f"EDGE(IS)={edge_bps:.2f} bps < reproduction bar {REPRO_BAR_BPS}")
        verdict = ("REJECT at spec-validation (binding rule frozen in SPEC.md before this "
                   "ran): " + "; ".join(why) + ". No tuning; OOS stays unread; post-mortem "
                   "in the SPEC. Would be the 5th published-then-gone confirmation.")

    per_year = {
        int(y): {"n": int(len(g)), "mean_gross_bps": round(float(g["gross_bps"].mean()), 2)}
        for y, g in ev.groupby("year")
    }
    pc = ev[ev["press_conference"]]
    npc = ev[~ev["press_conference"]]
    pc_mean = round(float(pc["gross_bps"].mean()), 2) if len(pc) else None
    npc_mean = round(float(npc["gross_bps"].mean()), 2) if len(npc) else None
    onset_mean = round(float(ev["onset_prevday_bps"].mean()), 2)

    out = {
        "strategy": "fomc-drift",
        "gate_scope": "IS ONLY (1994-01-01 -> 2015-12-31). OOS and WF NOT read.",
        "bars_file": str(args.bars),
        "bars_sha256_16": file_sha(args.bars),
        "bars_range_read": [str(dates[0].date()), str(dates[-1].date())],
        "calendar_file": str(args.calendar),
        "calendar_sha256_16": file_sha(args.calendar),
        "params": {
            "is_window": [IS_START, IS_END],
            "cost_round_trip_bps": COST_RT_BPS,
            "cost_bar_bps": COST_BAR_BPS,
            "reproduction_bar_bps": REPRO_BAR_BPS,
        },
        "gate_rule": "REJECT if EDGE(IS) <= 2.0 bps OR EDGE(IS) < 20.0 bps",
        "n_events": int(len(ev)),
        "n_nonevent_days": len(nonevent_slots),
        "FOMC_IS_mean_gross_bps": round(fomc_bps, 3),
        "BASE_IS_mean_gross_bps": round(base_bps, 4),
        "EDGE_IS_bps": round(edge_bps, 3),
        "se_per_event_bps": round(se_event, 2),
        "t_event_vs_zero": tstat(ev["gross_bps"].to_numpy()),
        "t_edge_approx": round(edge_bps / se_event, 2) if se_event else None,
        "mean_net_bps_per_event": round(float(ev["net_bps"].mean()), 2),
        "hit_rate_gross": round(float((ev["gross_bps"] > 0).mean()), 3),
        "verdict": verdict,
        "diagnostics_NOT_GATES": {
            "decomposition_mean_bps": {
                "overnight_close_to_open": round(float(ev["overnight_bps"].mean()), 2),
                "intraday_open_to_close": round(float(ev["intraday_bps"].mean()), 2),
            },
            "boguth_missed_onset_close_Tm2_to_Tm1_mean_bps": onset_mean,
            "press_conference_split": {
                "pc": {"n": int(len(pc)), "mean_gross_bps": pc_mean},
                "non_pc": {"n": int(len(npc)), "mean_gross_bps": npc_mean},
            },
            "median_gross_bps": round(float(ev["gross_bps"].median()), 2),
            "trimmed10_mean_gross_bps": round(trimmed_mean(ev["gross_bps"].to_numpy()), 2),
            "worst_event": ev.loc[ev["gross_bps"].idxmin(), ["T", "gross_bps"]].to_dict(),
            "best_event": ev.loc[ev["gross_bps"].idxmax(), ["T", "gross_bps"]].to_dict(),
            "per_year_gross": per_year,
        },
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True
        ).stdout.strip(),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "pregate_results.json").write_text(json.dumps(out, indent=2) + "\n")
    ev.to_csv(args.out / "pregate_events_is.csv", index=False)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
