"""Read-only preflight for the overnight paper path — places NO orders.

Run any time (market open or closed) to verify everything Monday's session
needs: credentials, paper account access, SIP data entitlement, order-type
enums, the exchange calendar, daily-gate freshness, and log paths.

    uv run --extra paper python scripts/preflight_paper.py \
        strategies/overnight-long/config.qqq.paper.yaml
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
import yaml

from core.data.calendar import next_session, session_close_et, session_open_et
from core.strategy import ET

REPO = Path(__file__).resolve().parents[1]
CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def last_completed_session(today) -> object:
    prev = today - pd.Timedelta(days=1)
    while session_close_et(prev) is None:
        prev -= pd.Timedelta(days=1)
    return prev


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("config", type=Path, nargs="?",
                    default=Path("strategies/overnight-long/config.qqq.paper.yaml"))
    args = ap.parse_args()
    cfg = yaml.safe_load((REPO / args.config).read_text())
    symbol = cfg["instrument"]["symbol"]

    print(f"Preflight for {args.config} ({symbol}) — read-only, no orders.\n")

    # 1. credentials + feed setting
    load_dotenv(REPO / ".env")
    key, secret = os.environ.get("ALPACA_API_KEY"), os.environ.get("ALPACA_SECRET_KEY")
    check("ALPACA_API_KEY / ALPACA_SECRET_KEY present", bool(key and secret))
    feed = os.environ.get("ALPACA_DATA_FEED", "iex")
    check("ALPACA_DATA_FEED is sip (required by overnight mode)", feed.lower() == "sip",
          f"feed={feed}")
    if not (key and secret):
        _summary()

    # 2. alpaca-py + auction order-type enums
    try:
        from alpaca.trading.enums import TimeInForce

        has_cls = hasattr(TimeInForce, "CLS") and hasattr(TimeInForce, "OPG")
        check("alpaca-py installed; MOC (CLS) / MOO (OPG) enums available", has_cls)
    except ImportError as exc:
        check("alpaca-py installed", False, f"{exc} — run: uv sync --extra paper")
        _summary()

    # 3. trading API: paper account + position
    from core.execution.paper import AlpacaPaperBroker

    broker = AlpacaPaperBroker(key, secret, feed=feed)
    try:
        equity, cash = broker.account()
        check("paper trading API reachable (account)", True,
              f"equity ${equity:,.0f}, cash ${cash:,.0f}")
    except Exception as exc:
        check("paper trading API reachable (account)", False, repr(exc))
        _summary()
    try:
        pos = broker.position(symbol)
        check(f"position query ({symbol})", True,
              "flat" if pos.is_flat else f"OPEN {pos.qty} @ {pos.avg_price}")
    except Exception as exc:
        check(f"position query ({symbol})", False, repr(exc))

    # 4. historical 5m bars for the last completed session (what the 15:30
    #    polling loop consumes)
    now_et = pd.Timestamp.now(tz=ET)
    last_sess = last_completed_session(now_et.date())
    start = pd.Timestamp(f"{last_sess} 09:30", tz=ET).tz_convert("UTC")
    end = pd.Timestamp(f"{last_sess} 16:10", tz=ET).tz_convert("UTC")
    try:
        bars = broker.recent_bars(symbol, start, end)
        ok = bars is not None and len(bars) > 60
        last_bar = bars.index[-1].tz_convert(ET) if ok else None
        check(f"5m SIP bars for last session ({last_sess})", ok,
              f"{len(bars)} bars, last {last_bar}" if ok else "empty/short response")
    except Exception as exc:
        check(f"5m SIP bars for last session ({last_sess})", False, repr(exc))

    # 5. official auction prints (what the fill log measures against)
    try:
        open_px, close_px = broker.auction_prints(symbol, last_sess)
        check("official auction prints (daily bar)", bool(open_px and close_px),
              f"{last_sess} open {open_px} close {close_px}")
    except Exception as exc:
        check("official auction prints (daily bar)", False, repr(exc))

    # 6. real-time SIP entitlement (historical SIP works on free tier for
    #    >15-min-old data; the 15:40 decision bar on Monday will NOT be —
    #    the latest-trade endpoint exercises the live entitlement now)
    try:
        from alpaca.data.enums import DataFeed
        from alpaca.data.requests import StockLatestTradeRequest

        req = StockLatestTradeRequest(symbol_or_symbols=symbol, feed=DataFeed.SIP)
        trade = broker._data.get_stock_latest_trade(req)[symbol]
        check("real-time SIP entitlement (latest trade)", True,
              f"last trade {trade.price} @ {trade.timestamp}")
    except Exception as exc:
        check("real-time SIP entitlement (latest trade)", False,
              f"{exc!r} — Monday's 15:40 bar needs a SIP-entitled key")

    # 7. calendar: the next session's schedule the runner will follow
    nxt = next_session(now_et.date()) if session_close_et(now_et.date()) is None \
        else now_et.date()
    open_et, close_et = session_open_et(nxt), session_close_et(nxt)
    offset = int(cfg["strategy"]["params"].get("decision_offset_minutes", 20))
    decision = close_et - pd.Timedelta(minutes=offset)
    check("next session schedule", True,
          f"{nxt}: open {open_et.time()}, decision {decision.time()}, "
          f"close {close_et.time()}, MOC cutoff ~{(close_et - pd.Timedelta(minutes=15)).time()}")

    # 8. daily-gate data freshness (same rule run_paper enforces)
    source = cfg["strategy"]["params"].get("daily_source")
    idx = pd.read_parquet(REPO / source).index
    last_daily = pd.Timestamp(idx.max()).tz_convert(ET).date()
    check(f"daily gate data fresh ({source})", last_daily >= last_sess,
          f"ends {last_daily}, last completed session {last_sess}")

    # 9. log paths writable
    execution = cfg.get("execution", {})
    fill_log = REPO / execution["fill_log"]
    try:
        fill_log.parent.mkdir(parents=True, exist_ok=True)
        probe = fill_log.parent / ".write-probe"
        probe.write_text("ok")
        probe.unlink()
        check("fill log / risk-state directory writable", True, str(fill_log.parent))
    except Exception as exc:
        check("fill log / risk-state directory writable", False, repr(exc))

    _summary()


def _summary() -> None:
    failed = [name for name, ok, _ in CHECKS if not ok]
    print()
    if failed:
        print(f"PREFLIGHT FAILED ({len(failed)}): " + "; ".join(failed))
        sys.exit(1)
    print(f"PREFLIGHT OK — all {len(CHECKS)} checks passed. No orders were placed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
