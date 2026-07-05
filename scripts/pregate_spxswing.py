"""Pre-scoring decomposition diagnostic for spx-swing (SPEC.md, Success
criteria + Decisions record, both frozen 2026-07-05 before this ran).

Simulates, OUTSIDE the backtest engine, the exact frozen rules on the spliced
daily series and reports, IS and OOS separately:

  (a) mean net return per trade (entry next open; exits per spec; minus the
      locked 8 bps round trip), and
  (b) the same-horizon unconditional open->open drift baseline
      (per-trade baseline = hold_days x window mean daily open->open return).

Binding gate (operationalized in SPEC.md before running): REJECT at
spec-validation if, in the OOS window, mean net return per trade <= 0, or the
net edge over the unconditional baseline <= 0. t-stats reported for honesty
about "~0" but the sign rule is the gate. The WF window (2025->) is NOT read.

Also computed, pre-registered as diagnostic-only (Decisions record #4): the
limit-at-C(d) entry variant — never the verdict number.

    uv run python scripts/pregate_spxswing.py \
        --bars data/SPY_daily_adj_spliced.parquet \
        --out experiments/spx-swing/2026-07-05-pregate
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

# --- frozen spec parameters (SPEC.md 2026-07-05; never swept) ---
RSI_ENTRY = 10.0
RSI_EXIT = 65.0
SMA_N = 200
ATR_N = 14
STOP_ATR = 3.0
MAX_HOLD_CLOSES = 9  # exit signal after the close of the 9th session post-fill
WARMUP = 250
COST_RT_BPS = 8.0  # 1.0 half-spread + 3.0 slippage, per side, both auction fills

IS_WINDOW = ("2005-01-01", "2017-12-31")
OOS_WINDOW = ("2018-01-01", "2024-12-31")  # WF 2025-> deliberately untouched here


def rsi2_wilder(close: np.ndarray) -> np.ndarray:
    n = 2
    delta = np.diff(close, prepend=close[0])
    delta[0] = 0.0
    up, dn = np.maximum(delta, 0.0), np.maximum(-delta, 0.0)
    avg_u = np.full(len(close), np.nan)
    avg_d = np.full(len(close), np.nan)
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


def atr_wilder(h: np.ndarray, l: np.ndarray, c: np.ndarray, n: int) -> np.ndarray:
    prev_c = np.roll(c, 1)
    prev_c[0] = c[0]
    tr = np.maximum.reduce([h - l, np.abs(h - prev_c), np.abs(l - prev_c)])
    out = np.full(len(c), np.nan)
    out[n - 1] = tr[:n].mean()
    for i in range(n, len(c)):
        out[i] = (out[i - 1] * (n - 1) + tr[i]) / n
    return out


def simulate(o, h, l, c, rsi, sma, atr, entry_mode: str) -> list[dict]:
    """One continuous pass over the whole series. entry_mode: 'open' (scored
    baseline, fill at O[s+1]) or 'limit' (diagnostic, limit at C[s] working
    day s+1 only; unfilled = no trade)."""
    n = len(c)
    trades = []
    pos_fill_px = pos_fill_i = pos_signal_i = pos_stop = None
    pending_signal_i = None  # entry signalled at close, fills next open
    cooldown_until = -1  # entry evaluation allowed again from this index's close

    for i in range(WARMUP, n - 1):
        # --- fill a pending entry at today's open ---
        if pending_signal_i is not None:
            s = pending_signal_i
            pending_signal_i = None
            if entry_mode == "open":
                fill = o[i]
            else:  # limit at C(s), working today only
                fill = min(o[i], c[s]) if l[i] <= c[s] else None
            if fill is not None:
                pos_fill_px, pos_fill_i, pos_signal_i = fill, i, s
                pos_stop = fill - STOP_ATR * atr[s]

        # --- close of day i: exits first ---
        if pos_fill_px is not None:
            reason = None
            if rsi[i] >= RSI_EXIT:
                reason = "strength"
            elif c[i] <= pos_stop:
                reason = "stop"
            elif i - pos_fill_i >= MAX_HOLD_CLOSES:
                reason = "time"
            if reason is not None:
                x = i + 1  # exit fills at the next open
                gross_bps = 1e4 * (o[x] / pos_fill_px - 1.0)
                trades.append({
                    "signal_date": None,  # filled in by caller from index
                    "signal_i": pos_signal_i,
                    "fill_i": pos_fill_i,
                    "exit_i": x,
                    "hold_days": x - pos_fill_i,
                    "exit_reason": reason,
                    "gross_bps": float(gross_bps),
                    "net_bps": float(gross_bps - COST_RT_BPS),
                })
                pos_fill_px = pos_fill_i = pos_signal_i = pos_stop = None
                cooldown_until = x  # entry evaluation resumes at exit-fill close
                continue  # exit signal suppresses same-close entry evaluation

        # --- entry evaluation at close of day i ---
        if pos_fill_px is None and pending_signal_i is None and i >= cooldown_until:
            if c[i] >= sma[i] and rsi[i] <= RSI_ENTRY:
                pending_signal_i = i

    return trades


def window_stats(df: pd.DataFrame, daily_oo_mean_bps: float) -> dict:
    if df.empty:
        return {"n": 0}
    net, gross = df["net_bps"], df["gross_bps"]
    baseline = df["hold_days"] * daily_oo_mean_bps
    edge = net - baseline

    def t(x):
        return round(float(x.mean() / (x.std() / np.sqrt(len(x)))), 2) if len(x) > 1 else None

    return {
        "n": int(len(df)),
        "trades_per_year": round(len(df) / (df["years"].iloc[0]), 1),
        "hit_rate_net": round(float((net > 0).mean()), 3),
        "mean_gross_bps": round(float(gross.mean()), 2),
        "mean_net_bps": round(float(net.mean()), 2),
        "median_net_bps": round(float(net.median()), 2),
        "t_net": t(net),
        "mean_hold_days": round(float(df["hold_days"].mean()), 2),
        "uncond_baseline_bps_same_horizon": round(float(baseline.mean()), 2),
        "mean_edge_vs_uncond_bps": round(float(edge.mean()), 2),
        "t_edge": t(edge),
        "worst_trade_net_bps": round(float(net.min()), 2),
        "best_trade_net_bps": round(float(net.max()), 2),
        "by_exit": {
            k: {"n": int(len(g)), "mean_net_bps": round(float(g["net_bps"].mean()), 2)}
            for k, g in df.groupby("exit_reason")
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", type=Path, default=REPO / "data/SPY_daily_adj_spliced.parquet")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    bars = pd.read_parquet(args.bars)
    dates = pd.DatetimeIndex(bars.index.tz_convert(ET).date)
    o = bars["open"].to_numpy(float)
    h = bars["high"].to_numpy(float)
    l = bars["low"].to_numpy(float)
    c = bars["close"].to_numpy(float)

    rsi = rsi2_wilder(c)
    sma = pd.Series(c).rolling(SMA_N).mean().to_numpy()
    atr = atr_wilder(h, l, c, ATR_N)
    daily_oo = pd.Series(o).pct_change().shift(-1)  # return open(t)->open(t+1) at slot t

    results = {}
    for mode in ("open", "limit"):
        trades = simulate(o, h, l, c, rsi, sma, atr, mode)
        df = pd.DataFrame(trades)
        if not df.empty:
            df["signal_date"] = dates[df["signal_i"]]
        per_window = {}
        for name, (w0, w1) in {"is": IS_WINDOW, "oos": OOS_WINDOW}.items():
            w0, w1 = pd.Timestamp(w0), pd.Timestamp(w1)
            in_w = (dates >= w0) & (dates <= w1)
            uncond = float(daily_oo[in_w].mean() * 1e4)
            sub = df[(df["signal_date"] >= w0) & (df["signal_date"] <= w1)].copy() if not df.empty else df
            if not sub.empty:
                sub["years"] = (w1 - w0).days / 365.25
            stats = window_stats(sub, uncond)
            stats["uncond_daily_oo_bps"] = round(uncond, 3)
            per_window[name] = stats
        results[mode] = per_window

    scored = results["open"]["oos"]
    gate_pass = (
        scored.get("n", 0) > 0
        and scored["mean_net_bps"] > 0
        and scored["mean_edge_vs_uncond_bps"] > 0
    )
    verdict = (
        "PASS pre-scoring gate — proceed to implementation and engine backtest"
        if gate_pass
        else "REJECT at spec-validation — OOS conditional edge is ~0/negative net of "
        "costs (binding rule frozen in SPEC.md Decisions record); nothing to tune toward"
    )

    out = {
        "strategy": "spx-swing",
        "bars_file": str(args.bars),
        "bars_range": [str(dates[0].date()), str(dates[-1].date())],
        "windows": {"is": IS_WINDOW, "oos": OOS_WINDOW, "wf": "2025-01-01 -> (NOT READ)"},
        "params": {
            "rsi_entry": RSI_ENTRY, "rsi_exit": RSI_EXIT, "sma_n": SMA_N,
            "atr_n": ATR_N, "stop_atr": STOP_ATR, "max_hold_closes": MAX_HOLD_CLOSES,
            "warmup": WARMUP, "cost_round_trip_bps": COST_RT_BPS,
        },
        "gate": "OOS (scored 'open' entry): mean_net_bps > 0 AND mean_edge_vs_uncond_bps > 0",
        "scored_open_entry": results["open"],
        "diagnostic_limit_entry_NOT_SCORED": results["limit"],
        "verdict": verdict,
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True
        ).stdout.strip(),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(json.dumps(out, indent=2) + "\n")

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
