"""Engine IS cross-check for fomc-drift (the ORB reconciliation pattern).

Runs the IMPLEMENTED strategy through the real backtest engine on the IS window
(1994-2015) and confirms it reproduces the standalone pregate
(``experiments/fomc-drift/2026-07-06-pregate/pregate_events_is.csv``)
event-by-event to rounding. This is a CORRECTNESS PROOF of the fill mapping, not
a new look at the edge — the IS window was already read in the pregate.

For each engine trade we strip the known per-side cost factor off the fill
prices to recover the raw close(T-1) and close(T) the engine actually
transacted, and compare that gross close-to-close return to the pregate's gross
for the same announcement day T. A match proves the engine bought at close(T-1)
and sold at close(T) — the exact daily-bar off-by-one the SPEC requires.

    uv run python scripts/crosscheck_fomc_is.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

from core.backtest.costs import CostModel
from core.backtest.engine import BacktestEngine
from core.data.feed import DataFeed
from core.loader import load_strategy
from core.risk.sizing import RiskLimits, RiskManager

REPO = Path(__file__).resolve().parents[1]
ET = "America/New_York"
PREGATE = REPO / "experiments/fomc-drift/2026-07-06-pregate/pregate_events_is.csv"
TOL_BPS = 0.01  # per-event gross agreement tolerance


def main() -> None:
    cfg = yaml.safe_load((REPO / "strategies/fomc-drift/config.yaml").read_text())
    window = cfg["backtest"]["in_sample"]

    feed = DataFeed.from_source(cfg["instrument"]["symbol"], REPO / cfg["data"]["source"])
    feed = feed.between(window["start"], window["end"])
    strat = load_strategy(REPO / cfg["strategy"]["path"], cfg["strategy"].get("params", {}))
    costs = CostModel(**cfg["costs"])
    risk = RiskManager(RiskLimits(**cfg["risk"]))
    engine = BacktestEngine(strat, feed, risk, costs,
                            starting_cash=cfg["backtest"]["starting_cash"], sample="is")
    result = engine.run()

    # Per-side cost factor the engine pushed against each MOC leg.
    f = (costs.half_spread_bps + costs.close_slippage_bps) / 1e4

    rows = []
    for t in result.trades:
        T = t.exit_time.tz_convert(ET).date()
        entry_raw = t.entry_price / (1 + f)   # strip buy-side adverse cost
        exit_raw = t.exit_price / (1 - f)     # strip sell-side adverse cost
        gross_bps = (exit_raw / entry_raw - 1) * 1e4
        net_bps = (t.exit_price / t.entry_price - 1) * 1e4
        rows.append({"T": str(T), "engine_gross_bps": gross_bps, "engine_net_bps": net_bps})
    eng = pd.DataFrame(rows).set_index("T")

    pre = pd.read_csv(PREGATE).set_index("T")
    pre.index = pre.index.astype(str)

    only_eng = sorted(set(eng.index) - set(pre.index))
    only_pre = sorted(set(pre.index) - set(eng.index))
    common = sorted(set(eng.index) & set(pre.index))

    merged = eng.loc[common].join(pre.loc[common, ["gross_bps"]])
    merged["gross_diff_bps"] = (merged["engine_gross_bps"] - merged["gross_bps"]).abs()
    max_diff = float(merged["gross_diff_bps"].max())
    worst = merged["gross_diff_bps"].idxmax()

    print(f"engine trades (IS): {len(eng)}   pregate events (IS): {len(pre)}")
    print(f"matched by T: {len(common)}   only-engine: {len(only_eng)}   "
          f"only-pregate: {len(only_pre)}")
    if only_eng:
        print(f"  ONLY IN ENGINE: {only_eng[:10]}")
    if only_pre:
        print(f"  ONLY IN PREGATE: {only_pre[:10]}")
    print(f"max |gross(engine) - gross(pregate)|: {max_diff:.5f} bps  (worst T={worst})")
    print(f"  engine net/event (mean, after 2.0 cost): {eng['engine_net_bps'].mean():.2f} bps")
    print(f"  pregate gross/event (mean): {pre['gross_bps'].mean():.2f} bps  "
          f"-> expected net {pre['gross_bps'].mean() - 2.0:.2f} bps")

    ok = (len(only_eng) == 0 and len(only_pre) == 0 and max_diff <= TOL_BPS
          and len(eng) == len(pre))
    if ok:
        print(f"\nPASS — engine reproduces the pregate event-by-event "
              f"(all {len(common)} events, max diff {max_diff:.5f} bps <= {TOL_BPS}). "
              "Fill mapping verified: BUY fills close(T-1), SELL fills close(T).")
        sys.exit(0)
    print("\nFAIL — engine does NOT reconcile with the pregate; fix the fill mapping "
          "before going near the OOS. (See event mismatches above.)")
    merged.sort_values("gross_diff_bps", ascending=False).head(15).to_csv(sys.stdout)
    sys.exit(1)


if __name__ == "__main__":
    main()
