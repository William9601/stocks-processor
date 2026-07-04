"""Isolation study: is the 15:40 decision-bar move itself neutral?

Runs each judged config twice — decision_offset_minutes 5 (== the old 15:55
decision bar on a full day) vs 20 (the 15:40 variant) — on identical code,
identical data, identical windows. Any difference between the two columns is
attributable to the decision-time shift alone; any difference vs the committed
v2 runs (2026-07-03-2323-*) is attributable to the calendar/metrics fixes.

Reproduce from the repo root:
    uv run python experiments/overnight-long/2026-07-04-0940-t1540-isolation-study/run_isolation.py
"""

from pathlib import Path

import yaml

from core.backtest.costs import CostModel
from core.backtest.engine import BacktestEngine
from core.data.feed import DataFeed
from core.loader import load_strategy
from core.risk.sizing import RiskLimits, RiskManager

REPO = Path(__file__).resolve().parents[3]


def run(cfg_path: str, sample: str, offset: int) -> str:
    cfg = yaml.safe_load((REPO / cfg_path).read_text())
    cfg["strategy"]["params"]["decision_offset_minutes"] = offset
    key = {"is": "in_sample", "oos": "out_of_sample", "walkforward": "walk_forward"}[sample]
    w = cfg["backtest"][key]
    feed = DataFeed.from_source(
        cfg["instrument"]["symbol"], REPO / cfg["data"]["source"]
    ).between(w.get("start"), w.get("end"))
    strat = load_strategy(REPO / cfg["strategy"]["path"], cfg["strategy"]["params"])
    m = BacktestEngine(
        strat, feed, RiskManager(RiskLimits(**cfg["risk"])), CostModel(**cfg["costs"]),
        starting_cash=cfg["backtest"]["starting_cash"], sample=sample,
    ).run().metrics
    return (f"  offset={offset:2d}: sharpe={m['sharpe']:.4f} "
            f"trade_days={m['sharpe_trade_days']:.4f} net={m['net_return']:+.4f} "
            f"dd={m['max_drawdown']:+.4f} trades={m['trade_count']} "
            f"sessions={m['session_count']}")


def main() -> None:
    suite = [
        ("evcost IS", "strategies/overnight-long/config.qqq.evcost.yaml", "is"),
        ("evcost OOS", "strategies/overnight-long/config.qqq.evcost.yaml", "oos"),
        ("evcost WF", "strategies/overnight-long/config.qqq.wf.evcost.yaml", "walkforward"),
        ("locked WF", "strategies/overnight-long/config.qqq.wf.yaml", "walkforward"),
    ]
    for label, cfg, sample in suite:
        print(label)
        for offset in (5, 20):
            print(run(cfg, sample, offset))


if __name__ == "__main__":
    main()
