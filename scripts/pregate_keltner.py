"""Pre-scoring gross-edge diagnostic for keltner-reversal (SPEC.md, PREGATE
section; every parameter and the gate rule frozen at user sign-off 2026-07-07,
before this script was written).

Measures, OUTSIDE the backtest engine, the raw gross follow-through of the
Keltner-reversal setup on 3-min DIA, IN-SAMPLE window ONLY (2018-01-01 ->
2022-12-31). The OOS (2023-2024) and WF (2025->) windows are hard-sliced out and
never read (the discipline is enforced here, not by a separate file).

The setup, exactly as frozen in SPEC.md:
  - 3-min RTH bars. Basis E = EMA(13) of close, ATR A = Wilder ATR(13), BOTH
    RESET EACH SESSION (no overnight-gap smear into the bands; SPEC Open Q3b).
    Outer band = E +/- 2.0*A (the setup band); inner 1.3 band is unused in the
    scored baseline. Midline target = E.
  - Higher-timeframe trend filter on 15-min bars: E15 = EMA(13) of 15-min
    closes, a CONTINUOUS cross-session series (see IMPLEMENTATION NOTE below).
    Uptrend iff the last completed 15-min close > E15 AND E15 is non-decreasing
    over the last 3 completed 15-min bars; downtrend symmetric. Longs only in an
    uptrend, shorts only in a downtrend.
  - Reversal (signal) bar s: LONG iff Ls < Louter_s AND Cs > Louter_s (pierced
    the lower outer band with the low, closed back inside) and HTF uptrend;
    SHORT symmetric on the upper band in a downtrend. Strict inequalities, no
    minimum penetration depth.
  - Entry: stop order at Hs + 1 tick (long) / Ls - 1 tick (short), tick = $0.01,
    armed on bars s+1..s+3 (3-bar expiry, then cancel). Gap-through (bar opens
    beyond the trigger) fills at the bar open.
  - Stop: 1 tick beyond the opposite signal-bar extreme -> risk D = signal-bar
    range + 2 ticks.
  - Exit (scored): the midline E. Target level for checking bar b is E through
    bar b-1 (last completed value), held constant across bar b (no same-bar
    lookahead). Aggressive opposite-band exit is a DIAGNOSTIC column only.
  - INTRABAR WORST-CASE ORDERING (LOCKED): on any bar spanning both the
    protective stop and the target (incl. the entry bar spanning entry+stop),
    the STOP is assumed to fill first -> full-D loss. Stop-before-target, always.
  - One position (or one live pending order) at a time; forced flat at the OPEN
    of the session's final 3-min bar. Gross of costs.

Gate (LOCKED before this script was written) - REJECT at spec validation if:
  1. IS mean gross return per trade <= 2.5 bps (the locked round-trip cost bar),
     OR
  2. the signal does not beat the matched intraday baseline (mean trend-direction
     open-to-open return over the same fill->exit bars: what you'd earn simply
     being in the market in the trend direction for the same clock time).

IMPLEMENTATION NOTE (flagged for quant-review, recorded because the frozen spec
is internally under-determined here). SPEC says "reset indicators each session,"
but the HTF trend uses EMA(13) on 15-min bars whose only warm-up is ">= 3
completed 15-min bars" - an EMA(13) cannot both reset each session and be valid
after 3 bars. The only coherent reading, implemented here: the 3-min BAND
indicators (E, A) reset each session (the Open Q3b rationale is specifically
about keeping the 17.5h gap out of the intraday ATR bands); the 15-min TREND
EMA is a continuous cross-session series (a slow trend context, not a band). The
">= 3 completed 15-min bars in the session" rule is kept as the entry warm-up,
which also guarantees the 3 slope bars are in-session. This choice affects only
the direction FILTER, never the edge measurement. No parameter is swept.

    uv run --extra paper python scripts/pregate_keltner.py \
        --bars data/DIA_3m.parquet --htf data/DIA_15m.parquet \
        --out experiments/keltner-reversal/2026-07-07-pregate
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

# --- frozen spec parameters (Sign-offs record, SPEC.md 2026-07-07) ---
EMA_N = 13            # basis EMA period (3-min), standard alpha = 2/(N+1)
ATR_N = 13            # Wilder ATR period (3-min)
MULT_OUTER = 2.0      # outer band multiplier = setup trigger
MULT_INNER = 1.3      # inner band - unused in the scored baseline
HTF_EMA_N = 13        # 15-min trend EMA (continuous)
HTF_SLOPE_BARS = 3    # slope evaluated over the last 3 completed 15-min bars
WARMUP_3M = EMA_N     # >= 13 completed 3-min bars in the session
WARMUP_15M = 3        # >= 3 completed 15-min bars in the session
TICK = 0.01           # DIA tick = 1 cent
PENDING_BARS = 3      # 3-bar entry expiry
COST_BAR_BPS = 2.5    # locked round-trip cost bar the gross edge must clear
RISK_PCT = 0.005      # R = 0.5% of equity, 100% notional cap (realized-R diag)
IS_START, IS_END = "2018-01-01", "2022-12-31"  # OOS/WF not read


def ema_per_session(close: np.ndarray, starts: np.ndarray, n: int) -> np.ndarray:
    """Standard EMA (alpha = 2/(n+1)), seeded on the simple mean of the first n
    bars, RESET at each session start. NaN before the seed."""
    out = np.full(len(close), np.nan)
    alpha = 2.0 / (n + 1)
    for k, s in enumerate(starts):
        e = starts[k + 1] if k + 1 < len(starts) else len(close)
        seg = close[s:e]
        if len(seg) < n:
            continue
        val = seg[:n].mean()
        out[s + n - 1] = val
        for i in range(n, len(seg)):
            val = alpha * seg[i] + (1.0 - alpha) * val
            out[s + i] = val
    return out


def atr_per_session(o, h, l, c, starts: np.ndarray, n: int) -> np.ndarray:
    """Wilder ATR (alpha = 1/n), RESET each session. First bar of a session uses
    H-L only (the overnight gap is not tradeable intraday range)."""
    out = np.full(len(c), np.nan)
    for k, s in enumerate(starts):
        e = starts[k + 1] if k + 1 < len(starts) else len(c)
        H, L, C = h[s:e], l[s:e], c[s:e]
        prev_c = np.roll(C, 1)
        tr = np.maximum.reduce([H - L, np.abs(H - prev_c), np.abs(L - prev_c)])
        tr[0] = H[0] - L[0]  # session boundary: no prior close
        if len(tr) < n:
            continue
        val = tr[:n].mean()
        out[s + n - 1] = val
        for i in range(n, len(tr)):
            val = (val * (n - 1) + tr[i]) / n
            out[s + i] = val
    return out


def ema_continuous(close: np.ndarray, n: int) -> np.ndarray:
    """Standard EMA over the whole series (the 15-min trend context)."""
    out = np.full(len(close), np.nan)
    if len(close) < n:
        return out
    alpha = 2.0 / (n + 1)
    val = close[:n].mean()
    out[n - 1] = val
    for i in range(n, len(close)):
        val = alpha * close[i] + (1.0 - alpha) * val
        out[i] = val
    return out


def build_htf_trend(m3: pd.DataFrame, m15: pd.DataFrame) -> np.ndarray:
    """For each 3-min bar, the HTF trend state (+1 up / -1 down / 0 none) from the
    most recently COMPLETED 15-min bar (close_15 <= close_3), continuous E15."""
    ts3 = m3.index.values.astype("int64")   # UTC ns
    ts15 = m15.index.values.astype("int64")
    c15 = m15["close"].to_numpy(float)
    e15 = ema_continuous(c15, HTF_EMA_N)

    idx15_et = m15.index.tz_convert(ET)
    date15 = np.array([t.date() for t in idx15_et])
    pos15 = np.ones(len(m15), dtype=int)      # 1-based position within its session
    for i in range(1, len(m15)):
        pos15[i] = pos15[i - 1] + 1 if date15[i] == date15[i - 1] else 1

    idx3_et = m3.index.tz_convert(ET)
    date3 = np.array([t.date() for t in idx3_et])

    # last completed 15-min bar for each 3-min bar
    hidx = np.searchsorted(ts15, ts3, side="right") - 1

    trend = np.zeros(len(m3), dtype=int)
    for i in range(len(m3)):
        h = hidx[i]
        if h < HTF_SLOPE_BARS - 1:
            continue
        if date15[h] != date3[i] or pos15[h] < WARMUP_15M:
            continue  # >= 3 completed 15-min bars IN this session
        e0, e1, e2 = e15[h], e15[h - 1], e15[h - 2]
        if np.isnan(e0) or np.isnan(e1) or np.isnan(e2):
            continue
        cc = c15[h]
        if cc > e0 and e0 >= e1 >= e2:
            trend[i] = 1
        elif cc < e0 and e0 <= e1 <= e2:
            trend[i] = -1
    return trend


def simulate(m3: pd.DataFrame, m15: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    idx_et = m3.index.tz_convert(ET)
    dates = np.array([t.date() for t in idx_et])
    times = np.array([t.time() for t in idx_et])
    o = m3["open"].to_numpy(float)
    h = m3["high"].to_numpy(float)
    l = m3["low"].to_numpy(float)
    c = m3["close"].to_numpy(float)
    n = len(m3)

    starts = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    session_last = {}
    for k, s in enumerate(starts):
        e = starts[k + 1] if k + 1 < len(starts) else n
        session_last[dates[s]] = e - 1

    E = ema_per_session(c, starts, EMA_N)
    A = atr_per_session(o, h, l, c, starts, ATR_N)
    trend = build_htf_trend(m3, m15)

    d0, d1 = pd.Timestamp(IS_START).date(), pd.Timestamp(IS_END).date()
    counts = {"sessions_is": 0, "reversal_bars": 0, "signals": 0,
              "long_signals": 0, "short_signals": 0, "filled": 0, "expired": 0}
    for s in starts:
        if d0 <= dates[s] <= d1:
            counts["sessions_is"] += 1

    trades = []
    busy_until = -1  # one position / one live pending order at a time

    for s in range(n):
        if not (d0 <= dates[s] <= d1):
            continue  # IS only - OOS/WF stay unread
        if s <= busy_until:
            continue
        if np.isnan(E[s]) or np.isnan(A[s]):
            continue  # 3-min band warm-up (>= 13 completed bars this session)

        louter = E[s] - MULT_OUTER * A[s]
        uouter = E[s] + MULT_OUTER * A[s]
        long_rev = (l[s] < louter) and (c[s] > louter)
        short_rev = (h[s] > uouter) and (c[s] < uouter)
        if long_rev or short_rev:
            counts["reversal_bars"] += 1

        side = 0
        if long_rev and trend[s] == 1:
            side = 1
        elif short_rev and trend[s] == -1:
            side = -1
        if side == 0:
            continue
        counts["signals"] += 1
        counts["long_signals" if side == 1 else "short_signals"] += 1

        last = session_last[dates[s]]
        if side == 1:
            trigger, stop = h[s] + TICK, l[s] - TICK
        else:
            trigger, stop = l[s] - TICK, h[s] + TICK
        D = abs(trigger - stop)  # signal-bar range + 2 ticks

        # --- entry fill scan: bars s+1..s+3, same session (3-bar expiry) ---
        bmax = min(s + PENDING_BARS, last)
        fill_i, fill_px = None, None
        for b in range(s + 1, bmax + 1):
            hit = (h[b] >= trigger) if side == 1 else (l[b] <= trigger)
            if hit:
                if side == 1:
                    fill_px = o[b] if o[b] > trigger else trigger
                else:
                    fill_px = o[b] if o[b] < trigger else trigger
                fill_i = b
                break
        if fill_i is None:
            counts["expired"] += 1
            busy_until = bmax  # occupied through the pending window
            continue
        counts["filled"] += 1
        sign = float(side)

        # --- exit: worst-case stop-before-target each bar (entry bar included:
        #     spans entry+stop => stopped same bar). Midline level uses E through
        #     the previous completed bar. Forced flat at o[last] otherwise. ---
        def scan_exit(target_of):
            exit_i, reason, exit_px = last, "time", o[last]
            for e in range(fill_i, last):
                hit_stop = (l[e] <= stop) if side == 1 else (h[e] >= stop)
                if hit_stop:
                    if side == 1:
                        exit_px = o[e] if o[e] < stop else stop
                    else:
                        exit_px = o[e] if o[e] > stop else stop
                    return e, "stop", exit_px
                lvl = target_of(e)
                if lvl is None or np.isnan(lvl):
                    continue
                hit_tgt = (h[e] >= lvl) if side == 1 else (l[e] <= lvl)
                if hit_tgt:
                    if side == 1:
                        exit_px = o[e] if o[e] >= lvl else lvl
                    else:
                        exit_px = o[e] if o[e] <= lvl else lvl
                    return e, "target", exit_px
            return exit_i, reason, exit_px

        # scored exit: midline E (through e-1)
        exit_i, reason, exit_px = scan_exit(lambda e: E[e - 1])
        gross_bps = sign * 1e4 * (exit_px - fill_px) / fill_px
        gross_R = sign * (exit_px - fill_px) / D

        # diagnostic-only: aggressive opposite-band exit (through e-1)
        opp_i, opp_reason, opp_px = scan_exit(
            lambda e: (E[e - 1] + sign * MULT_OUTER * A[e - 1])
            if not np.isnan(A[e - 1]) else None
        )
        gross_opp_bps = sign * 1e4 * (opp_px - fill_px) / fill_px

        # matched baseline: trend-direction open-to-open over the same bars
        base_bps = sign * 1e4 * (o[exit_i] - o[fill_i]) / o[fill_i]

        d_frac = D / fill_px
        notional_frac = min(RISK_PCT / d_frac, 1.0)
        tt = times[s]
        bucket = ("open" if tt <= time(11, 0)
                  else "midday" if tt <= time(14, 0) else "close")
        trades.append({
            "signal_ts": str(idx_et[s]), "year": dates[s].year,
            "side": "long" if side == 1 else "short",
            "fill_delay": int(fill_i - s), "hold_bars": int(exit_i - fill_i),
            "exit_reason": reason, "gross_bps": float(gross_bps),
            "gross_R": float(gross_R), "baseline_bps": float(base_bps),
            "gross_opp_bps": float(gross_opp_bps), "opp_exit": opp_reason,
            "stop_dist_bps": float(1e4 * d_frac),
            "notional_frac": float(notional_frac),
            "realized_risk_pct": float(100 * notional_frac * d_frac),
            "tod_bucket": bucket,
        })
        busy_until = exit_i

    return pd.DataFrame(trades), counts


def stats(sub: pd.DataFrame, col: str = "gross_bps") -> dict:
    if sub.empty:
        return {"n": 0}
    r = sub[col]
    sd = float(r.std())
    return {
        "n": int(len(sub)),
        "mean_bps": round(float(r.mean()), 3),
        "median_bps": round(float(r.median()), 2),
        "std_bps": round(sd, 1),
        "t_stat": round(float(r.mean() / (sd / np.sqrt(len(r)))), 2) if sd else None,
        "hit_rate": round(float((r > 0).mean()), 3),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", type=Path, default=REPO / "data/DIA_3m.parquet")
    ap.add_argument("--htf", type=Path, default=REPO / "data/DIA_15m.parquet")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    m3 = pd.read_parquet(args.bars)
    m15 = pd.read_parquet(args.htf)
    df, counts = simulate(m3, m15)

    def sha256(p: Path) -> str:
        import hashlib
        return hashlib.sha256(p.read_bytes()).hexdigest()

    if df.empty:
        result = {"strategy": "keltner-reversal", "counts": counts,
                  "verdict": "REJECT at spec validation - zero filled trades in IS"}
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "results.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        return

    mean_gross = float(df["gross_bps"].mean())
    mean_base = float(df["baseline_bps"].mean())
    edge = mean_gross - mean_base
    gate_pass = mean_gross > COST_BAR_BPS and edge > 0.0
    years = df.groupby("year")["gross_bps"].agg(["count", "mean"]).round(3)

    result = {
        "strategy": "keltner-reversal",
        "bars_file": str(args.bars), "bars_sha256": sha256(args.bars),
        "htf_file": str(args.htf), "htf_sha256": sha256(args.htf),
        "bars_range": [str(m3.index[0]), str(m3.index[-1])],
        "is_window": [IS_START, IS_END],
        "windows_not_read": "OOS 2023-2024, WF 2025->",
        "params": {
            "ema_n": EMA_N, "atr_n": ATR_N, "mult_outer": MULT_OUTER,
            "mult_inner_UNUSED": MULT_INNER, "htf_ema_n": HTF_EMA_N,
            "htf_slope_bars": HTF_SLOPE_BARS, "tick": TICK,
            "pending_bars": PENDING_BARS, "cost_bar_bps": COST_BAR_BPS,
            "risk_pct": RISK_PCT,
            "session_reset": "3-min band E/A reset per session; 15-min trend EMA continuous",
        },
        "gate": f"IS mean gross > {COST_BAR_BPS} bps AND > matched trend-direction baseline",
        "counts": counts,
        "trades_per_year": round(counts["filled"] / 5.0, 1),
        "all": stats(df),
        "matched_baseline_bps": round(mean_base, 3),
        "edge_vs_baseline_bps": round(edge, 3),
        "long": stats(df[df["side"] == "long"]),
        "short": stats(df[df["side"] == "short"]),
        "by_exit": {k: stats(g) for k, g in df.groupby("exit_reason")},
        "by_tod": {k: stats(g) for k, g in df.groupby("tod_bucket")},
        "by_year": {str(y): {"n": int(r["count"]), "mean_bps": float(r["mean"])}
                    for y, r in years.iterrows()},
        "fill_rate": round(float(counts["filled"] / max(counts["signals"], 1)), 3),
        "stop_rate": round(float((df["exit_reason"] == "stop").mean()), 3),
        "target_rate": round(float((df["exit_reason"] == "target").mean()), 3),
        "time_exit_rate": round(float((df["exit_reason"] == "time").mean()), 3),
        "median_hold_bars": float(df["hold_bars"].median()),
        "stop_dist_bps_quartiles": [round(float(q), 1) for q in
                                    df["stop_dist_bps"].quantile([0.25, 0.5, 0.75])],
        "realized_risk_pct_median": round(float(df["realized_risk_pct"].median()), 3),
        "notional_cap_binds_frac": round(float((df["notional_frac"] >= 1.0).mean()), 3),
        "worst_trade_R": round(float(df["gross_R"].min()), 2),
        "diagnostic_opposite_band_NOT_SCORED": {
            "all": stats(df, "gross_opp_bps"),
            "target_hit_frac": round(float((df["opp_exit"] == "target").mean()), 4),
        },
        "verdict": (
            "PASS pre-scoring gate - reuse orb's intrabar-stop core, then engine backtest IS->OOS"
            if gate_pass else
            "REJECT at spec validation - IS gross edge fails the locked bar "
            f"(mean gross {'<=' if mean_gross <= COST_BAR_BPS else '>'} {COST_BAR_BPS} bps cost bar; "
            f"edge vs matched baseline {edge:+.3f} bps); no tuning, no parameter/HTF/instrument shopping"
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
