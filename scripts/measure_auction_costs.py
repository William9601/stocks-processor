"""Measure the real-cost inputs for MOC/MOO auction fills in SPY/QQQ.

Method is pre-registered in
experiments/execution-cost-study/2026-07-03-2319-spy-qqq-auction/notes.md — read that
first. Two measurements:

1. Fill-reference error: |5-min bar reference price - official auction print| in bps,
   close site (last 16:00-stamped bar's close vs daily close) and open site (first
   09:35-stamped bar's open vs daily open), per symbol, pooled 2018-2026.
2. NBBO half-spread in the seconds around the auctions (fallback bound if an order
   missed the auction cutoff), on a stratified sample of days.

    uv run --extra paper python scripts/measure_auction_costs.py \
        --out experiments/execution-cost-study/2026-07-03-2319-spy-qqq-auction/metrics.json
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import time
from pathlib import Path

import numpy as np
import pandas as pd

from core.strategy import ET

REPO = Path(__file__).resolve().parents[1]

# (5-min file, daily file) pairs; WF files extend coverage to 2026-07.
PAIRS = {
    "SPY": [
        ("data/SPY_5m_adj.parquet", "data/SPY_daily_adj.parquet"),
        ("data/SPY_5m_adj_wf.parquet", "data/SPY_daily_adj_wf.parquet"),
    ],
    "QQQ": [
        ("data/QQQ_5m_adj.parquet", "data/QQQ_daily_adj.parquet"),
        ("data/QQQ_5m_adj_wf.parquet", "data/QQQ_daily_adj_wf.parquet"),
    ],
}

OPEN_STAMP = time(9, 35)  # close-stamped first RTH 5-min bar (covers 09:30-09:35)
CLOSE_STAMP = time(16, 0)
QUOTE_WINDOWS = [("09:30:00", "09:30:10"), ("15:59:50", "16:00:00")]
SPREAD_SAMPLE_DAYS = 12  # per symbol, stratified across the full span


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def session_refs(five_path: Path) -> pd.DataFrame:
    """Per ET session: first-bar open/time and last-bar close/time."""
    bars = pd.read_parquet(five_path).sort_index()
    et = bars.index.tz_convert(ET)
    g = pd.DataFrame(
        {"open": bars["open"].values, "close": bars["close"].values, "t": et.time},
        index=pd.Index(et.date, name="d"),
    ).groupby(level="d")
    return pd.DataFrame(
        {
            "first_open": g["open"].first(),
            "first_t": g["t"].first(),
            "last_close": g["close"].last(),
            "last_t": g["t"].last(),
        }
    )


def daily_refs(daily_path: Path) -> pd.DataFrame:
    d = pd.read_parquet(daily_path).sort_index()
    d.index = pd.Index(pd.DatetimeIndex(d.index).tz_convert(ET).date, name="d")
    return d[["open", "close"]]


def fill_reference_errors(symbol: str) -> dict:
    frames = []
    for five, daily in PAIRS[symbol]:
        refs = session_refs(REPO / five).join(daily_refs(REPO / daily), how="inner")
        frames.append(refs)
    refs = pd.concat(frames)
    refs = refs[~refs.index.duplicated(keep="last")].sort_index()

    open_ok = refs["first_t"] == OPEN_STAMP
    close_ok = refs["last_t"] == CLOSE_STAMP  # drops half-days (13:00 close)
    o = refs.loc[open_ok]
    c = refs.loc[close_ok]
    open_err = 1e4 * (o["first_open"] - o["open"]) / o["open"]
    close_err = 1e4 * (c["last_close"] - c["close"]) / c["close"]

    def stats(err: pd.Series) -> dict:
        a = err.abs()
        return {
            "n": int(err.size),
            "signed_mean_bps": round(float(err.mean()), 4),
            "abs_p50_bps": round(float(a.quantile(0.50)), 4),
            "abs_p75_bps": round(float(a.quantile(0.75)), 4),
            "abs_p90_bps": round(float(a.quantile(0.90)), 4),
            "abs_p95_bps": round(float(a.quantile(0.95)), 4),
            "abs_max_bps": round(float(a.max()), 4),
        }

    return {
        "sessions": int(len(refs)),
        "dropped_open_site": int((~open_ok).sum()),
        "dropped_close_site": int((~close_ok).sum()),
        "date_range": [str(refs.index.min()), str(refs.index.max())],
        "open_site": stats(open_err),
        "close_site": stats(close_err),
    }


def sample_half_spreads(symbol: str) -> dict:
    """Median NBBO half-spread (bps) near the open/close auctions, sampled days."""
    from alpaca.data.enums import DataFeed
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockQuotesRequest

    key, secret = os.environ.get("ALPACA_API_KEY"), os.environ.get("ALPACA_SECRET_KEY")
    if not key or not secret:
        raise SystemExit("Missing ALPACA_API_KEY / ALPACA_SECRET_KEY (see .env.example).")
    client = StockHistoricalDataClient(key, secret)

    sessions = pd.concat([session_refs(REPO / five) for five, _ in PAIRS[symbol]])
    days = sessions.index.unique().sort_values()
    picks = [days[i] for i in np.linspace(0, len(days) - 1, SPREAD_SAMPLE_DAYS, dtype=int)]

    out = {"09:30": [], "15:59-16:00": [], "sample_days": [str(d) for d in picks], "failed": []}
    for d in picks:
        for (t0, t1), label in zip(QUOTE_WINDOWS, ["09:30", "15:59-16:00"], strict=True):
            try:
                req = StockQuotesRequest(
                    symbol_or_symbols=symbol,
                    start=pd.Timestamp(f"{d} {t0}", tz=ET).tz_convert("UTC").to_pydatetime(),
                    end=pd.Timestamp(f"{d} {t1}", tz=ET).tz_convert("UTC").to_pydatetime(),
                    feed=DataFeed.SIP,
                )
                q = client.get_stock_quotes(req).df
                q = q[(q["bid_price"] > 0) & (q["ask_price"] >= q["bid_price"])]
                if q.empty:
                    out["failed"].append(f"{d} {label}: no quotes")
                    continue
                mid = (q["ask_price"] + q["bid_price"]) / 2
                half = 1e4 * (q["ask_price"] - q["bid_price"]) / 2 / mid
                out[label].append(float(half.median()))
            except Exception as e:  # keep the study runnable if one window 404s
                out["failed"].append(f"{d} {label}: {type(e).__name__}")
    def med(vals: list[float]) -> float | None:
        return round(float(np.median(vals)), 4) if vals else None

    return {
        "half_spread_bps_median_0930": med(out["09:30"]),
        "half_spread_bps_median_1559": med(out["15:59-16:00"]),
        "windows_ok": len(out["09:30"]) + len(out["15:59-16:00"]),
        "windows_failed": out["failed"],
        "sample_days": out["sample_days"],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--skip-quotes", action="store_true")
    args = ap.parse_args()
    load_dotenv(REPO / ".env")

    results: dict = {"regulatory_fees_bps_round_trip": 0.3}
    for symbol in PAIRS:
        print(f"== {symbol}: fill-reference error (5m bar vs official auction print) ==")
        ref = fill_reference_errors(symbol)
        print(json.dumps(ref, indent=2))
        spread = None if args.skip_quotes else sample_half_spreads(symbol)
        if spread:
            print(f"== {symbol}: NBBO half-spread near auctions ==")
            print(json.dumps({k: v for k, v in spread.items() if k != "sample_days"}, indent=2))
        results[symbol] = {"fill_reference_error": ref, "auction_half_spread": spread}

    # Pre-registered mapping: per-fill cost = abs p75; fees (0.3 bps) ride the sell side.
    for symbol in PAIRS:
        ref = results[symbol]["fill_reference_error"]
        results[symbol]["evidence_based_costs"] = {
            "half_spread_bps": 0.0,
            "close_slippage_bps": ref["close_site"]["abs_p75_bps"],
            "slippage_bps": round(ref["open_site"]["abs_p75_bps"] + 0.3, 4),
            "round_trip_bps": round(
                ref["close_site"]["abs_p75_bps"] + ref["open_site"]["abs_p75_bps"] + 0.3, 4
            ),
        }
        print(f"{symbol} evidence-based: {results[symbol]['evidence_based_costs']}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
