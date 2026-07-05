"""Run a backtest from a strategy config and write a provenanced experiment.

Usage:
    uv run python scripts/run_backtest.py strategies/intraday-momentum/config.yaml --sample oos
    uv run python scripts/run_backtest.py <config> --sample is --tag demo   # synthetic if no data

Writes experiments/<strategy>/<YYYY-MM-DD-HHMM>-<tag>/ with config.yaml (incl.
git commit), metrics.json, and notes.md — never overwriting an existing run.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path

import yaml

from core.backtest.costs import CostModel
from core.backtest.engine import BacktestEngine
from core.data.feed import DataFeed
from core.data.synthetic import make_intraday_bars
from core.loader import load_strategy
from core.risk.sizing import RiskLimits, RiskManager

REPO = Path(__file__).resolve().parents[1]


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
        ).strip()
    except Exception:
        return "unknown"


def build_feed(cfg: dict, window: dict | None) -> tuple[DataFeed, bool]:
    symbol = cfg["instrument"]["symbol"]
    source = cfg.get("data", {}).get("source")
    synthetic = source is None
    if synthetic:
        bars = make_intraday_bars(symbol=symbol, start="2020-01-02", days=120, momentum=0.6)
        feed = DataFeed(symbol, bars)
    else:
        feed = DataFeed.from_source(symbol, REPO / source)
    if window:
        feed = feed.between(window.get("start"), window.get("end"))
    return feed, synthetic


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("config", type=Path)
    ap.add_argument("--sample", choices=["is", "oos", "walkforward"], default="is")
    ap.add_argument("--tag", default=None)
    args = ap.parse_args()

    cfg = yaml.safe_load(args.config.read_text())
    window_key = {"is": "in_sample", "oos": "out_of_sample", "walkforward": "walk_forward"}[
        args.sample
    ]
    window = cfg["backtest"].get(window_key)

    feed, synthetic = build_feed(cfg, None if synthetic_needed(cfg) else window)
    if synthetic:
        print("WARNING: no data.source configured — running on SYNTHETIC bars. "
              "Not a valid result; wire a real provider before trusting numbers.")

    strat = load_strategy(REPO / cfg["strategy"]["path"], cfg["strategy"].get("params", {}))
    risk = RiskManager(RiskLimits(**cfg["risk"]))
    costs = CostModel(**cfg["costs"])
    engine = BacktestEngine(
        strat, feed, risk, costs,
        starting_cash=cfg["backtest"]["starting_cash"], sample=args.sample,
    )
    result = engine.run()

    print(json.dumps(result.metrics, indent=2, default=str))
    write_experiment(cfg, args, result, synthetic)


def synthetic_needed(cfg: dict) -> bool:
    return cfg.get("data", {}).get("source") is None


def write_experiment(cfg: dict, args, result, synthetic: bool) -> None:
    strat_name = Path(cfg["strategy"]["path"]).name
    tag = args.tag or ("synthetic-demo" if synthetic else args.sample)
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    out = REPO / "experiments" / strat_name / f"{stamp}-{tag}"
    out.mkdir(parents=True, exist_ok=False)

    provenance = dict(cfg)
    provenance["provenance"] = {
        "git_commit": git_commit(),
        "sample": args.sample,
        "synthetic_data": synthetic,
        "run_at": datetime.now().isoformat(timespec="seconds"),
    }
    (out / "config.yaml").write_text(yaml.safe_dump(provenance, sort_keys=False))
    (out / "metrics.json").write_text(json.dumps(result.metrics, indent=2, default=str))
    if result.trades:
        # Per-trade record: the SPEC-level reporting (realized-R distribution,
        # exit-type split, worst trade) is only reproducible from trades.
        import pandas as pd

        pd.DataFrame(
            [
                {
                    "entry_time": t.entry_time,
                    "exit_time": t.exit_time,
                    "side": t.side.name,
                    "qty": t.qty,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "costs": t.costs,
                    "net_pnl": t.net_pnl,
                    "exit_reason": t.exit_reason,
                }
                for t in result.trades
            ]
        ).to_csv(out / "trades.csv", index=False)
    (out / "notes.md").write_text(
        f"# {strat_name} — {tag}\n\n"
        f"- sample: {args.sample}\n- synthetic data: {synthetic}\n"
        f"- trades: {result.metrics['trade_count']}\n"
        f"- net return: {result.metrics['net_return']:.4f}\n"
        f"- sharpe: {result.metrics['sharpe']:.3f}\n\n"
        "## Notes\n\n_What was tried and learned._\n"
    )
    print(f"\nWrote experiment -> {out.relative_to(REPO)}")


if __name__ == "__main__":
    main()
