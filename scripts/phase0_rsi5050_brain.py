"""Phase 0 separability audit for rsi-5050-brain (SPEC.md, Phase gates).

Tests the ONE claim the brain hypothesis rests on: that the rsi-5050 trade
population is a mixture of an EOD bucket (+23.50 bps, n=101) and a recross
bucket (-3.21 bps, n=666) that is SEPARABLE EX ANTE from context available at
the signal bar's close.

Locked gate (SPEC.md, frozen 2026-08-30, before this script was written):
    cross-validated mean gross of selected trades >= 2.0 bps, retaining >= 150
    trades, using a logistic regression on the frozen 17-feature set with a
    per-fold threshold retaining 40% of trades.
On FAIL: reject at spec validation. No LLM arm, no feature additions, no
threshold relaxation, no tree models.

IN-SAMPLE ONLY (2018-2021). OOS (2022-2024) and WF (2025+) are never read.

    .venv/bin/python scripts/phase0_rsi5050_brain.py \
        --out experiments/rsi-5050-brain/2026-08-30-phase0
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
from datetime import time
from pathlib import Path

import numpy as np
import pandas as pd

from core.strategy import ET

REPO = Path(__file__).resolve().parents[1]

# --- Shared mechanics: load the ORIGINAL pregate module so the indicator math
# and every locked parameter are literally the same code, not a re-typing. ---
_spec = importlib.util.spec_from_file_location(
    "pregate_rsi5050", REPO / "scripts" / "pregate_rsi5050.py"
)
PG = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(PG)

# --- Locked Phase 0 parameters (SPEC.md) ---
RETENTION = 0.40          # Q1: single value, no sweep
N_FOLDS = 5
GATE_MEAN_BPS = 2.0
GATE_MIN_TRADES = 150
RIDGE = 1.0               # L2 on standardised features; intercept unpenalised

# Inherited verification targets (experiments/rsi-5050/2026-07-05-pregate/results_5min.json)
EXPECT = {"n": 767, "mean_bps": 0.304, "eod": 101, "recross": 666}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------
# 1. Rebuild the per-trade log (mechanics copied verbatim from pregate run())
# --------------------------------------------------------------------------
def rebuild_trades(bars_path: Path, is_start: str, is_end: str,
                   filter_sessions: bool = False) -> tuple[pd.DataFrame, dict, dict]:
    bars = pd.read_parquet(bars_path)
    n_raw = len(bars)
    if filter_sessions:
        from core.data.calendar import filter_to_sessions
        bars = filter_to_sessions(bars)
        print(f"  [filter_to_sessions] dropped {n_raw - len(bars)} phantom bars "
              f"stamped after their session's official close\n")
    idx_et = bars.index.tz_convert(ET)
    o = bars["open"].to_numpy(float)
    h = bars["high"].to_numpy(float)
    l = bars["low"].to_numpy(float)  # noqa: E741
    c = bars["close"].to_numpy(float)
    v = bars["volume"].to_numpy(float)
    dates = np.array([t.date() for t in idx_et])
    times = np.array([t.time() for t in idx_et])
    n = len(bars)

    first_of_session = np.zeros(n, dtype=bool)
    first_of_session[0] = True
    first_of_session[1:] = dates[1:] != dates[:-1]

    session_last, session_first = {}, {}
    for i in range(n):
        session_last[dates[i]] = i
        session_first.setdefault(dates[i], i)

    rsi = PG.rsi_wilder(c, PG.RSI_N)
    atr = PG.wilder(PG.true_range(o, h, l, c, first_of_session), PG.ATR_N)
    atr_bps = 1e4 * atr / c

    cross_up = np.zeros(n, dtype=bool)
    cross_dn = np.zeros(n, dtype=bool)
    cross_up[1:] = (rsi[:-1] <= PG.MIDLINE) & (rsi[1:] > PG.MIDLINE)
    cross_dn[1:] = (rsi[:-1] >= PG.MIDLINE) & (rsi[1:] < PG.MIDLINE)
    any_cross = cross_up | cross_dn
    # bars since the previous midline cross (feature 5)
    since_cross = np.full(n, np.nan)
    last_x = -1
    for i in range(n):
        if last_x >= 0:
            since_cross[i] = i - last_x
        if any_cross[i]:
            last_x = i

    # session cumulative VWAP + running range (features 9, 10)
    pv = c * v
    cum_pv = np.zeros(n)
    cum_v = np.zeros(n)
    run_hi = np.zeros(n)
    run_lo = np.zeros(n)
    for i in range(n):
        if first_of_session[i]:
            cum_pv[i], cum_v[i] = pv[i], v[i]
            run_hi[i], run_lo[i] = h[i], l[i]
        else:
            cum_pv[i], cum_v[i] = cum_pv[i - 1] + pv[i], cum_v[i - 1] + v[i]
            run_hi[i], run_lo[i] = max(run_hi[i - 1], h[i]), min(run_lo[i - 1], l[i])
    vwap = np.divide(cum_pv, cum_v, out=np.full(n, np.nan), where=cum_v > 0)

    # daily series for ADR-20 and the overnight gap (features 10, 11)
    day_idx = pd.Series(dates)
    daily = pd.DataFrame({"d": dates, "h": h, "l": l, "c": c, "o": o})
    dh = daily.groupby("d")["h"].max()
    dl = daily.groupby("d")["l"].min()
    dc = daily.groupby("d")["c"].last()
    do = daily.groupby("d")["o"].first()
    adr20 = (dh - dl).rolling(20).mean().shift(1)          # prior 20 sessions only
    prev_close = dc.shift(1)
    gap_bps = 1e4 * (do - prev_close) / prev_close
    del day_idx

    d0, d1 = pd.Timestamp(is_start).date(), pd.Timestamp(is_end).date()
    trades = []
    counts = {"crosses_is": 0, "band_pass": 0, "time_gated": 0, "armed": 0,
              "cancelled_recross": 0, "cancelled_stale": 0, "cancelled_cutoff": 0,
              "filled": 0}

    for s in range(PG.WARMUP_BARS, n):
        if not (cross_up[s] or cross_dn[s]):
            continue
        if not (d0 <= dates[s] <= d1):
            continue
        counts["crosses_is"] += 1
        if not (PG.BAND_LO_BPS <= atr_bps[s] <= PG.BAND_HI_BPS):
            continue
        counts["band_pass"] += 1

        last_i = session_last[dates[s]]
        arm_cutoff = (idx_et[last_i] - PG.ARM_CUTOFF_BEFORE_CLOSE).time()
        if times[s] <= PG.FIRST_SIGNAL_ET or times[s] > arm_cutoff:
            continue
        counts["time_gated"] += 1

        long_side = bool(cross_up[s])
        buffer = max(PG.BUFFER_ATR_FRAC * atr[s], PG.BUFFER_FLOOR)
        trigger = h[s] + buffer if long_side else l[s] - buffer
        stop = l[s] - buffer if long_side else h[s] + buffer
        counts["armed"] += 1

        fill_i, cancelled = None, None
        for j in range(s + 1, min(s + PG.PENDING_BARS, last_i) + 1):
            if times[j] > arm_cutoff:
                cancelled = "cutoff"
                break
            if (h[j] >= trigger) if long_side else (l[j] <= trigger):
                fill_i = j
                break
            if cross_dn[j] if long_side else cross_up[j]:
                cancelled = "recross"
                break
        if fill_i is None:
            counts[f"cancelled_{cancelled or 'stale'}"] += 1
            continue
        counts["filled"] += 1

        fill_px = max(o[fill_i], trigger) if long_side else min(o[fill_i], trigger)

        exit_i, exit_type = last_i, "eod"
        for e in range(fill_i, last_i):
            if cross_dn[e] if long_side else cross_up[e]:
                exit_i, exit_type = e + 1, "recross"
                break
        exit_px = o[exit_i]

        sign = 1.0 if long_side else -1.0
        ret_trigger = sign * 1e4 * (exit_px - trigger) / trigger
        ret_fill = sign * 1e4 * (exit_px - fill_px) / fill_px

        stopped, stop_ret = False, ret_fill
        for e in range(fill_i, exit_i):
            if (l[e] <= stop) if long_side else (h[e] >= stop):
                stop_px = min(o[e], stop) if long_side else max(o[e], stop)
                stop_ret = sign * 1e4 * (stop_px - fill_px) / fill_px
                stopped = True
                break

        tt = times[s]
        bucket = "open" if tt <= time(11, 0) else ("midday" if tt <= time(14, 0) else "close")
        sess_open_px = o[session_first[dates[s]]]
        trades.append({
            "signal_ts": idx_et[s], "s": s, "date": dates[s], "side": "long" if long_side else "short",
            "hold_bars": int(exit_i - fill_i), "exit_type": exit_type,
            "ret_trigger_bps": float(ret_trigger), "ret_fill_bps": float(ret_fill),
            "ret_with_stop_bps": float(stop_ret), "stopped": stopped, "tod_bucket": bucket,
            # --- frozen feature set (SPEC.md) ---
            "f01_atr5_bps": float(atr_bps[s]),
            "f02_atr5_slope_3": float(atr_bps[s] - atr_bps[s - 3]),
            "f03_bar_range_over_atr": float((h[s] - l[s]) / atr[s]) if atr[s] > 0 else np.nan,
            "f04_rsi_jump": float(rsi[s] - rsi[s - 1]),
            "f05_bars_since_cross": float(since_cross[s]),
            "f06_buffer_over_range": float(buffer / (h[s] - l[s])) if h[s] > l[s] else np.nan,
            "f07_minutes_since_open": float((idx_et[s] - idx_et[session_first[dates[s]]]).total_seconds() / 60.0),
            "f08_ret_since_open_bps": float(sign * 1e4 * (c[s] - sess_open_px) / sess_open_px),
            "f09_dist_from_vwap_bps": float(sign * 1e4 * (c[s] - vwap[s]) / vwap[s]),
            "f10_session_range_over_adr": float((run_hi[s] - run_lo[s]) / adr20.get(dates[s], np.nan)),
            "f11_overnight_gap_bps": float(sign * gap_bps.get(dates[s], np.nan)),
            "f17_day_of_week": int(idx_et[s].weekday()),
        })

    df = pd.DataFrame(trades)
    meta = {"bars": {"path": str(bars_path), "sha256": sha256(bars_path),
                     "range": [str(idx_et[0]), str(idx_et[-1])], "rows": int(n)}}
    return df, counts, meta


# --------------------------------------------------------------------------
# 2. Cross-sectional / macro features (12-16) from SPY, QQQ and the calendar
# --------------------------------------------------------------------------
def attach_cross_features(df: pd.DataFrame, meta: dict) -> pd.DataFrame:
    dia = pd.read_parquet(REPO / "data" / "DIA_5m.parquet")
    out = {}
    for sym in ("SPY", "QQQ"):
        p = REPO / "data" / f"{sym}_5m.parquet"
        meta["bars_" + sym] = {"path": str(p), "sha256": sha256(p)}
        b = pd.read_parquet(p)
        r5 = b["close"].pct_change(5)
        out[sym] = r5.reindex(dia.index).ffill(limit=1)

    sign = np.where(df["side"].to_numpy() == "long", 1.0, -1.0)
    ts = pd.DatetimeIndex(df["signal_ts"]).tz_convert("UTC")
    for sym, col in (("SPY", "f12_spy_align"), ("QQQ", "f13_qqq_align")):
        vals = out[sym].reindex(ts).to_numpy(float)
        df[col] = sign * np.sign(vals) * np.minimum(np.abs(vals) * 1e4, 500.0)

    dia_r = dia["close"].pct_change()
    spy_b = pd.read_parquet(REPO / "data" / "SPY_5m.parquet")
    spy_r = spy_b["close"].pct_change().reindex(dia.index).ffill(limit=1)
    corr20 = dia_r.rolling(20).corr(spy_r)
    df["f14_spy_dia_corr_20"] = corr20.reindex(ts).to_numpy(float)

    # f15 DEVIATION (recorded before results): VIX is unavailable offline and no
    # vendor for it exists in this repo. Substituted with SPY 20-day realised
    # volatility from SPY_5m daily closes — same vol-regime role, no new vendor.
    spy_daily = spy_b["close"].groupby(spy_b.index.tz_convert(ET).date).last()
    rv20 = spy_daily.pct_change().rolling(20).std() * np.sqrt(252) * 100.0
    rv20_prev = rv20.shift(1)
    d = df["date"].to_numpy()
    df["f15a_spy_rvol20"] = [float(rv20_prev.get(x, np.nan)) for x in d]
    df["f15b_spy_rvol20_chg"] = [float(rv20_prev.diff().get(x, np.nan)) for x in d]

    fomc = pd.read_csv(REPO / "strategies" / "fomc-drift" / "fomc_calendar.csv")
    fdates = pd.to_datetime(fomc["end_date"]).dt.date.to_numpy()
    df["f16a_is_fomc_day"] = [1.0 if x in set(fdates) else 0.0 for x in d]
    df["f16b_days_to_fomc"] = [
        float(min((f - x).days for f in fdates if f >= x), ) if any(f >= x for f in fdates) else np.nan
        for x in d
    ]
    return df


# --------------------------------------------------------------------------
# 3. Logistic regression (IRLS, numpy — no sklearn dependency)
# --------------------------------------------------------------------------
def fit_logistic(X: np.ndarray, y: np.ndarray, ridge: float = RIDGE, iters: int = 50) -> np.ndarray:
    Xd = np.column_stack([np.ones(len(X)), X])
    w = np.zeros(Xd.shape[1])
    pen = np.eye(Xd.shape[1]) * ridge
    pen[0, 0] = 0.0
    for _ in range(iters):
        eta = np.clip(Xd @ w, -30, 30)
        mu = 1.0 / (1.0 + np.exp(-eta))
        W = np.clip(mu * (1 - mu), 1e-6, None)
        H = Xd.T @ (Xd * W[:, None]) + pen
        g = Xd.T @ (y - mu) - pen @ w
        try:
            step = np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            break
        w = w + step
        if np.max(np.abs(step)) < 1e-8:
            break
    return w


def predict(w: np.ndarray, X: np.ndarray) -> np.ndarray:
    eta = np.clip(np.column_stack([np.ones(len(X)), X]) @ w, -30, 30)
    return 1.0 / (1.0 + np.exp(-eta))


def norm_sf(z: np.ndarray | float) -> np.ndarray | float:
    """Two-sided normal tail. n~767 so the t/normal difference is immaterial."""
    from math import erfc, sqrt
    z = np.atleast_1d(np.asarray(z, dtype=float))
    return np.array([erfc(abs(v) / sqrt(2.0)) for v in z])


def benjamini_hochberg(p: np.ndarray, q: float = 0.10) -> np.ndarray:
    n = len(p)
    order = np.argsort(p)
    thresh = q * (np.arange(1, n + 1) / n)
    passed = p[order] <= thresh
    k = np.max(np.where(passed)[0]) + 1 if passed.any() else 0
    out = np.zeros(n, dtype=bool)
    out[order[:k]] = True
    return out


FEATURES = [
    "f01_atr5_bps", "f02_atr5_slope_3", "f03_bar_range_over_atr", "f04_rsi_jump",
    "f05_bars_since_cross", "f06_buffer_over_range", "f07_minutes_since_open",
    "f08_ret_since_open_bps", "f09_dist_from_vwap_bps", "f10_session_range_over_adr",
    "f11_overnight_gap_bps", "f12_spy_align", "f13_qqq_align", "f14_spy_dia_corr_20",
    "f15a_spy_rvol20", "f15b_spy_rvol20_chg", "f16a_is_fomc_day", "f16b_days_to_fomc",
    "f17_day_of_week",
]


def design_matrix(df: pd.DataFrame) -> tuple[np.ndarray, list[str], np.ndarray]:
    """Numeric features + one-hot tod bucket (midday reference) and side."""
    cols, names = [], []
    for f in FEATURES:
        cols.append(df[f].to_numpy(float))
        names.append(f)
    for b in ("open", "close"):
        cols.append((df["tod_bucket"].to_numpy() == b).astype(float))
        names.append(f"tod_{b}")
    cols.append((df["side"].to_numpy() == "long").astype(float))
    names.append("side_long")
    X = np.column_stack(cols)
    # median-impute any residual NaN (warm-up edges), recorded in the results
    med = np.nanmedian(X, axis=0)
    nan_counts = np.isnan(X).sum(axis=0)
    X = np.where(np.isnan(X), med, X)
    return X, names, nan_counts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", type=Path, default=REPO / "data" / "DIA_5m.parquet")
    ap.add_argument("--is-start", default="2018-01-01")
    ap.add_argument("--is-end", default="2021-12-31")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--filter-sessions", action="store_true",
                    help="drop phantom bars stamped after a half-day's official close "
                         "(core.data.calendar.filter_to_sessions). Changes the trade set, "
                         "so the verification cell becomes report-only.")
    args = ap.parse_args()

    print("=== Phase 0 separability audit — rsi-5050-brain ===")
    print(f"IS window {args.is_start}..{args.is_end}   (OOS 2022-2024 and WF 2025+ NOT read)\n")

    df, counts, meta = rebuild_trades(args.bars, args.is_start, args.is_end,
                                      filter_sessions=args.filter_sessions)
    df = attach_cross_features(df, meta)

    # ---- data-verification cell (SPEC.md: halts the phase on mismatch) ----
    got = {"n": int(len(df)), "mean_bps": round(float(df["ret_trigger_bps"].mean()), 3),
           "eod": int((df["exit_type"] == "eod").sum()),
           "recross": int((df["exit_type"] == "recross").sum())}
    verify_ok = got == EXPECT
    print("--- data-verification cell ---"
          + ("  (REPORT-ONLY: --filter-sessions changes the trade set by design)"
             if args.filter_sessions else ""))
    for k in EXPECT:
        flag = "OK " if got[k] == EXPECT[k] else "MISMATCH"
        print(f"  {k:>9}: got {got[k]!s:>8}  expect {EXPECT[k]!s:>8}   [{flag}]")
    if not verify_ok and not args.filter_sessions:
        print("\nHALT: rebuilt log does not reproduce the inherited pregate. "
              "The mechanical layer was perturbed; nothing downstream is valid.")
        raise SystemExit(1)
    if verify_ok:
        print("  -> reproduces experiments/rsi-5050/2026-07-05-pregate exactly\n")
    else:
        print("  -> differs by design: phantom half-day bars removed\n")

    # chronological order first, so folds are time-blocked and every array aligns
    df = df.sort_values("signal_ts").reset_index(drop=True)
    y = (df["exit_type"] == "eod").astype(float).to_numpy()
    r = df["ret_trigger_bps"].to_numpy()
    X, names, nan_counts = design_matrix(df)
    base_rate = float(y.mean())

    # ---- chronological 5-fold CV (blocked, not random: adjacent sessions leak) ----
    folds = np.array_split(np.arange(len(df)), N_FOLDS)

    sel_mask = np.zeros(len(df), dtype=bool)
    fold_rows = []
    for k, te in enumerate(folds):
        tr = np.setdiff1d(np.arange(len(df)), te)
        mu, sd = X[tr].mean(0), X[tr].std(0)
        sd[sd == 0] = 1.0
        w = fit_logistic((X[tr] - mu) / sd, y[tr])
        p_tr = predict(w, (X[tr] - mu) / sd)
        thr = float(np.quantile(p_tr, 1.0 - RETENTION))   # threshold from TRAIN only
        p_te = predict(w, (X[te] - mu) / sd)
        take = p_te >= thr
        sel_mask[te] = take
        fold_rows.append({
            "fold": k + 1, "n_test": int(len(te)), "threshold": round(thr, 4),
            "n_selected": int(take.sum()),
            "retention": round(float(take.mean()), 3),
            "mean_bps_selected": round(float(r[te][take].mean()), 3) if take.any() else None,
            "eod_precision": round(float(y[te][take].mean()), 3) if take.any() else None,
        })

    sel_r, sel_y = r[sel_mask], y[sel_mask]
    cv = {
        "n_selected": int(sel_mask.sum()),
        "retention": round(float(sel_mask.mean()), 3),
        "mean_bps_selected": round(float(sel_r.mean()), 3),
        "median_bps_selected": round(float(np.median(sel_r)), 3),
        "t_stat": round(float(sel_r.mean() / (sel_r.std(ddof=1) / np.sqrt(len(sel_r)))), 2),
        "eod_precision": round(float(sel_y.mean()), 4),
        "eod_precision_base": round(base_rate, 4),
        "precision_lift": round(float(sel_y.mean() / base_rate), 2),
        "mean_bps_rejected": round(float(r[~sel_mask].mean()), 3),
        "mean_bps_all": round(float(r.mean()), 3),
    }

    # ---- univariate screen: point-biserial corr(feature, EOD), BH-corrected ----
    uni = []
    for j, nm in enumerate(names):
        x = X[:, j]
        if x.std() == 0:
            uni.append({"feature": nm, "corr": 0.0, "t": 0.0, "p": 1.0}); continue
        rho = float(np.corrcoef(x, y)[0, 1])
        t = rho * np.sqrt((len(y) - 2) / max(1e-12, 1 - rho ** 2))
        uni.append({"feature": nm, "corr": round(rho, 4), "t": round(float(t), 2),
                    "p": round(float(norm_sf(t)[0]), 5)})
    pvals = np.array([u["p"] for u in uni])
    passed = benjamini_hochberg(pvals, q=0.10)
    for u, ok in zip(uni, passed):
        u["bh_q10"] = bool(ok)
    uni.sort(key=lambda d: d["p"])

    # ---- locked gate ----
    gate_mean = cv["mean_bps_selected"] >= GATE_MEAN_BPS
    gate_n = cv["n_selected"] >= GATE_MIN_TRADES
    verdict = "PASS" if (gate_mean and gate_n) else "FAIL"

    result = {
        "phase": 0, "strategy": "rsi-5050-brain", "sample": "is",
        "is_window": [args.is_start, args.is_end],
        "spec": "strategies/rsi-5050-brain/SPEC.md (frozen 2026-08-30)",
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                                     capture_output=True, text=True).stdout.strip(),
        "data": meta,
        "verification_cell": {"expected": EXPECT, "got": got, "pass": verify_ok},
        "counts": counts,
        "deviations": [
            "f15 vix_level/vix_chg_1d UNAVAILABLE offline (no VIX vendor in repo, no "
            "yfinance dep). Substituted f15a/f15b = SPY 20-day realised volatility "
            "(annualised %, prior-day) from SPY_5m daily closes. Recorded BEFORE any "
            "result was computed. If Phase 0 passes, source true VIX for Phase 1.",
            "Folds are chronological blocks, not random: adjacent sessions share "
            "regime and random folds would leak. Implementation choice, fixed before "
            "the first run.",
            "p-values use a normal approximation (n=767; t/normal difference immaterial).",
        ],
        "params": {"retention": RETENTION, "n_folds": N_FOLDS, "ridge": RIDGE,
                   "gate_mean_bps": GATE_MEAN_BPS, "gate_min_trades": GATE_MIN_TRADES},
        "population": {
            "n": int(len(df)), "mean_bps_all": round(float(r.mean()), 3),
            "eod": {"n": int(y.sum()), "mean_bps": round(float(r[y == 1].mean()), 3)},
            "recross": {"n": int((1 - y).sum()), "mean_bps": round(float(r[y == 0].mean()), 3)},
        },
        "cv": cv, "folds": fold_rows, "univariate": uni,
        "nan_imputed": {nm: int(cnt) for nm, cnt in zip(names, nan_counts) if cnt},
        "gate": {"mean_bps": {"value": cv["mean_bps_selected"], "bar": GATE_MEAN_BPS,
                              "pass": bool(gate_mean)},
                 "n_selected": {"value": cv["n_selected"], "bar": GATE_MIN_TRADES,
                                "pass": bool(gate_n)}},
        "verdict": verdict,
    }

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    df["selected_oof"] = sel_mask
    df.to_csv(args.out / "trades_is.csv", index=False)

    # ---- report ----
    print("--- population (inherited, IS) ---")
    print(f"  all      n={len(df):>4}  mean {r.mean():+.3f} bps")
    print(f"  EOD      n={int(y.sum()):>4}  mean {r[y == 1].mean():+.3f} bps   "
          f"base rate {base_rate:.4f}")
    print(f"  recross  n={int((1 - y).sum()):>4}  mean {r[y == 0].mean():+.3f} bps\n")

    print("--- 5-fold chronological CV (out-of-fold) ---")
    print(f"  {'fold':>4} {'n_test':>7} {'sel':>5} {'ret%':>6} {'mean bps':>9} {'EOD prec':>9}")
    for f in fold_rows:
        print(f"  {f['fold']:>4} {f['n_test']:>7} {f['n_selected']:>5} "
              f"{f['retention']:>6.2f} {str(f['mean_bps_selected']):>9} "
              f"{str(f['eod_precision']):>9}")
    print(f"\n  pooled selected : n={cv['n_selected']}  mean {cv['mean_bps_selected']:+.3f} bps"
          f"  (t={cv['t_stat']})")
    print(f"  pooled rejected : mean {cv['mean_bps_rejected']:+.3f} bps")
    print(f"  EOD precision   : {cv['eod_precision']:.4f} vs base {base_rate:.4f}"
          f"  ({cv['precision_lift']}x lift)")
    print(f"  break-even p    : 0.2513  ->  needs {0.2513 / base_rate:.2f}x\n")

    print("--- univariate screen (corr with EOD, BH q=0.10) ---")
    print(f"  {'feature':<28} {'corr':>7} {'t':>7} {'p':>9}  BH")
    for u in uni:
        print(f"  {u['feature']:<28} {u['corr']:>7.4f} {u['t']:>7.2f} {u['p']:>9.5f}  "
              f"{'*' if u['bh_q10'] else ''}")

    print(f"\n--- LOCKED GATE ---")
    print(f"  mean gross of selected >= {GATE_MEAN_BPS} bps : "
          f"{cv['mean_bps_selected']:+.3f}  [{'PASS' if gate_mean else 'FAIL'}]")
    print(f"  selected trades        >= {GATE_MIN_TRADES}     : "
          f"{cv['n_selected']:>6}  [{'PASS' if gate_n else 'FAIL'}]")
    print(f"\n  VERDICT: {verdict}")
    if verdict == "FAIL":
        print("  -> SPEC.md Phase 0: reject at spec validation. No LLM arm, no feature\n"
              "     additions, no threshold relaxation, no tree models.")
    print(f"\n  written -> {args.out}/results.json")


if __name__ == "__main__":
    main()
