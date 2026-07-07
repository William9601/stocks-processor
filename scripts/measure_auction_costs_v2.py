"""Execution-cost study #2 — quote-grounded, judgment-window-clean.

Method pre-registered in
experiments/execution-cost-study/2026-07-07-0914-quote-validation/notes.md — read it
first; this script only executes that locked method.

Two measurements, QQQ primary (the candidate), SPY reported for context on B:

  B. Fill-reference cost (|5-min-bar reference - official auction print| in bps),
     computed SEPARATELY per vintage (IS/OOS/WF). Charged cost is the IS-only p75.
  A. Quote-grounded auction premium: official RAW print vs pre-auction NBBO mid, from
     Alpaca SIP historical quotes. Prints fetched RAW (adjustment=raw) so they share
     the raw quotes' price basis (adjusted parquet prints would be off by the
     back-adjustment factor vs a raw quote and corrupt the bps).

    uv run --extra paper python scripts/measure_auction_costs_v2.py \
        --out experiments/execution-cost-study/2026-07-07-0914-quote-validation/metrics.json
"""

from __future__ import annotations

import argparse
import json
import os
import time as _time
from datetime import time
from pathlib import Path

import numpy as np
import pandas as pd

from core.strategy import ET

REPO = Path(__file__).resolve().parents[1]

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
QUOTE_SYMBOL = "QQQ"  # measurement A: the candidate strategy is QQQ-gated

OPEN_STAMP = time(9, 35)
CLOSE_STAMP = time(16, 0)

# Vintages (from config.qqq.paper.yaml; fixed, not chosen here).
IS_END = pd.Timestamp("2021-12-31").date()
OOS_END = pd.Timestamp("2024-12-31").date()  # WF = everything after

SEED = 20260707
N_PER_VINTAGE = 40
N_HIGH_GAP = 30


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def vintage_of(d) -> str:
    if d <= IS_END:
        return "IS"
    if d <= OOS_END:
        return "OOS"
    return "WF"


# --------------------------------------------------------------------------- #
# Shared: session references and adjusted daily prints
# --------------------------------------------------------------------------- #
def session_refs(five_path: Path) -> pd.DataFrame:
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


def combined_refs(symbol: str) -> pd.DataFrame:
    frames = []
    for five, daily in PAIRS[symbol]:
        frames.append(session_refs(REPO / five).join(daily_refs(REPO / daily), how="inner"))
    refs = pd.concat(frames)
    return refs[~refs.index.duplicated(keep="last")].sort_index()


# --------------------------------------------------------------------------- #
# Measurement B — fill-reference cost per vintage
# --------------------------------------------------------------------------- #
def fill_reference_table(symbol: str) -> pd.DataFrame:
    refs = combined_refs(symbol)
    refs = refs.assign(
        open_ok=refs["first_t"].eq(OPEN_STAMP),
        close_ok=refs["last_t"].eq(CLOSE_STAMP),  # drops half-days
    )
    refs["close_err"] = 1e4 * (refs["last_close"] - refs["close"]).abs() / refs["close"]
    refs["open_err"] = 1e4 * (refs["first_open"] - refs["open"]).abs() / refs["open"]
    refs["vintage"] = [vintage_of(d) for d in refs.index]
    return refs


def p75(s: pd.Series) -> float:
    return round(float(s.quantile(0.75)), 4)


def b_stats(symbol: str) -> dict:
    t = fill_reference_table(symbol)
    out: dict = {"sessions": int(len(t)), "date_range": [str(t.index.min()), str(t.index.max())]}
    for v in ("IS", "OOS", "WF"):
        c = t[(t["vintage"] == v) & t["close_ok"]]["close_err"]
        o = t[(t["vintage"] == v) & t["open_ok"]]["open_err"]
        out[v] = {
            "n_close": int(c.size),
            "n_open": int(o.size),
            "close_p75_bps": p75(c) if c.size else None,
            "open_p75_bps": p75(o) if o.size else None,
        }
    # Cost-estimation pools (WF excluded from cost estimation entirely).
    is_only = t[t["vintage"] == "IS"]
    is_oos = t[t["vintage"].isin(["IS", "OOS"])]
    out["cost_close_p75_IS_only"] = p75(is_only[is_only["close_ok"]]["close_err"])
    out["cost_open_p75_IS_only"] = p75(is_only[is_only["open_ok"]]["open_err"])
    out["cost_close_p75_IS_OOS"] = p75(is_oos[is_oos["close_ok"]]["close_err"])
    out["cost_open_p75_IS_OOS"] = p75(is_oos[is_oos["open_ok"]]["open_err"])
    return out


# --------------------------------------------------------------------------- #
# Measurement A — quote-grounded auction premium (RAW prints vs RAW SIP quotes)
# --------------------------------------------------------------------------- #
def build_sample(symbol: str) -> pd.DataFrame:
    """Seeded stratified sample: N per vintage + a pooled high-gap stratum."""
    refs = combined_refs(symbol)
    # Overnight gap on adjusted closes/opens (ratio -> adjustment-invariant enough
    # for stratum selection): |Open(d+1)/Close(d) - 1|.
    nxt_open = refs["open"].shift(-1)
    gap = (nxt_open / refs["close"] - 1.0).abs()
    df = pd.DataFrame({"vintage": [vintage_of(d) for d in refs.index], "gap": gap}, index=refs.index)
    df = df.dropna(subset=["gap"])
    rng = np.random.default_rng(SEED)

    picks: dict = {}
    for v in ("IS", "OOS", "WF"):
        pool = df.index[df["vintage"] == v].to_numpy()
        n = min(N_PER_VINTAGE, len(pool))
        for d in rng.choice(pool, size=n, replace=False):
            picks[d] = "rand_" + v
    # High-gap stratum: top decile of gap, pooled; fill up to N_HIGH_GAP (may overlap
    # a random pick -> that day carries both labels; recorded once, both strata noted).
    thr = df["gap"].quantile(0.90)
    hg_pool = df.index[df["gap"] >= thr].to_numpy().copy()
    rng.shuffle(hg_pool)
    added = 0
    for d in hg_pool:
        if added >= N_HIGH_GAP:
            break
        picks.setdefault(d, "high_gap")
        added += 1
    labels = pd.Series(picks).sort_index()
    return pd.DataFrame({"stratum": labels})


def raw_daily_prints(symbol: str, start, end) -> pd.DataFrame:
    """RAW (unadjusted) official daily open/close — same basis as raw SIP quotes."""
    from alpaca.data.enums import Adjustment, DataFeed
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    key, secret = os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"]
    client = StockHistoricalDataClient(key, secret)
    req = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Day,
        start=pd.Timestamp(start).to_pydatetime(),
        end=pd.Timestamp(end).to_pydatetime(),
        feed=DataFeed.SIP,
        adjustment=Adjustment.RAW,
    )
    bars = client.get_stock_bars(req).df
    bars = bars.reset_index()
    bars["d"] = pd.to_datetime(bars["timestamp"]).dt.tz_convert(ET).dt.date
    return bars.set_index("d")[["open", "close"]].rename(
        columns={"open": "raw_open", "close": "raw_close"}
    )


def window_mid(client, symbol: str, d, t0: str, t1: str) -> float | None:
    from alpaca.data.enums import DataFeed
    from alpaca.data.requests import StockQuotesRequest

    req = StockQuotesRequest(
        symbol_or_symbols=symbol,
        start=pd.Timestamp(f"{d} {t0}", tz=ET).tz_convert("UTC").to_pydatetime(),
        end=pd.Timestamp(f"{d} {t1}", tz=ET).tz_convert("UTC").to_pydatetime(),
        feed=DataFeed.SIP,
    )
    q = client.get_stock_quotes(req).df
    if q.empty:
        return None
    q = q[(q["bid_price"] > 0) & (q["ask_price"] >= q["bid_price"])]
    if len(q) < 3:
        return None
    return float(((q["ask_price"] + q["bid_price"]) / 2).median())


def quote_premiums(symbol: str) -> dict:
    from alpaca.data.historical import StockHistoricalDataClient

    key, secret = os.environ.get("ALPACA_API_KEY"), os.environ.get("ALPACA_SECRET_KEY")
    if not key or not secret:
        raise SystemExit("Missing ALPACA_API_KEY / ALPACA_SECRET_KEY (see .env.example).")
    client = StockHistoricalDataClient(key, secret)

    sample = build_sample(symbol)
    end_pad = pd.Timestamp(sample.index.max()) + pd.Timedelta(days=1)  # daily end is exclusive
    prints = raw_daily_prints(symbol, f"{sample.index.min()}", f"{end_pad.date()}")

    rows = []
    fails = []
    for i, (d, row) in enumerate(sample.iterrows(), 1):
        if d not in prints.index:
            fails.append(f"{d}: no raw daily print")
            continue
        raw_open, raw_close = prints.loc[d, "raw_open"], prints.loc[d, "raw_close"]
        # Close site (MOC buy): print above pre-close mid = adverse (positive).
        close_mid = window_mid(client, symbol, d, "15:59:50", "16:00:00")
        close_prem = 1e4 * (raw_close - close_mid) / close_mid if close_mid else None
        # Open site (MOO sell): sold below pre-open mid = adverse (positive).
        open_mid = window_mid(client, symbol, d, "09:29:50", "09:30:00")
        open_tag = "preopen"
        if open_mid is None:
            open_mid = window_mid(client, symbol, d, "09:30:00", "09:30:10")
            open_tag = "postopen_fallback"
        open_prem = 1e4 * (open_mid - raw_open) / open_mid if open_mid else None
        if close_prem is None:
            fails.append(f"{d} close: no quotes")
        if open_prem is None:
            fails.append(f"{d} open: no quotes")
        rows.append(
            {
                "d": str(d),
                "stratum": row["stratum"],
                "close_prem_bps": close_prem,
                "open_prem_bps": open_prem,
                "open_tag": open_tag,
            }
        )
        if i % 20 == 0:
            print(f"  ...{i}/{len(sample)} sessions fetched")
        _time.sleep(0.05)

    df = pd.DataFrame(rows)
    # PRIMARY charge is measured on the random-stratified sample only; the high-gap
    # stratum is reported SEPARATELY as a tail check (per pre-registration).
    rand = df[df["stratum"].str.startswith("rand_")]
    hg = df[df["stratum"] == "high_gap"]

    def site(frame: pd.DataFrame, col: str) -> dict:
        s = frame[col].dropna()
        a = s.abs()
        return {
            "n": int(s.size),
            "signed_mean_bps": round(float(s.mean()), 4) if s.size else None,
            "signed_p50_bps": round(float(s.median()), 4) if s.size else None,
            "abs_p75_bps": round(float(a.quantile(0.75)), 4) if s.size else None,
            "abs_p90_bps": round(float(a.quantile(0.90)), 4) if s.size else None,
        }

    return {
        "symbol": symbol,
        "n_sampled": int(len(df)),
        "n_random": int(len(rand)),
        "n_high_gap": int(len(hg)),
        "close_site": site(rand, "close_prem_bps"),  # primary (random sample)
        "open_site": site(rand, "open_prem_bps"),
        "high_gap_close_site": site(hg, "close_prem_bps"),  # tail check, reported not charged
        "high_gap_open_site": site(hg, "open_prem_bps"),
        "open_fallback_used": int((df["open_tag"] == "postopen_fallback").sum()),
        "failures": fails,
        "per_session": rows,
    }


# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--skip-quotes", action="store_true", help="measurement B only")
    args = ap.parse_args()
    load_dotenv(REPO / ".env")

    results: dict = {"regulatory_fees_bps_round_trip": 0.3, "seed": SEED}

    print("== Measurement B: fill-reference cost per vintage ==")
    for symbol in PAIRS:
        results.setdefault(symbol, {})["fill_reference"] = b_stats(symbol)
        print(f"  {symbol}: {json.dumps(results[symbol]['fill_reference'], indent=2)}")

    if not args.skip_quotes:
        print(f"== Measurement A: quote-grounded auction premium ({QUOTE_SYMBOL}) ==")
        qa = quote_premiums(QUOTE_SYMBOL)
        results[QUOTE_SYMBOL]["quote_premium"] = qa
        print(f"  close_site: {qa['close_site']}")
        print(f"  open_site:  {qa['open_site']}  (fallback opens: {qa['open_fallback_used']})")
        print(f"  failures: {len(qa['failures'])}")

        # Charged cost per the locked rule: MORE CONSERVATIVE of A vs B, per site,
        # B measured IS-only.
        b = results[QUOTE_SYMBOL]["fill_reference"]
        a_close = qa["close_site"]["abs_p75_bps"]
        a_open = qa["open_site"]["abs_p75_bps"]
        charged_close = max(b["cost_close_p75_IS_only"], a_close or 0.0)
        charged_open = max(b["cost_open_p75_IS_only"], a_open or 0.0)
        results[QUOTE_SYMBOL]["charged_cost"] = {
            "half_spread_bps": 0.0,
            "close_slippage_bps": round(charged_close, 4),
            "slippage_bps": round(charged_open + 0.3, 4),
            "round_trip_bps": round(charged_close + charged_open + 0.3, 4),
            "close_source": "B_IS" if charged_close == b["cost_close_p75_IS_only"] else "A_quote",
            "open_source": "B_IS" if charged_open == b["cost_open_p75_IS_only"] else "A_quote",
        }
        print(f"  CHARGED (conservative A/B): {results[QUOTE_SYMBOL]['charged_cost']}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
