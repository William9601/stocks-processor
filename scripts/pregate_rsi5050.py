"""Pre-gating gross-edge diagnostic for rsi-5050 (SPEC.md, Success criteria).

Measures, OUTSIDE the backtest engine, the distribution of the raw gross
continuation — from `signal-bar extreme + buffer` (the stop-entry trigger) to
the RSI-recross exit — for all band-passing RSI(21) midline crosses on
IN-SAMPLE data only (2018-2021), both sides, gross of costs.

Gate (locked in SPEC.md before this script was written): if the mean gross
continuation <= the modeled round-trip cost (~3.5 bps), there is no edge to
trade and the strategy is rejected at spec validation — no tuning.

    uv run python scripts/pregate_rsi5050.py \
        --bars data/DIA_5m.parquet --label 5min \
        --out experiments/rsi-5050/2026-07-05-pregate

Runs the 15-min co-equal diagnostic the same way with data/DIA_15m.parquet.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import time
from pathlib import Path

import numpy as np
import pandas as pd

from core.strategy import ET

REPO = Path(__file__).resolve().parents[1]

# --- spec parameters (Decisions record, SPEC.md 2026-07-05) ---
RSI_N = 21
ATR_N = 5
MIDLINE = 50.0
BAND_LO_BPS = 4.5
BAND_HI_BPS = 6.8
BUFFER_ATR_FRAC = 0.04
BUFFER_FLOOR = 0.02  # dollars, 2 ticks
PENDING_BARS = 10
WARMUP_BARS = 250
FIRST_SIGNAL_ET = time(9, 45)  # signal bar must CLOSE strictly after this
ARM_CUTOFF_BEFORE_CLOSE = pd.Timedelta(minutes=30)  # 15:30 on a 16:00 day
ROUND_TRIP_COST_BPS = 3.5  # modeled cost the gross edge must clear


def _maybe_filter(bars, enabled: bool, label: str = "bars"):
    """Drop phantom post-close half-day bars when --filter-sessions is passed."""
    if not enabled:
        return bars
    from core.data.calendar import filter_to_sessions

    kept = filter_to_sessions(bars)
    print(f"  [filter_to_sessions] {label}: dropped {len(bars) - len(kept)} phantom bar(s)")
    return kept


def wilder(values: np.ndarray, n: int) -> np.ndarray:
    """Wilder smoothing: seed = simple mean of the first n values, then
    out[i] = (out[i-1]*(n-1) + values[i]) / n. NaN before the seed."""
    out = np.full(len(values), np.nan)
    if len(values) < n:
        return out
    out[n - 1] = values[:n].mean()
    for i in range(n, len(values)):
        out[i] = (out[i - 1] * (n - 1) + values[i]) / n
    return out


def rsi_wilder(close: np.ndarray, n: int) -> np.ndarray:
    delta = np.diff(close, prepend=close[0])
    delta[0] = 0.0
    up = np.maximum(delta, 0.0)
    dn = np.maximum(-delta, 0.0)
    # deltas start being meaningful at index 1; seed over deltas 1..n
    avg_u = np.full(len(close), np.nan)
    avg_d = np.full(len(close), np.nan)
    if len(close) <= n:
        return np.full(len(close), np.nan)
    avg_u[n] = up[1 : n + 1].mean()
    avg_d[n] = dn[1 : n + 1].mean()
    for i in range(n + 1, len(close)):
        avg_u[i] = (avg_u[i - 1] * (n - 1) + up[i]) / n
        avg_d[i] = (avg_d[i - 1] * (n - 1) + dn[i]) / n
    with np.errstate(divide="ignore", invalid="ignore"):
        rsi = 100.0 - 100.0 / (1.0 + avg_u / avg_d)
    rsi[np.isnan(avg_u)] = np.nan
    rsi[(avg_d == 0) & ~np.isnan(avg_u)] = 100.0
    return rsi


def true_range(o, h, l, c, first_of_session: np.ndarray) -> np.ndarray:
    prev_c = np.roll(c, 1)
    prev_c[0] = c[0]
    tr = np.maximum.reduce([h - l, np.abs(h - prev_c), np.abs(l - prev_c)])
    # Session-boundary convention: overnight gap is not tradeable intraday
    # range — first bar of each session uses H-L only.
    tr[first_of_session] = (h - l)[first_of_session]
    return tr


def run(bars_path: Path, label: str, is_start: str, is_end: str,
        filter_sessions: bool = False) -> dict:
    bars = _maybe_filter(pd.read_parquet(bars_path), filter_sessions)
    idx_et = bars.index.tz_convert(ET)
    o = bars["open"].to_numpy(float)
    h = bars["high"].to_numpy(float)
    l = bars["low"].to_numpy(float)
    c = bars["close"].to_numpy(float)
    dates = np.array([t.date() for t in idx_et])
    times = np.array([t.time() for t in idx_et])  # close-stamped
    n = len(bars)

    first_of_session = np.zeros(n, dtype=bool)
    first_of_session[0] = True
    first_of_session[1:] = dates[1:] != dates[:-1]

    # per-session last index and close time (handles early closes)
    session_last = {}
    for i in range(n):
        session_last[dates[i]] = i  # ends at the session's final bar

    rsi = rsi_wilder(c, RSI_N)
    atr = wilder(true_range(o, h, l, c, first_of_session), ATR_N)
    atr_bps = 1e4 * atr / c

    cross_up = np.zeros(n, dtype=bool)
    cross_dn = np.zeros(n, dtype=bool)
    cross_up[1:] = (rsi[:-1] <= MIDLINE) & (rsi[1:] > MIDLINE)
    cross_dn[1:] = (rsi[:-1] >= MIDLINE) & (rsi[1:] < MIDLINE)

    d0, d1 = pd.Timestamp(is_start).date(), pd.Timestamp(is_end).date()

    trades = []
    counts = {"crosses_is": 0, "band_pass": 0, "time_gated": 0, "armed": 0,
              "cancelled_recross": 0, "cancelled_stale": 0, "cancelled_cutoff": 0,
              "filled": 0}

    for s in range(WARMUP_BARS, n):
        if not (cross_up[s] or cross_dn[s]):
            continue
        if not (d0 <= dates[s] <= d1):
            continue  # in-sample only — OOS stays untouched
        counts["crosses_is"] += 1
        if not (BAND_LO_BPS <= atr_bps[s] <= BAND_HI_BPS):
            continue
        counts["band_pass"] += 1

        last_i = session_last[dates[s]]
        session_close_ts = idx_et[last_i]
        arm_cutoff = (session_close_ts - ARM_CUTOFF_BEFORE_CLOSE).time()
        if times[s] <= FIRST_SIGNAL_ET or times[s] > arm_cutoff:
            continue
        counts["time_gated"] += 1

        long_side = bool(cross_up[s])
        buffer = max(BUFFER_ATR_FRAC * atr[s], BUFFER_FLOOR)
        trigger = h[s] + buffer if long_side else l[s] - buffer
        stop = l[s] - buffer if long_side else h[s] + buffer
        counts["armed"] += 1

        # --- fill scan: bars s+1 .. s+PENDING_BARS, same session, pending
        # order dies at the arm cutoff; adverse recross at a bar CLOSE cancels
        # the order, but an intrabar fill on that same bar happens first.
        fill_i = None
        cancelled = None
        for j in range(s + 1, min(s + PENDING_BARS, last_i) + 1):
            if times[j] > arm_cutoff:
                cancelled = "cutoff"
                break
            hit = (h[j] >= trigger) if long_side else (l[j] <= trigger)
            if hit:
                fill_i = j
                break
            recross = cross_dn[j] if long_side else cross_up[j]
            if recross:
                cancelled = "recross"
                break
        if fill_i is None:
            if cancelled is None:
                cancelled = "stale"
            counts[f"cancelled_{cancelled}"] += 1
            continue
        counts["filled"] += 1

        fill_px = max(o[fill_i], trigger) if long_side else min(o[fill_i], trigger)

        # --- exit: first adverse recross at a bar close -> exit next-bar
        # open; forced flat at the open of the session's final bar.
        exit_i, exit_type = last_i, "eod"
        for e in range(fill_i, last_i):
            recross = cross_dn[e] if long_side else cross_up[e]
            if recross:
                exit_i, exit_type = e + 1, "recross"
                break
        exit_px = o[exit_i]

        sign = 1.0 if long_side else -1.0
        ret_trigger = sign * 1e4 * (exit_px - trigger) / trigger
        ret_fill = sign * 1e4 * (exit_px - fill_px) / fill_px

        # stop sensitivity (NOT the gating number): worst-case same-bar
        # convention — if the fill bar's range also crosses the stop, the
        # full loss is taken there.
        stopped = False
        stop_ret = ret_fill
        for e in range(fill_i, exit_i):
            hit_stop = (l[e] <= stop) if long_side else (h[e] >= stop)
            if hit_stop:
                stop_px = min(o[e], stop) if long_side else max(o[e], stop)
                stop_ret = sign * 1e4 * (stop_px - fill_px) / fill_px
                stopped = True
                break

        tt = times[s]
        bucket = "open" if tt <= time(11, 0) else ("midday" if tt <= time(14, 0) else "close")
        trades.append({
            "signal_ts": str(idx_et[s]), "side": "long" if long_side else "short",
            "hold_bars": int(exit_i - fill_i), "exit_type": exit_type,
            "ret_trigger_bps": float(ret_trigger), "ret_fill_bps": float(ret_fill),
            "ret_with_stop_bps": float(stop_ret), "stopped": stopped,
            "tod_bucket": bucket,
        })

    df = pd.DataFrame(trades)

    def stats(sub: pd.DataFrame) -> dict:
        if sub.empty:
            return {"n": 0}
        r = sub["ret_trigger_bps"]
        return {
            "n": int(len(sub)),
            "mean_bps": round(float(r.mean()), 3),
            "median_bps": round(float(r.median()), 3),
            "std_bps": round(float(r.std()), 3),
            "t_stat": round(float(r.mean() / (r.std() / np.sqrt(len(sub)))), 2),
            "hit_rate": round(float((r > 0).mean()), 3),
            "mean_fill_bps": round(float(sub["ret_fill_bps"].mean()), 3),
            "mean_with_stop_bps": round(float(sub["ret_with_stop_bps"].mean()), 3),
        }

    years = (pd.Timestamp(is_end) - pd.Timestamp(is_start)).days / 365.25
    result = {
        "label": label,
        "bars_file": str(bars_path),
        "bars_range": [str(idx_et[0]), str(idx_et[-1])],
        "is_window": [is_start, is_end],
        "params": {
            "rsi_n": RSI_N, "atr_n": ATR_N, "band_bps": [BAND_LO_BPS, BAND_HI_BPS],
            "buffer": f"max({BUFFER_ATR_FRAC}*ATR5, ${BUFFER_FLOOR})",
            "pending_bars": PENDING_BARS, "warmup_bars": WARMUP_BARS,
            "round_trip_cost_bps": ROUND_TRIP_COST_BPS,
        },
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True
        ).stdout.strip(),
        "counts": counts,
        "trades_per_year": round(counts["filled"] / years, 1),
        "all": stats(df),
        "long": stats(df[df["side"] == "long"]) if not df.empty else {"n": 0},
        "short": stats(df[df["side"] == "short"]) if not df.empty else {"n": 0},
        "by_exit": {k: stats(g) for k, g in df.groupby("exit_type")} if not df.empty else {},
        "by_tod": {k: stats(g) for k, g in df.groupby("tod_bucket")} if not df.empty else {},
    }
    mean = result["all"].get("mean_bps")
    result["verdict"] = (
        "PASS (gross edge > modeled round-trip cost)"
        if mean is not None and mean > ROUND_TRIP_COST_BPS
        else "FAIL (mean gross continuation <= modeled round-trip cost — reject at spec validation)"
    )
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", type=Path, required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--is-start", default="2018-01-01")
    ap.add_argument("--is-end", default="2021-12-31")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--filter-sessions", action="store_true", help="drop phantom bars stamped after a half-day's official 13:00 close (core.data.calendar.filter_to_sessions). Default OFF so the recorded result reproduces byte-for-byte; see experiments/data-audits/2026-08-30-phantom-half-day-bars/.")
    args = ap.parse_args()

    result = run(args.bars, args.label, args.is_start, args.is_end,
                 filter_sessions=args.filter_sessions)
    if args.filter_sessions:
        result["filter_sessions"] = True
    args.out.mkdir(parents=True, exist_ok=True)
    out_file = args.out / f"results_{args.label}.json"
    out_file.write_text(json.dumps(result, indent=2) + "\n")

    print(f"\n=== rsi-5050 pre-gating diagnostic — {args.label} ===")
    print(f"IS window {args.is_start}..{args.is_end}  (gross of costs, trigger->recross-exit)")
    for k, v in result["counts"].items():
        print(f"  {k:>18}: {v}")
    print(f"  trades/year (filled): {result['trades_per_year']}")
    for name in ("all", "long", "short"):
        print(f"  {name:>6}: {result[name]}")
    print(f"  by exit: {result['by_exit']}")
    print(f"  by tod : {result['by_tod']}")
    print(f"\n  VERDICT vs {ROUND_TRIP_COST_BPS} bps bar: {result['verdict']}")
    print(f"  written -> {out_file}")


if __name__ == "__main__":
    main()
