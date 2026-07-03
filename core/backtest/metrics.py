"""Standard performance metrics (the experiments/ metrics.json field set).

Because the strategy is flat overnight, daily P&L is well defined and the
equity curve is built by summing each day's realized trade P&L. Sharpe/Sortino
are annualized from daily returns (252 trading days).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from core.strategy import Side

if TYPE_CHECKING:
    from core.execution.broker import Trade

TRADING_DAYS = 252


def _daily_equity(trades: list[Trade], starting_equity: float) -> pd.Series:
    if not trades:
        return pd.Series([starting_equity])
    rows = [(t.day, t.net_pnl) for t in trades]
    daily = pd.DataFrame(rows, columns=["day", "pnl"]).groupby("day")["pnl"].sum().sort_index()
    return starting_equity + daily.cumsum()


def compute_metrics(
    trades: list[Trade],
    starting_equity: float,
    sample: str,
    start_date: str,
    end_date: str,
) -> dict:
    equity = _daily_equity(trades, starting_equity)
    daily_ret = equity.pct_change().dropna()

    net_pnls = np.array([t.net_pnl for t in trades], dtype=float)
    gross_pnls = np.array([t.net_pnl + t.costs for t in trades], dtype=float)
    wins = net_pnls[net_pnls > 0]
    losses = net_pnls[net_pnls < 0]

    sharpe = _annualized_sharpe(daily_ret)
    sortino = _annualized_sortino(daily_ret)
    max_dd, dd_days = _max_drawdown(equity)

    total_costs = float(sum(t.costs for t in trades))
    ending_equity = float(equity.iloc[-1]) if len(equity) else starting_equity

    return {
        "net_return": ending_equity / starting_equity - 1.0,
        "gross_return": (starting_equity + gross_pnls.sum()) / starting_equity - 1.0,
        "annualized_return": _annualized_return(daily_ret),
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_dd,
        "max_drawdown_days": dd_days,
        "win_rate": float(len(wins) / len(net_pnls)) if len(net_pnls) else 0.0,
        "profit_factor": float(wins.sum() / -losses.sum()) if losses.sum() != 0 else float("inf"),
        "avg_win": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss": float(losses.mean()) if len(losses) else 0.0,
        "trade_count": len(trades),
        "turnover": float(sum(abs(t.qty * t.entry_price) for t in trades) / starting_equity),
        "cost_drag": total_costs / starting_equity,
        "long_pnl": float(sum(t.net_pnl for t in trades if t.side is Side.LONG)),
        "short_pnl": float(sum(t.net_pnl for t in trades if t.side is Side.SHORT)),
        "start_date": start_date,
        "end_date": end_date,
        "sample": sample,
    }


def _annualized_sharpe(daily_ret: pd.Series) -> float:
    if len(daily_ret) < 2 or daily_ret.std(ddof=1) == 0:
        return 0.0
    return float(daily_ret.mean() / daily_ret.std(ddof=1) * np.sqrt(TRADING_DAYS))


def _annualized_sortino(daily_ret: pd.Series) -> float:
    downside = daily_ret[daily_ret < 0]
    if len(downside) < 2 or downside.std(ddof=1) == 0:
        return 0.0
    return float(daily_ret.mean() / downside.std(ddof=1) * np.sqrt(TRADING_DAYS))


def _annualized_return(daily_ret: pd.Series) -> float:
    if len(daily_ret) == 0:
        return 0.0
    return float((1 + daily_ret.mean()) ** TRADING_DAYS - 1)


def _max_drawdown(equity: pd.Series) -> tuple[float, int]:
    if len(equity) < 2:
        return 0.0, 0
    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    max_dd = float(drawdown.min())
    # longest stretch below a prior peak, in calendar days
    underwater = drawdown < 0
    longest = 0
    start = None
    for day, uw in underwater.items():
        if uw and start is None:
            start = day
        elif not uw and start is not None:
            longest = max(longest, (day - start).days)
            start = None
    if start is not None:
        longest = max(longest, (underwater.index[-1] - start).days)
    return max_dd, int(longest)
