"""Sharpe conventions: zero-filled session calendar vs legacy trade-days-only."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from core.backtest.metrics import compute_metrics
from core.execution.broker import Trade
from core.strategy import Side


def _trade(exit_day: str, pnl: float) -> Trade:
    # Trade.day is the EXIT date — pin it directly.
    exit_ = pd.Timestamp(f"{exit_day} 09:35", tz="America/New_York").tz_convert("UTC")
    entry = exit_ - pd.Timedelta(hours=17, minutes=35)
    return Trade(
        entry_time=entry, exit_time=exit_, side=Side.LONG, qty=10.0,
        entry_price=300.0, exit_price=300.0 + pnl / 10.0, costs=1.0,
        net_pnl=pnl, exit_reason="overnight_exit",
    )


def test_zero_fill_counts_gate_flat_sessions_in_sharpe():
    # Trades exit on 2 of 5 sessions; the other 3 are real 0% days.
    trades = [_trade("2024-06-03", 200.0), _trade("2024-06-05", -80.0)]
    sessions = [date(2024, 6, d) for d in (3, 4, 5, 6, 7)]
    m = compute_metrics(trades, 100_000.0, "is", "2024-06-04", "2024-06-10",
                        session_days=sessions)

    assert m["session_count"] == 5

    # Legacy convention: only the 2 trade days form the curve.
    eq_td = 100_000.0 + np.cumsum([200.0, -80.0])
    ret_td = np.diff(eq_td) / eq_td[:-1]
    # A single return has no stdev -> legacy sharpe is 0 here; use 3 trades
    # for a meaningful comparison below instead.
    assert m["sharpe_trade_days"] == 0.0

    trades = [_trade("2024-06-03", 200.0), _trade("2024-06-05", -80.0),
              _trade("2024-06-07", 150.0)]
    m = compute_metrics(trades, 100_000.0, "is", "2024-06-04", "2024-06-10",
                        session_days=sessions)

    # Zero-filled: returns over the 5-session calendar (4 pct-change points).
    eq = 100_000.0 + np.cumsum([200.0, 0.0, -80.0, 0.0, 150.0])
    ret = pd.Series(eq).pct_change().dropna()
    expected = float(ret.mean() / ret.std(ddof=1) * np.sqrt(252))
    assert abs(m["sharpe"] - expected) < 1e-12

    eq_td = 100_000.0 + np.cumsum([200.0, -80.0, 150.0])
    ret_td = pd.Series(eq_td).pct_change().dropna()
    expected_td = float(ret_td.mean() / ret_td.std(ddof=1) * np.sqrt(252))
    assert abs(m["sharpe_trade_days"] - expected_td) < 1e-12
    assert m["sharpe"] != m["sharpe_trade_days"]


def test_without_session_days_both_conventions_agree():
    trades = [_trade("2024-06-03", 200.0), _trade("2024-06-04", -80.0),
              _trade("2024-06-05", 150.0)]
    m = compute_metrics(trades, 100_000.0, "is", "2024-06-03", "2024-06-05")
    assert m["session_count"] is None
    assert m["sharpe"] == m["sharpe_trade_days"]


def test_off_calendar_trade_pnl_is_not_dropped():
    trades = [_trade("2024-06-03", 200.0)]
    sessions = [date(2024, 6, 4), date(2024, 6, 5)]  # trade day missing
    m = compute_metrics(trades, 100_000.0, "is", "2024-06-03", "2024-06-05",
                        session_days=sessions)
    assert abs(m["net_return"] - 200.0 / 100_000.0) < 1e-12
