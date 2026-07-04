"""Run the strategy live against an Alpaca PAPER account.

    uv sync --extra paper
    cp .env.example .env            # then fill in your Alpaca paper keys
    uv run python scripts/run_paper.py strategies/intraday-momentum/config.yaml

PAPER ONLY. This script never connects to a live account. It requires an
explicit per-session confirmation before it will place any (paper) orders,
per the project's hard rules.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
import yaml

from core.data.calendar import session_close_et
from core.execution.live_runner import LiveRunner, OvernightAuctionRunner
from core.execution.paper import AlpacaPaperBroker
from core.loader import load_strategy
from core.risk.sizing import RiskLimits, RiskManager

REPO = Path(__file__).resolve().parents[1]


def check_daily_source_fresh(cfg: dict) -> None:
    """The regime gate reads the LAST COMPLETED daily close from the daily
    parquet — a stale file silently gates on old data. Refuse to trade unless
    it covers the most recent completed session."""
    source = cfg["strategy"]["params"].get("daily_source")
    if source is None:
        return
    idx = pd.read_parquet(REPO / source).index
    last_date = pd.Timestamp(idx.max()).tz_convert("America/New_York").date()
    first_date = pd.Timestamp(idx.min()).tz_convert("America/New_York").date()
    today = pd.Timestamp.now(tz="America/New_York").date()
    # Most recent completed session strictly before today.
    prev = today - pd.Timedelta(days=1)
    while session_close_et(prev) is None:
        prev -= pd.Timedelta(days=1)
    if last_date < prev:
        sys.exit(
            f"STALE daily data: {source} ends {last_date}, but the last completed "
            f"session is {prev}. The 200-SMA gate would run on old closes.\n"
            f"Refresh it first, e.g.:\n"
            f"  uv run --extra paper python scripts/fetch_data.py --symbol "
            f"{cfg['instrument']['symbol']} --start {first_date} --end {today} "
            f"--timeframe daily --adjustment all --feed sip --out {source}"
        )


def load_dotenv(path: Path) -> None:
    """Minimal .env loader (no extra dependency)."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())


def confirm_paper(symbol: str, assume_yes: bool) -> None:
    banner = (
        "\n" + "=" * 64 + "\n"
        "  ALPACA PAPER TRADING — this WILL place orders on your paper account\n"
        f"  strategy symbol: {symbol}   endpoint: paper-api.alpaca.markets\n"
        + "=" * 64 + "\n"
    )
    print(banner)
    if assume_yes:
        return
    if input("Type 'paper' to confirm this session: ").strip().lower() != "paper":
        print("Aborted.")
        sys.exit(1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("config", type=Path)
    ap.add_argument("--yes", action="store_true", help="skip the interactive confirmation")
    ap.add_argument("--poll-seconds", type=float, default=30.0)
    args = ap.parse_args()

    load_dotenv(REPO / ".env")
    key, secret = os.environ.get("ALPACA_API_KEY"), os.environ.get("ALPACA_SECRET_KEY")
    if not key or not secret:
        sys.exit("Missing ALPACA_API_KEY / ALPACA_SECRET_KEY (see .env.example).")

    cfg = yaml.safe_load(args.config.read_text())
    symbol = cfg["instrument"]["symbol"]
    feed = os.environ.get("ALPACA_DATA_FEED", "iex")
    if feed.lower() != "sip":
        print("WARNING: using IEX data (thin). Set ALPACA_DATA_FEED=sip for real signals.")

    confirm_paper(symbol, args.yes)

    strat = load_strategy(REPO / cfg["strategy"]["path"], cfg["strategy"].get("params", {}))
    risk = RiskManager(RiskLimits(**cfg["risk"]))
    broker = AlpacaPaperBroker(key, secret, feed=feed)

    execution = cfg.get("execution", {})
    if execution.get("mode") == "overnight_auction":
        # MOC entry / MOO exit cycle; every auction fill is appended to the
        # fill log — that log is the paper-phase cost measurement.
        check_daily_source_fresh(cfg)
        runner = OvernightAuctionRunner(
            strat, risk, broker, symbol,
            fill_log=str(REPO / execution["fill_log"]),
            poll_seconds=float(execution.get("poll_seconds", args.poll_seconds)),
            on_event=lambda m: print(f"[paper] {m}"),
        )
        runner.run()
        return

    runner = LiveRunner(
        strat, risk, broker, symbol,
        session_start=cfg["strategy"]["params"].get("ref_start", "09:30"),
        on_event=lambda m: print(f"[paper] {m}"),
    )
    runner.run(poll_seconds=args.poll_seconds)


if __name__ == "__main__":
    main()
