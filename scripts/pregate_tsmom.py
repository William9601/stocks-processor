"""Pre-scoring diagnostic for tsmom (SPEC.md, Success criteria + Sign-offs, frozen
2026-07-08 before this ran).

Simulates the frozen long/short 12-month time-series-momentum book and its
pre-registered benchmark — the STATIC always-long version of the same basket — OUTSIDE
the backtest engine and on the IS WINDOW ONLY, then scores the diversifier edge:

  TSMOM(IS)  = net annualized Sharpe of the timed long/short book
  STATIC(IS) = net annualized Sharpe of the same basket held always-long (signal = +1),
               identical inverse-vol sizing, identical portfolio vol target
  EDGE(IS)   = TSMOM(IS) - STATIC(IS)          (Sharpe units; the diversifier edge)

Binding gate (frozen in SPEC.md before this ran) — REJECT at spec-validation if:
  * EDGE(IS) <= 0            (the timing does not beat holding the basket -> the return
                             is diversification beta, not trend alpha), OR
  * TSMOM(IS) Sharpe < 0.3   (even in-sample the book fails a minimal standalone bar), OR
  * TSMOM worst-SPY-quartile return < STATIC's  (the timing removes rather than adds the
                             crisis convexity that is the entire thesis).

**OOS (2017-01 -> 2024-12) and WF (2025->) are NOT read here.** Bars are hard-sliced to
<= 2016-12-31 before any computation so nothing post-IS can leak into this number.

Everything is pre-registered in SPEC.md and never swept: 12-month (252d) sign-of-excess
signal, 60-day inverse-vol sizing, 10% portfolio vol target, 3x gross cap, monthly MOC
rebalance, 4.0 bps round-trip cost (2.0/side) + 50 bps/yr short borrow.

    uv run python scripts/pregate_tsmom.py --out experiments/tsmom/2026-07-08-pregate
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]

# --- frozen spec parameters (SPEC.md 2026-07-08; never swept) ---
BASKET = ["SPY", "EFA", "EEM", "IEF", "TLT", "DBC", "GLD", "UUP"]
IS_END = "2016-12-31"          # OOS starts 2017-01-01 and is NOT read here
SCORE_START = "2008-04-01"     # first month fully past the 252d+60d warm-up on 2007-03 data
LOOKBACK = 252                 # 12-month signal
VOL_WINDOW = 60                # inverse-vol + portfolio-vol estimator
SIGMA_TGT_PORT = 0.10          # 10% annualized portfolio vol target
GROSS_CAP = 3.0                # max gross leverage
COST_PER_SIDE_BPS = 2.0        # 1.5 half-spread + 0.5 slippage, charged on |turnover|
BORROW_ANNUAL_BPS = 50.0       # short borrow on average short notional
ANN = 252


def file_sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def sharpe(daily_excess: np.ndarray) -> float:
    x = np.asarray(daily_excess, float)
    x = x[~np.isnan(x)]
    sd = x.std(ddof=1)
    return float(x.mean() / sd * np.sqrt(ANN)) if sd > 0 else 0.0


def load_prices(data_dir: Path) -> pd.DataFrame:
    cols = {}
    for tk in BASKET:
        s = pd.read_parquet(data_dir / f"{tk}_daily_adj.parquet")["close"]
        s.index = pd.DatetimeIndex(s.index.tz_convert("America/New_York").date)
        cols[tk] = s[~s.index.duplicated(keep="last")].sort_index()
    px = pd.DataFrame(cols)
    # HARD IS SLICE: drop everything after IS_END before any computation.
    return px[px.index <= pd.Timestamp(IS_END)].dropna(how="any")


def load_rf_daily(path: Path, index: pd.DatetimeIndex) -> pd.Series:
    rf = pd.read_csv(path, parse_dates=["date"]).set_index("date")["irx_annual_pct"]
    rf.index = pd.DatetimeIndex(rf.index.date)
    rf = rf[~rf.index.duplicated(keep="last")].sort_index().reindex(index).ffill().fillna(0.0)
    return rf / 100.0 / ANN  # annual percent -> daily fraction


def simulate(px: pd.DataFrame, rf_daily: pd.Series, long_only: bool) -> pd.DataFrame:
    """Monthly-rebalanced, inverse-vol, portfolio-vol-targeted book. Causal: signals and
    vols use completed bars up to a rebalance date; positions apply from the NEXT day.
    Returns a daily frame with net/gross excess returns, turnover, borrow, exposure."""
    r = px.pct_change()                          # daily total returns
    re = r.sub(rf_daily, axis=0)                 # daily excess returns
    vol = r.rolling(VOL_WINDOW).std() * np.sqrt(ANN)
    logexc = np.log1p(re)
    cum252 = np.expm1(logexc.rolling(LOOKBACK).sum())   # trailing 252d excess return
    sig = pd.DataFrame(1.0, index=px.index, columns=px.columns)
    if not long_only:
        sig = np.sign(cum252).replace(0.0, 0.0)         # +1 / -1 / 0 (measure-zero)

    dates = px.index
    month_id = pd.Series(dates.year * 12 + dates.month, index=dates)
    is_rebal = month_id != month_id.shift(-1)           # last trading day of each month

    # --- Pass 1: base weights (s_i / vol_i), stepped monthly, applied from t+1 ---
    base_target = sig.div(vol).replace([np.inf, -np.inf], np.nan)
    base_w = pd.DataFrame(np.nan, index=dates, columns=px.columns)
    last = None
    for j in range(len(dates)):
        if last is not None and is_rebal.iloc[j - 1]:   # yesterday was a rebalance -> apply
            row = base_target.iloc[j - 1]
            if row.notna().all():
                last = row
        base_w.iloc[j] = last if last is not None else np.nan
        if last is None and is_rebal.iloc[j] and base_target.iloc[j].notna().all():
            last = base_target.iloc[j]                  # seed the first live weights
    unscaled = (base_w * re).sum(axis=1, skipna=False)  # unscaled daily book excess return

    # --- Pass 2: monthly portfolio-vol scale k (trailing 60d realized vol of unscaled) ---
    book_vol = unscaled.rolling(VOL_WINDOW).std() * np.sqrt(ANN)
    rows = []
    w_prev = pd.Series(0.0, index=px.columns)
    k_live = np.nan
    for j, d in enumerate(dates):
        if j > 0 and is_rebal.iloc[j - 1]:
            bv = book_vol.iloc[j - 1]
            if np.isfinite(bv) and bv > 0:
                k_live = SIGMA_TGT_PORT / bv
        w = (k_live * base_w.iloc[j]) if np.isfinite(k_live) \
            else pd.Series(np.nan, index=px.columns)
        gross = float(w.abs().sum()) if w.notna().all() else np.nan
        if np.isfinite(gross) and gross > GROSS_CAP:     # gross leverage cap
            w = w * (GROSS_CAP / gross)
            gross = GROSS_CAP
        rebal_today = bool(j > 0 and is_rebal.iloc[j - 1])
        turnover = float((w - w_prev).abs().sum()) if (w.notna().all() and rebal_today) else 0.0
        cost = turnover * COST_PER_SIDE_BPS / 1e4
        short_notional = float((-w).clip(lower=0).sum()) if w.notna().all() else 0.0
        borrow = short_notional * (BORROW_ANNUAL_BPS / 1e4 / ANN)
        gross_ret = float((w * re.iloc[j]).sum()) if w.notna().all() else np.nan
        rows.append({
            "date": d, "gross_ret": gross_ret, "net_ret": gross_ret - cost - borrow,
            "turnover": turnover, "cost": cost, "borrow": borrow, "gross_exp": gross,
            "net_exp": float(w.sum()) if w.notna().all() else np.nan,
        })
        if w.notna().all():
            w_prev = w
    out = pd.DataFrame(rows).set_index("date")
    return out


def monthly(returns: pd.Series) -> pd.Series:
    return (1.0 + returns).groupby([returns.index.year, returns.index.month]).prod() - 1.0


def worst_spy_quartile(strat_m: pd.Series, spy_m: pd.Series) -> float:
    common = strat_m.index.intersection(spy_m.index)
    s, b = strat_m.loc[common], spy_m.loc[common]
    thresh = b.quantile(0.25)
    worst = s[b <= thresh]
    return float(worst.mean()) if len(worst) else float("nan")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=REPO / "data/tsmom")
    ap.add_argument("--rf", type=Path, default=REPO / "strategies/tsmom/rf_13w.csv")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    px = load_prices(args.data_dir)
    rf_daily = load_rf_daily(args.rf, px.index)

    tsmom = simulate(px, rf_daily, long_only=False)
    static = simulate(px, rf_daily, long_only=True)

    score = (px.index >= pd.Timestamp(SCORE_START)) & (px.index <= pd.Timestamp(IS_END))
    score_dates = px.index[score]
    ts_net = tsmom.loc[score_dates, "net_ret"]
    st_net = static.loc[score_dates, "net_ret"]
    ts_gross = tsmom.loc[score_dates, "gross_ret"]

    spy_daily_excess = (px["SPY"].pct_change() - rf_daily).loc[score_dates]
    spy_m = monthly(px["SPY"].pct_change().loc[score_dates])
    ts_m, st_m = monthly(ts_net), monthly(st_net)

    ts_sharpe = sharpe(ts_net.to_numpy())
    st_sharpe = sharpe(st_net.to_numpy())
    edge = ts_sharpe - st_sharpe
    ts_wq = worst_spy_quartile(ts_m, spy_m)
    st_wq = worst_spy_quartile(st_m, spy_m)

    # --- gate (frozen SPEC rule) ---
    reasons = []
    if edge <= 0:
        reasons.append(f"EDGE(IS)={edge:.3f} <= 0 (timing does not beat holding the basket)")
    if ts_sharpe < 0.3:
        reasons.append(f"TSMOM(IS) Sharpe={ts_sharpe:.3f} < 0.30 standalone bar")
    if ts_wq < st_wq:
        reasons.append(f"TSMOM worst-SPY-quartile={ts_wq*100:.2f}% < STATIC {st_wq*100:.2f}% "
                       "(timing removes crisis convexity)")
    if reasons:
        verdict = ("REJECT at spec-validation (binding rule frozen in SPEC.md before this "
                   "ran): " + "; ".join(reasons) + ". No tuning; OOS/WF stay unread; "
                   "post-mortem in the SPEC.")
    else:
        verdict = ("PASS pre-scoring gate — the 12-month timing beats the static basket "
                   "in-sample and preserves crisis convexity; proceed to implementation, "
                   "engine IS cross-check, then the ONE OOS look + 1.5x-cost companion.")

    ann_turnover = float(tsmom.loc[score_dates, "turnover"].sum()
                         / (len(score_dates) / ANN))
    out = {
        "strategy": "tsmom",
        "gate_scope": f"IS ONLY ({SCORE_START} -> {IS_END}). OOS (2017-01->2024-12)/WF NOT read.",
        "data_dir": str(args.data_dir),
        "bars_sha256_16": {
            tk: file_sha(args.data_dir / f"{tk}_daily_adj.parquet") for tk in BASKET
        },
        "rf_file": str(args.rf), "rf_sha256_16": file_sha(args.rf),
        "score_range": [str(score_dates[0].date()), str(score_dates[-1].date())],
        "n_days": int(len(score_dates)), "n_months": int(len(ts_m)),
        "params": {
            "lookback_days": LOOKBACK, "vol_window": VOL_WINDOW,
            "sigma_target_port": SIGMA_TGT_PORT, "gross_cap": GROSS_CAP,
            "cost_per_side_bps": COST_PER_SIDE_BPS, "borrow_annual_bps": BORROW_ANNUAL_BPS,
        },
        "gate_rule": "REJECT if EDGE(IS)<=0 OR TSMOM Sharpe<0.30 OR TSMOM worst-quartile<STATIC",
        "TSMOM_IS_net_sharpe": round(ts_sharpe, 3),
        "STATIC_IS_net_sharpe": round(st_sharpe, 3),
        "EDGE_IS_sharpe": round(edge, 3),
        "TSMOM_worst_spy_quartile_monthly_pct": round(ts_wq * 100, 3),
        "STATIC_worst_spy_quartile_monthly_pct": round(st_wq * 100, 3),
        "verdict": verdict,
        "diagnostics_NOT_GATES": {
            "TSMOM_IS_gross_sharpe": round(sharpe(ts_gross.to_numpy()), 3),
            "TSMOM_ann_return_pct": round(float(ts_net.mean() * ANN * 100), 3),
            "TSMOM_ann_vol_pct": round(float(ts_net.std(ddof=1) * np.sqrt(ANN) * 100), 3),
            "STATIC_ann_return_pct": round(float(st_net.mean() * ANN * 100), 3),
            "TSMOM_corr_to_SPY_monthly": round(float(ts_m.corr(spy_m)), 3),
            "STATIC_corr_to_SPY_monthly": round(float(st_m.corr(spy_m)), 3),
            "TSMOM_annual_turnover_x": round(ann_turnover, 2),
            "TSMOM_avg_gross_exposure": round(float(tsmom.loc[score_dates, "gross_exp"].mean()), 2),
            "TSMOM_avg_net_exposure": round(float(tsmom.loc[score_dates, "net_exp"].mean()), 2),
            "TSMOM_cost_drag_ann_bps": round(float(tsmom.loc[score_dates, "cost"].sum()
                                             / (len(score_dates) / ANN) * 1e4), 1),
            "TSMOM_borrow_drag_ann_bps": round(float(tsmom.loc[score_dates, "borrow"].sum()
                                               / (len(score_dates) / ANN) * 1e4), 1),
            "TSMOM_max_drawdown_pct": round(float(
                ((1 + ts_net).cumprod() / (1 + ts_net).cumprod().cummax() - 1).min() * 100), 2),
            "per_year_net_return_pct": {
                int(y): round(float((1 + g).prod() - 1) * 100, 2)
                for (y), g in ts_net.groupby(ts_net.index.year)
            },
        },
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True
        ).stdout.strip(),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "pregate_results.json").write_text(json.dumps(out, indent=2) + "\n")
    pd.DataFrame({"tsmom_net": ts_net, "static_net": st_net,
                  "spy_excess": spy_daily_excess}).to_csv(args.out / "pregate_daily_is.csv")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
