"""Download historical bars from Alpaca into the local (gitignored) cache.

    uv sync --extra paper
    cp .env.example .env          # add your Alpaca keys (paper keys are fine for data)
    uv run --extra paper python scripts/fetch_data.py \
        --symbol SPY --start 2018-01-01 --end 2024-12-31 --feed sip \
        --out data/SPY_5m.parquet

Then set `data.source: data/SPY_5m.parquet` in the strategy config and run
scripts/run_backtest.py.

Free-tier note: SIP *historical* bars are available without a paid subscription
as long as they are older than ~15 minutes (always true for a backtest). If you
hit a subscription error, re-run with `--feed iex` (thinner data, prototype
only).
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd

from core.data.alpaca import bars_to_canonical, filter_rth
from core.strategy import ET

REPO = Path(__file__).resolve().parents[1]


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
    ap.add_argument("--symbol", default="SPY")
    ap.add_argument("--start", required=True, help="YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD")
    ap.add_argument("--minutes", type=int, default=5)
    ap.add_argument(
        "--timeframe",
        choices=["intraday", "daily"],
        default="intraday",
        help="intraday: RTH-filtered N-minute bars. daily: one bar/session (for SMA/ATR warm-up).",
    )
    ap.add_argument("--feed", choices=["sip", "iex"], default="sip")
    ap.add_argument(
        "--adjustment",
        choices=["raw", "split", "dividend", "all"],
        default="raw",
        help="Corporate-action adjustment. Use 'all' so ex-div/split gaps aren't "
        "counted as returns (required for overnight/close->open strategies).",
    )
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    load_dotenv(REPO / ".env")
    key, secret = os.environ.get("ALPACA_API_KEY"), os.environ.get("ALPACA_SECRET_KEY")
    if not key or not secret:
        raise SystemExit("Missing ALPACA_API_KEY / ALPACA_SECRET_KEY (see .env.example).")

    from alpaca.data.enums import Adjustment, DataFeed
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

    client = StockHistoricalDataClient(key, secret)
    feed = DataFeed.SIP if args.feed == "sip" else DataFeed.IEX
    adjustment = Adjustment(args.adjustment)
    daily = args.timeframe == "daily"
    timeframe = TimeFrame.Day if daily else TimeFrame(args.minutes, TimeFrameUnit.Minute)

    # Fetch year-by-year so a failure is resumable and progress is visible.
    frames = []
    for yr_start, yr_end in _year_chunks(args.start, args.end):
        label = "1d" if daily else f"{args.minutes}m"
        print(
            f"  fetching {args.symbol} {yr_start.date()} .. {yr_end.date()} "
            f"({label}, {args.feed}) ..."
        )
        req = StockBarsRequest(
            symbol_or_symbols=args.symbol,
            timeframe=timeframe,
            start=yr_start.to_pydatetime(),
            end=yr_end.to_pydatetime(),
            feed=feed,
            adjustment=adjustment,
        )
        raw = client.get_stock_bars(req).df
        if daily:
            # Daily bars are one-per-session; keep the vendor timestamp (session
            # date) as-is and do not apply the intraday RTH filter.
            canonical = bars_to_canonical(raw, args.symbol, timestamp="close")
        else:
            canonical = filter_rth(
                bars_to_canonical(raw, args.symbol, args.minutes, timestamp="open")
            )
        if not canonical.empty:
            frames.append(canonical)

    if not frames:
        raise SystemExit("No bars returned — check the symbol, dates, and data feed access.")

    bars = pd.concat(frames)
    bars = bars[~bars.index.duplicated(keep="last")].sort_index()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    bars.to_parquet(args.out)
    _report(bars, args.out, daily=daily)


def _year_chunks(start: str, end: str):
    s, e = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC")
    cur = s
    while cur < e:
        nxt = min(pd.Timestamp(f"{cur.year + 1}-01-01", tz="UTC"), e)
        yield cur, nxt
        cur = nxt


def _report(bars: pd.DataFrame, out: Path, daily: bool = False) -> None:
    et = bars.index.tz_convert(ET)
    print(f"\nWrote {len(bars):,} bars -> {out}")
    print(f"  date range : {et.min().date()} .. {et.max().date()}")
    if daily:
        print(f"  sessions   : {len(bars):,} daily bars (expect ~252/yr)")
        return
    per_day = bars.groupby(et.date).size()
    first_t = min(t.strftime("%H:%M") for t in et.time)
    last_t = max(t.strftime("%H:%M") for t in et.time)
    print(f"  sessions   : {per_day.size}")
    print(f"  ET bar span: {first_t} .. {last_t}  (expect 09:35 .. 16:00 for close-stamped RTH)")
    print(f"  bars/session median: {int(per_day.median())} (expect ~78 for full 5-min RTH days)")


if __name__ == "__main__":
    main()
