"""Pre-scoring gross-edge diagnostic for orb (SPEC.md, PREGATE section; all
parameters and the gate rule frozen at user sign-off 2026-07-05, before this
script was written).

Measures, OUTSIDE the backtest engine, the raw gross follow-through of the
5-min opening range breakout on QQQ, IS window ONLY (2018-01-01 -> 2022-12-31);
the OOS (2023-2024) and WF (2025->) windows are not read.

Per session: bar 1 = the close-stamped 09:35 ET bar (09:30-09:35). Skips: doji
(C1 == O1), zero range (H1 == L1), missing bar 1, born-stopped (long: O2 <= L1;
short: O2 >= H1). Direction = sign(C1 - O1); entry = O2 (bar 2 open); stop =
L1 (long) / H1 (short), live from bar 2 inclusive; touch fills at the stop
price, gap-through (bar opens beyond the stop) fills at the bar open; otherwise
forced flat at the OPEN of the session's final bar. Gross of costs.

Gate (LOCKED): REJECT at spec validation if the IS mean gross return per trade
<= 2.0 bps (the locked round-trip cost bar), OR if it does not exceed the
unconditional long QQQ O2 -> final-bar-open mean over the same sessions.

Diagnostic-only columns (never the gate): 10R-target variant (worst-case
intrabar ordering: stop before target), per-year means, long/short split, hit
rate, stop-distance / realized-R / time-to-stop distributions.

    uv run python scripts/pregate_orb.py \
        --bars data/QQQ_5m_adj.parquet \
        --out experiments/orb/2026-07-05-pregate
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
ET = ZoneInfo("America/New_York")

# --- frozen spec parameters (SPEC.md Decisions record 2026-07-05) ---
COST_BAR_BPS = 2.0  # locked round-trip cost bar the gross edge must clear
TARGET_R = 10.0  # diagnostic-only variant
RISK_PCT = 0.005  # R = 0.5% of equity, notional capped at 100% (realized-R diag)
IS_START, IS_END = "2018-01-01", "2022-12-31"  # OOS/WF not read


def _maybe_filter(bars, enabled: bool, label: str = "bars"):
    """Drop phantom post-close half-day bars when --filter-sessions is passed."""
    if not enabled:
        return bars
    from core.data.calendar import filter_to_sessions

    kept = filter_to_sessions(bars)
    print(f"  [filter_to_sessions] {label}: dropped {len(bars) - len(kept)} phantom bar(s)")
    return kept


def simulate(bars: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    et_idx = bars.index.tz_convert(ET)
    dates = np.array([t.date() for t in et_idx])
    times = np.array([t.time() for t in et_idx])
    o = bars["open"].to_numpy(float)
    h = bars["high"].to_numpy(float)
    l = bars["low"].to_numpy(float)
    c = bars["close"].to_numpy(float)

    d0, d1 = pd.Timestamp(IS_START).date(), pd.Timestamp(IS_END).date()
    counts = {"sessions_is": 0, "skip_no_bar1": 0, "skip_short_session": 0,
              "skip_doji": 0, "skip_zero_range": 0, "skip_born_stopped": 0,
              "traded": 0}
    trades = []

    session_starts = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    bar1_time = pd.Timestamp("09:35").time()

    for k, s in enumerate(session_starts):
        e = session_starts[k + 1] if k + 1 < len(session_starts) else len(dates)
        if not (d0 <= dates[s] <= d1):
            continue  # IS only — OOS/WF stay unread
        counts["sessions_is"] += 1
        if times[s] != bar1_time:
            counts["skip_no_bar1"] += 1
            continue
        if e - s < 3:  # need bar 1, bar 2, and a distinct final bar
            counts["skip_short_session"] += 1
            continue
        o1, h1, l1, c1 = o[s], h[s], l[s], c[s]
        if c1 == o1:
            counts["skip_doji"] += 1
            continue
        if h1 == l1:
            counts["skip_zero_range"] += 1
            continue
        long_side = c1 > o1
        entry = o[s + 1]
        stop = l1 if long_side else h1
        if (long_side and entry <= stop) or (not long_side and entry >= stop):
            counts["skip_born_stopped"] += 1
            continue
        counts["traded"] += 1

        sign = 1.0 if long_side else -1.0
        D = abs(entry - stop)
        last = e - 1  # final bar of the session; EoD exit at its OPEN
        target = entry + sign * TARGET_R * D  # diagnostic only

        # --- baseline: stop scan bars 2..last-1, else flat at o[last] ---
        exit_px, exit_reason, exit_i = o[last], "eod", last
        for j in range(s + 1, last):
            hit = (l[j] <= stop) if long_side else (h[j] >= stop)
            if hit:
                gap_through = (o[j] < stop) if long_side else (o[j] > stop)
                exit_px = o[j] if gap_through else stop
                exit_reason, exit_i = "stop", j
                break
        gross_bps = sign * 1e4 * (exit_px - entry) / entry

        # --- 10R diagnostic: worst-case ordering, stop checked first per bar ---
        t_px, t_reason = o[last], "eod"
        for j in range(s + 1, last):
            hit_stop = (l[j] <= stop) if long_side else (h[j] >= stop)
            if hit_stop:
                gap = (o[j] < stop) if long_side else (o[j] > stop)
                t_px, t_reason = (o[j] if gap else stop), "stop"
                break
            hit_tgt = (h[j] >= target) if long_side else (l[j] <= target)
            if hit_tgt:
                fav_gap = (o[j] >= target) if long_side else (o[j] <= target)
                t_px, t_reason = (o[j] if fav_gap else target), "target"
                break
        gross_10r_bps = sign * 1e4 * (t_px - entry) / entry

        d_frac = D / entry
        notional_frac = min(RISK_PCT / d_frac, 1.0)
        uncond_bps = 1e4 * (o[last] - entry) / entry  # long O2 -> final-bar-open

        trades.append({
            "date": str(dates[s]), "year": dates[s].year,
            "side": "long" if long_side else "short",
            "exit_reason": exit_reason,
            "bars_held": int(exit_i - (s + 1)),
            "gross_bps": float(gross_bps),
            "gross_10r_bps": float(gross_10r_bps), "exit_10r": t_reason,
            "stop_dist_bps": float(1e4 * d_frac),
            "notional_frac": float(notional_frac),
            "realized_risk_pct": float(100 * notional_frac * d_frac),
            "uncond_long_bps": float(uncond_bps),
        })
    return pd.DataFrame(trades), counts


def stats(sub: pd.DataFrame, col: str = "gross_bps") -> dict:
    if sub.empty:
        return {"n": 0}
    r = sub[col]
    return {
        "n": int(len(sub)),
        "mean_bps": round(float(r.mean()), 3),
        "median_bps": round(float(r.median()), 2),
        "std_bps": round(float(r.std()), 1),
        "t_stat": round(float(r.mean() / (r.std() / np.sqrt(len(r)))), 2),
        "hit_rate": round(float((r > 0).mean()), 3),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", type=Path, default=REPO / "data/QQQ_5m_adj.parquet")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--filter-sessions", action="store_true", help="drop phantom bars stamped after a half-day's official 13:00 close (core.data.calendar.filter_to_sessions). Default OFF so the recorded result reproduces byte-for-byte; see experiments/data-audits/2026-08-30-phantom-half-day-bars/.")
    args = ap.parse_args()

    bars = _maybe_filter(pd.read_parquet(args.bars), args.filter_sessions)
    df, counts = simulate(bars)

    mean_gross = float(df["gross_bps"].mean())
    uncond = float(df["uncond_long_bps"].mean())
    gate_pass = mean_gross > COST_BAR_BPS and mean_gross > uncond
    years = df.groupby("year")["gross_bps"].agg(["count", "mean"]).round(3)

    result = {
        "strategy": "orb",
        "bars_file": str(args.bars),
        "bars_range": [str(bars.index[0]), str(bars.index[-1])],
        "is_window": [IS_START, IS_END],
        "windows_not_read": "OOS 2023-2024, WF 2025->",
        "params": {"cost_bar_bps": COST_BAR_BPS, "target_r_diagnostic": TARGET_R,
                   "risk_pct": RISK_PCT},
        "gate": "IS mean gross > 2.0 bps AND > unconditional long O2->final-open mean",
        "counts": counts,
        "trades_per_year": round(counts["traded"] / 5.0, 1),
        "all": stats(df),
        "unconditional_long_same_sessions_bps": round(uncond, 3),
        "edge_vs_unconditional_bps": round(mean_gross - uncond, 3),
        "long": stats(df[df["side"] == "long"]),
        "short": stats(df[df["side"] == "short"]),
        "by_exit": {k: stats(g) for k, g in df.groupby("exit_reason")},
        "by_year": {str(y): {"n": int(r["count"]), "mean_bps": float(r["mean"])}
                    for y, r in years.iterrows()},
        "stop_rate": round(float((df["exit_reason"] == "stop").mean()), 3),
        "median_bars_to_stop": float(df.loc[df.exit_reason == "stop", "bars_held"].median()),
        "stop_dist_bps_quartiles": [round(float(q), 1) for q in
                                    df["stop_dist_bps"].quantile([0.25, 0.5, 0.75])],
        "realized_risk_pct_median": round(float(df["realized_risk_pct"].median()), 3),
        "notional_cap_binds_frac": round(float((df["notional_frac"] >= 1.0).mean()), 3),
        "diagnostic_10r_NOT_SCORED": {
            "all": stats(df, "gross_10r_bps"),
            "target_hit_frac": round(float((df["exit_10r"] == "target").mean()), 4),
        },
        "verdict": (
            "PASS pre-scoring gate — build the intrabar-stop core extension, then engine backtest"
            if gate_pass else
            "REJECT at spec validation — IS gross edge fails the locked bar "
            "(mean gross <= 2.0 bps cost bar and/or <= unconditional long drift); "
            "no tuning, no duration/instrument shopping"
        ),
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True
        ).stdout.strip(),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
