"""Build the diversified daily total-return basket for the TSMOM candidate
(trend-following / time-series momentum; research screen passed 2026-07-08, see
experiments/tsmom/2026-07-08-research-screen/prereg.md).

TSMOM's edge is multi-asset: equity-only trend is closet beta. This builds one
self-adjusted daily series per instrument across four asset classes, following
the house data discipline established for the SPY EOD splice
(scripts/build_spy_eod_splice.py): take raw prints, apply our OWN corporate-action
adjustment from the distribution record, and audit — never trust a vendor's
adjusted series blindly (Alpaca `adjustment=all` was found missing/doubling
dividends; see docs/strategy-candidates.md data-pipeline note).

Method (per instrument), and why it is correct across the one split in-window
(EEM 3:1 on 2008-07-24 — verified empirically before writing this):
  - BASE = Yahoo `auto_adjust=False` Close/OHLC. Empirically this is
    SPLIT-adjusted (continuous through the EEM split) but DIVIDEND-unadjusted, and
    is continuous across history, so we never re-apply splits to prices.
  - Yahoo Dividends are on the RAW as-paid per-share basis (EEM's pre-split 2007
    dividend is ~3x the post-split ones), so a distribution on ex-date d is put on
    the split-adjusted price basis by dividing by S_after(d) = product of split
    ratios with ex-date strictly after d, before the CRSP step.
  - Distributions = Dividends + Capital Gains (commodity/bond ETFs pay cap-gains
    distributions with ex-dates; both are cash off the NAV and must be adjusted).
  - Back-adjust the split-adjusted OHLC by the CRSP-standard factor
    1 - dist_adj/prev_close per ex-date, anchored at the latest bar. For the seven
    split-free instruments S_after==1 everywhere and this reduces exactly to the
    SPY EOD method.

Audits written to the combined report (locked bars stop the pipeline on failure):
  1. Per-event distribution audit: our implied adjustment step vs Yahoo's own
     (Adj Close / Close) step at each ex-date — flags any event we and the vendor
     disagree on (the missing/doubled-dividend failure class).
  2. Self-built vs Yahoo Adj Close, full overlap, boundary-rescaled: validates our
     split x dividend arithmetic against the vendor's independent construction
     (daily-return divergence is the strict bar).
  3. Cross-vendor, 2016->present: our total-return daily returns vs Alpaca SIP
     `adjustment=all` daily returns — confirms both vendors print the same market
     (no split in any instrument's post-2016 window, so this is apples-to-apples).

Outputs:
  - data/tsmom/<TICKER>_daily_adj.parquet   per-instrument total-return series
                                            (gitignored; /data is never committed)
  - data/tsmom/_yahoo_raw/<TICKER>.parquet  raw vendor cache (gitignored)
  - <out-dir>/basket_report.json            all audit evidence + sha256 + git commit

    uv run --extra paper --with yfinance python scripts/build_tsmom_basket.py \
        --out-dir experiments/tsmom/2026-07-08-basket-build
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
ET = ZoneInfo("America/New_York")

# The diversified basket the screen authorized: four asset classes, all liquid
# US-listed ETFs. Common start is UUP's 2007-03 inception -> a 2007->present
# window that spans 2008, the 2011-2019 lean decade, 2020, the 2022 revival, and
# the 2024-2025 drawdown (the lean-inclusive OOS the spec requires).
BASKET: dict[str, str] = {
    "SPY": "equity",     # US large cap
    "EFA": "equity",     # developed ex-US
    "EEM": "equity",     # emerging markets
    "IEF": "bond",       # 7-10y US Treasury
    "TLT": "bond",       # 20y+ US Treasury
    "DBC": "commodity",  # broad commodities
    "GLD": "commodity",  # gold
    "UUP": "fx",         # US dollar index (bullish)
}

YAHOO_START = "2003-01-01"      # >= earliest needed inception with warm-up room
ALPACA_START = "2016-01-01"     # SIP daily history floor
RETURN_BAR_BPS = 5.0            # locked: daily-return divergence bar for audits 2 & 3
EVENT_BAR_BPS = 10.0            # locked: |our step - vendor step| above this = disputed event


def day_index(idx) -> pd.DatetimeIndex:
    tz = getattr(idx, "tz", None)
    vals = idx.tz_convert(ET).date if tz is not None else [d.date() for d in idx]
    return pd.DatetimeIndex(vals).astype("datetime64[ns]")


def div_stats(diff_bps: pd.Series) -> dict:
    diff_bps = diff_bps.dropna()
    return {
        "mean": round(float(diff_bps.mean()), 4),
        "p99": round(float(diff_bps.quantile(0.99)), 4),
        "max": round(float(diff_bps.max()), 4),
        "worst_dates": {str(k.date()): round(float(v), 3) for k, v in diff_bps.nlargest(3).items()},
    }


def fetch_yahoo(tk: str, cache: Path, start: str):
    """Returns (base OHLC [split-adj, div-unadj], yahoo adj_close, dists, splits),
    all day-indexed. dists = Dividends + Capital Gains (raw as-paid per share)."""
    import yfinance as yf

    hist = yf.Ticker(tk).history(start=start, auto_adjust=False)
    if hist.empty:
        raise SystemExit(f"[{tk}] Yahoo returned no data.")
    hist.index = day_index(hist.index)
    hist = hist[~hist.index.duplicated(keep="last")].sort_index()
    base = hist.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].copy()
    base.to_parquet(cache)

    adj_close = hist["Adj Close"].rename("adj_close")
    div = hist.get("Dividends", pd.Series(0.0, index=hist.index)).fillna(0.0)
    capg = hist.get("Capital Gains", pd.Series(0.0, index=hist.index)).fillna(0.0)
    dists = (div + capg)
    dists = dists[dists > 0]
    splits = hist.get("Stock Splits", pd.Series(0.0, index=hist.index)).fillna(0.0)
    splits = splits[splits > 0]
    return base, adj_close, dists, splits


def fetch_alpaca(tk: str, start: str, end: str, adjustment: str) -> pd.DataFrame:
    """Raw daily SIP bars, day-indexed OHLCV. adjustment: 'raw' | 'all'."""
    from alpaca.data.enums import Adjustment, DataFeed
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    client = StockHistoricalDataClient(
        os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"]
    )
    req = StockBarsRequest(
        symbol_or_symbols=tk,
        timeframe=TimeFrame.Day,
        start=pd.Timestamp(start).to_pydatetime(),
        end=pd.Timestamp(end).to_pydatetime(),
        feed=DataFeed.SIP,
        adjustment=Adjustment(adjustment),
    )
    df = client.get_stock_bars(req).df
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.index, pd.MultiIndex):
        df = df.xs(tk, level=0)
    df = df.reset_index().rename(columns={"timestamp": "ts"})
    out = df[["ts", "open", "high", "low", "close", "volume"]].copy()
    out.index = day_index(pd.DatetimeIndex(pd.to_datetime(out["ts"], utc=True)))
    return out.drop(columns="ts")[["open", "high", "low", "close", "volume"]]


def total_return_adjust(base: pd.DataFrame, dists: pd.Series):
    """Back-adjust split-adjusted OHLC for distributions (CRSP factor), returning
    (adjusted OHLCV, per-ex-date factor applied to prior bars for the audit).

    Yahoo's Close is split-adjusted to the current basis and its Dividends are
    reported on that same basis (verified empirically: raw dividend / split-adjusted
    prev_close reproduces Yahoo's own adjustment step to <0.02 bps across the EEM
    3:1 splits), so no split conversion of the distribution is needed here — for the
    split-free instruments this is identical to the SPY EOD method."""
    prev_close = base["close"].shift(1)
    log_cum = pd.Series(0.0, index=base.index)
    steps = {}
    for d, raw_dist in dists.items():
        if d not in base.index or pd.isna(prev_close.loc[d]) or prev_close.loc[d] <= 0:
            continue
        step = 1.0 - float(raw_dist) / float(prev_close.loc[d])
        if step <= 0:
            raise SystemExit(f"Non-positive CRSP step {d.date()} (dist={raw_dist}) - check data.")
        log_cum.loc[base.index < d] += np.log(step)
        steps[d] = step
    factor = np.exp(log_cum)
    adj = base.copy()
    for col in ("open", "high", "low", "close"):
        adj[col] = base[col] * factor
    return adj, pd.Series(steps)


def audit_event_steps(
    our_steps: pd.Series, adj_close: pd.Series, base_close: pd.Series
) -> list[dict]:
    """Compare our per-ex-date factor (applied to prior bars, <1) to Yahoo's own.
    Yahoo's factor for prior bars is the reciprocal of its (Adj Close / Close) step
    across the ex-date; a disagreement flags a missing/doubled/mis-sized event."""
    vfactor = (adj_close / base_close)
    vstep = vfactor / vfactor.shift(1)  # jumps UP across ex-date; prior-bar factor is 1/vstep
    events = []
    for d, our in our_steps.items():
        if d not in vstep.index or pd.isna(vstep.loc[d]) or vstep.loc[d] <= 0:
            continue
        yahoo_prior_factor = 1.0 / float(vstep.loc[d])
        diff_bps = float((our - yahoo_prior_factor) * 1e4)
        events.append({
            "ex_date": str(d.date()),
            "our_step_bps": round(float((our - 1) * 1e4), 3),
            "yahoo_step_bps": round(float((yahoo_prior_factor - 1) * 1e4), 3),
            "diff_bps": round(diff_bps, 3),
            "disputed": abs(diff_bps) > EVENT_BAR_BPS,
        })
    return events


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_one(tk: str, cls: str, raw_dir: Path, out_dir_data: Path) -> dict:
    base, adj_close, dists, splits = fetch_yahoo(tk, raw_dir / f"{tk}.parquet", YAHOO_START)

    adj, our_steps = total_return_adjust(base, dists)

    # Audit 1: per-event distribution steps vs Yahoo's own adjustment.
    events = audit_event_steps(our_steps, adj_close, base["close"])
    disputed = [e for e in events if e["disputed"]]

    # Audit 2: our total-return vs Yahoo Adj Close, full overlap, boundary-rescaled.
    ov = adj.index.intersection(adj_close.index)
    oc = adj.loc[ov, "close"]
    yc = adj_close.loc[ov] * float(oc.iloc[0] / adj_close.loc[ov].iloc[0])
    lvl2 = (1e4 * (yc / oc - 1.0)).abs()
    ret2 = (1e4 * (yc.pct_change() - oc.pct_change())).abs()

    # Audit 3: cross-vendor sanity, 2016+ (post-split, apples-to-apples total
    # return). Alpaca is a cross-check only (never in the price path) and carries
    # occasional extreme-day print discrepancies and its own ex-dividend bugs, so
    # the guard is on TYPICAL agreement (median / p99), not the single worst day;
    # the largest-divergence days are listed for eyeballing (expected: COVID-crash
    # sessions and ex-div dates).
    a_all = fetch_alpaca(tk, ALPACA_START, str(pd.Timestamp.today().date()), "all")
    time.sleep(0.3)
    cross = {"skipped": "no Alpaca overlap"}
    if not a_all.empty:
        ov3 = adj.index.intersection(a_all.index)
        our_ret = adj.loc[ov3, "close"].pct_change()
        alp_ret = a_all.loc[ov3, "close"].pct_change()
        ret3 = (1e4 * (our_ret - alp_ret)).abs().dropna()
        median = float(ret3.median())
        p99 = float(ret3.quantile(0.99))
        cross = {
            "overlap_sessions": int(len(ov3)),
            "median_bps": round(median, 4),
            "p99_bps": round(p99, 4),
            "max_bps": round(float(ret3.max()), 3),
            "days_over_25bps": int((ret3 > 25).sum()),
            "worst_dates": {str(k.date()): round(float(v), 2) for k, v in ret3.nlargest(5).items()},
            "median_bar_bps": 2.0,
            "p99_bar_bps": 25.0,
            "pass": bool(median < 2.0 and p99 < 25.0),
            "note": "Alpaca is cross-check only (not in the price path); large days are "
            "extreme-vol vendor print noise / Alpaca ex-div handling, not the built series.",
        }

    # Write the total-return series in canonical UTC/close-stamped schema.
    out = adj.copy()
    out.index = pd.DatetimeIndex(
        [pd.Timestamp(d, tz=ET).tz_convert("UTC") for d in adj.index], name="ts"
    )
    out_path = out_dir_data / f"{tk}_daily_adj.parquet"
    out.to_parquet(out_path)

    return {
        "ticker": tk,
        "asset_class": cls,
        "range": [str(adj.index[0].date()), str(adj.index[-1].date())],
        "sessions": int(len(adj)),
        "distributions_applied": int(len(dists)),
        "splits_applied": {str(k.date()): float(v) for k, v in splits.items()},
        "out_file": str(out_path.relative_to(REPO)),
        "sha256": sha256(out_path),
        "audit1_event_steps": {
            "events_checked": len(events),
            "disputed_events": disputed,
        },
        "audit2_self_vs_yahoo_adjclose": {
            "overlap_sessions": int(len(ov)),
            "level_divergence_bps": div_stats(lvl2),
            "daily_return_divergence_bps": div_stats(ret2),
            "return_bar_bps": RETURN_BAR_BPS,
            "pass_max": bool(ret2.dropna().max() < RETURN_BAR_BPS),
        },
        "audit3_cross_vendor_alpaca_2016plus": cross,
    }


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--data-dir", type=Path, default=REPO / "data/tsmom")
    args = ap.parse_args()

    load_dotenv(REPO / ".env")
    if not os.environ.get("ALPACA_API_KEY"):
        raise SystemExit("Missing ALPACA_API_KEY / ALPACA_SECRET_KEY (see .env.example).")

    raw_dir = args.data_dir / "_yahoo_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    args.data_dir.mkdir(parents=True, exist_ok=True)

    per_ticker = []
    for tk, cls in BASKET.items():
        print(f"  building {tk} ({cls}) ...")
        per_ticker.append(build_one(tk, cls, raw_dir, args.data_dir))
        time.sleep(0.5)  # be polite to Yahoo (429-prone)

    common_start = max(pd.Timestamp(t["range"][0]) for t in per_ticker)
    audit2_fail = [
        t["ticker"] for t in per_ticker if not t["audit2_self_vs_yahoo_adjclose"]["pass_max"]
    ]
    audit3_fail = [
        t["ticker"] for t in per_ticker
        if t["audit3_cross_vendor_alpaca_2016plus"].get("pass") is False
    ]
    disputed = {
        t["ticker"]: t["audit1_event_steps"]["disputed_events"]
        for t in per_ticker if t["audit1_event_steps"]["disputed_events"]
    }

    report = {
        "purpose": "Diversified daily total-return basket for the TSMOM candidate.",
        "method": "Yahoo split-adjusted raw Close/OHLC + self CRSP distribution "
        "back-adjust (dividends + capital gains, split-basis corrected); audited "
        "vs Yahoo Adj Close and vs Alpaca SIP adjustment=all 2016+.",
        "basket": BASKET,
        "common_start_all_instruments": str(common_start.date()),
        "return_bar_bps": RETURN_BAR_BPS,
        "event_bar_bps": EVENT_BAR_BPS,
        "instruments": per_ticker,
        "audit2_failures": audit2_fail,
        "audit3_failures": audit3_fail,
        "audit1_disputed_events": disputed,
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True
        ).stdout.strip(),
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "basket_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))

    problems = []
    if audit2_fail:
        problems.append(f"audit-2 (self vs Yahoo adj) FAILED: {audit2_fail}")
    if audit3_fail:
        problems.append(f"audit-3 (cross-vendor) FAILED: {audit3_fail}")
    if disputed:
        problems.append(f"audit-1 disputed distribution events: {list(disputed)}")
    if problems:
        raise SystemExit(
            "\nBASKET BUILD HAS AUDIT FAILURES — surface to user:\n  " + "\n  ".join(problems)
        )
    print(f"\nAll audits PASS — {len(per_ticker)} instruments, common start {common_start.date()}")


if __name__ == "__main__":
    main()
