"""Replay a trading day through the LIVE loop, on demand.

Watch the strategy make its live decisions (ENTER / STOP / CLOSE) bar-by-bar
over a simulated session — no market hours, no Alpaca account needed. Uses the
same LiveRunner code path that paper/live trading uses.

    # scripted scenarios (synthetic, deterministic):
    uv run python scripts/simulate_day.py strategies/intraday-momentum/config.yaml --scenario up
    uv run python scripts/simulate_day.py <config> --scenario reversal   # shows a stop-out

    # multiple random momentum days:
    uv run python scripts/simulate_day.py <config> --days 5

    # your own historical bars (parquet/csv), one date or all:
    uv run python scripts/simulate_day.py <config> --source data/spy_5m.parquet --date 2024-03-15

NOTE: fills here follow the LIVE model (market fills at the decision bar's
close); this can differ slightly from scripts/run_backtest.py, which fills at
the next bar's open. Use this to *watch behaviour*, and run_backtest for the
number that counts.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from core.backtest.costs import CostModel
from core.data.feed import load_bars
from core.execution.live_runner import LiveRunner
from core.execution.replay import ReplayBroker, et_hhmm, simulate
from core.loader import load_strategy
from core.risk.sizing import RiskLimits, RiskManager
from core.strategy import ET, Side

REPO = Path(__file__).resolve().parents[1]


def _session(date: str, closes: np.ndarray) -> pd.DataFrame:
    idx = pd.date_range(f"{date} 09:35", f"{date} 16:00", freq="5min", tz=ET).tz_convert("UTC")
    n = len(idx)
    closes = np.asarray(closes, dtype=float)
    open_ = np.empty(n)
    open_[0] = float(closes[0])
    open_[1:] = closes[:-1]
    high = np.maximum(open_, closes) + 0.05
    low = np.minimum(open_, closes) - 0.05
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": closes, "volume": np.full(n, 1e5)},
        index=idx,
    )


def _scenario(kind: str, date: str = "2024-03-15") -> pd.DataFrame:
    n = len(pd.date_range(f"{date} 09:35", f"{date} 16:00", freq="5min"))
    if kind == "up":
        closes = np.linspace(300.0, 303.0, n)
    elif kind == "down":
        closes = np.linspace(300.0, 297.0, n)
    elif kind == "reversal":
        # gentle morning rise into the 15:00 long, then a crash through the stop.
        closes = np.linspace(300.0, 301.0, n)
        entry_i = _index_at(date, "15:00")
        closes[entry_i:] = np.linspace(301.0, 296.5, n - entry_i)
    else:
        raise SystemExit(f"unknown scenario: {kind}")
    return _session(date, closes)


def _index_at(date: str, hhmm: str) -> int:
    idx = pd.date_range(f"{date} 09:35", f"{date} 16:00", freq="5min")
    target = pd.Timestamp(f"{date} {hhmm}").time()
    matches = np.where(idx.time == target)[0]
    return int(matches[0]) if len(matches) else len(idx) - 1


def build_bars(args) -> pd.DataFrame:
    if args.source:
        bars = load_bars(REPO / args.source)
        if args.date:
            et = bars.tz_convert(ET)
            bars = bars[et.index.date == pd.Timestamp(args.date).date()]
            if bars.empty:
                raise SystemExit(f"No bars for {args.date} in {args.source}")
        return bars
    if args.scenario:
        return _scenario(args.scenario)
    # default: N random momentum sessions
    from core.data.synthetic import make_intraday_bars

    return make_intraday_bars(days=args.days, momentum=0.8, seed=args.seed)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("config", type=Path)
    ap.add_argument("--scenario", choices=["up", "down", "reversal"])
    ap.add_argument("--days", type=int, default=1)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--source", type=str, help="parquet/csv of 5-min bars")
    ap.add_argument("--date", type=str, help="restrict --source to one YYYY-MM-DD")
    ap.add_argument("--sleep", type=float, default=0.0, help="seconds between bars (animate)")
    args = ap.parse_args()

    cfg = yaml.safe_load(args.config.read_text())
    symbol = cfg["instrument"]["symbol"]
    bars = build_bars(args)

    strat = load_strategy(REPO / cfg["strategy"]["path"], cfg["strategy"].get("params", {}))
    risk = RiskManager(RiskLimits(**cfg["risk"]))
    costs = CostModel(**cfg["costs"])
    cash = cfg["backtest"]["starting_cash"]
    broker = ReplayBroker(symbol, bars, cash, costs)

    print(f"Simulating {symbol}: {len(bars)} bars, "
          f"{et_hhmm(bars.index[0])} -> {et_hhmm(bars.index[-1])}\n")
    runner = LiveRunner(
        strat, risk, broker, symbol,
        session_start=cfg["strategy"]["params"].get("ref_start", "09:30"),
        on_event=lambda m: print(f"  {et_hhmm(broker._now())}  {m}"),
    )
    trades = simulate(runner, broker, sleep=args.sleep)
    _summary(bars, broker, trades, cash)


def _summary(bars, broker, trades, starting_cash) -> None:
    print("\n" + "-" * 60)
    if not trades:
        print("No trades — the threshold gate sat out every session (or no signal).")
    for t in trades:
        side = "LONG " if t.side is Side.LONG else "SHORT"
        print(f"  {side} {int(t.qty):>4} | in {t.entry_price:8.3f} @ {et_hhmm(t.entry_time)[-5:]}"
              f" -> out {t.exit_price:8.3f} @ {et_hhmm(t.exit_time)[-5:]}"
              f" | {t.exit_reason:9} | net ${t.net_pnl:+.2f} (costs ${t.costs:.2f})")
    net = sum(t.net_pnl for t in trades)
    end_equity = broker.cash + broker._pos_qty * float(bars.iloc[-1]["close"])
    print("-" * 60)
    print(f"  trades: {len(trades)}   net P&L: ${net:+.2f}   "
          f"return: {end_equity / starting_cash - 1:+.4%}   "
          f"flat at close: {broker._pos_qty == 0.0}")


if __name__ == "__main__":
    main()
