"""ReplayBroker: drive the live loop over historical/synthetic bars.

This is a simulated ``LiveBroker`` so you can watch ``LiveRunner`` trade a full
session on demand — no market hours, no Alpaca account — while exercising the
exact same live code path (Context construction, strategy, risk sizing, order
handling).

Fill model matches *live* behaviour, not the backtest engine: a market order
placed right after a bar closes fills at that bar's close (plus costs), and a
protective stop is checked against each subsequent bar's range (as Alpaca's
server-side stop would be). This differs slightly from ``BacktestEngine``, which
fills at the next bar's open — the two answer different questions (what would
live have done vs. the historical backtest), so small differences are expected.
"""

from __future__ import annotations

import time as _time

import pandas as pd

from core.backtest.costs import CostModel
from core.execution.broker import Trade
from core.strategy import ET, Position, Side


class ReplayBroker:
    def __init__(self, symbol: str, bars: pd.DataFrame, starting_cash: float, costs: CostModel):
        self.symbol = symbol
        self.bars = bars
        self.costs = costs
        self.cash = starting_cash
        self._i = 0
        self._pos_qty = 0.0
        self._avg = 0.0
        self._stop_price: float | None = None
        self._entry: tuple | None = None  # (time, price, signed_qty, commission, slippage)
        self.trades: list[Trade] = []
        self._last_fill: float | None = None

    # --- simulation control ---
    def advance_to(self, i: int) -> None:
        """Move the clock to bar ``i`` and let a resting stop trigger on it."""
        self._i = i
        if self._pos_qty != 0.0 and self._stop_price is not None:
            bar = self.bars.iloc[i]
            low, high = float(bar["low"]), float(bar["high"])
            hit = (self._pos_qty > 0 and low <= self._stop_price) or (
                self._pos_qty < 0 and high >= self._stop_price
            )
            if hit:
                self._fill_close(self._stop_price, self.bars.index[i], is_stop=True, reason="stop")

    def _mark(self) -> float:
        return float(self.bars.iloc[self._i]["close"])

    def _now(self) -> pd.Timestamp:
        return self.bars.index[self._i]

    # --- LiveBroker interface ---
    def recent_bars(self, symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        return self.bars[self.bars.index <= end]

    def account(self) -> tuple[float, float]:
        return self.cash + self._pos_qty * self._mark(), self.cash

    def position(self, symbol: str) -> Position:
        if self._pos_qty == 0.0:
            return Position()
        side = Side.LONG if self._pos_qty > 0 else Side.SHORT
        return Position(side=side, qty=abs(self._pos_qty), avg_price=self._avg,
                        stop_price=self._stop_price)

    def submit_market(self, symbol: str, qty: float, is_buy: bool) -> str:
        ref = self._mark()
        price = self.costs.adverse_price(ref, is_buy=is_buy)
        signed = qty * (1 if is_buy else -1)
        comm = self.costs.commission(signed)
        slip = abs(price - ref) * abs(signed)
        if self._pos_qty == 0.0:
            self.cash -= signed * price + comm
            self._pos_qty = signed
            self._avg = price
            self._entry = (self._now(), price, signed, comm, slip)
        self._last_fill = price
        return "market"

    def wait_fill(self, order_id: str, timeout: float = 30.0) -> float:
        return self._last_fill

    def submit_stop(self, symbol: str, qty: float, is_buy: bool, stop_price: float) -> str:
        self._stop_price = stop_price
        return "stop"

    def cancel(self, order_id: str) -> None:
        self._stop_price = None

    def close_position(self, symbol: str) -> None:
        self._fill_close(self._mark(), self._now(), is_stop=False, reason="time_exit")

    def _fill_close(self, ref: float, ts: pd.Timestamp, is_stop: bool, reason: str) -> None:
        if self._pos_qty == 0.0 or self._entry is None:
            return
        is_buy = self._pos_qty < 0
        price = self.costs.adverse_price(ref, is_buy=is_buy, is_stop=is_stop)
        close_qty = -self._pos_qty
        comm = self.costs.commission(close_qty)
        slip = abs(price - ref) * abs(close_qty)
        self.cash -= close_qty * price + comm
        e_time, e_price, e_qty, e_comm, e_slip = self._entry
        self.trades.append(
            Trade(
                entry_time=e_time,
                exit_time=ts,
                side=Side.LONG if e_qty > 0 else Side.SHORT,
                qty=abs(e_qty),
                entry_price=e_price,
                exit_price=price,
                costs=e_comm + comm + e_slip + slip,
                net_pnl=(price - e_price) * e_qty - e_comm - comm,
                exit_reason=reason,
            )
        )
        self._pos_qty = 0.0
        self._avg = 0.0
        self._stop_price = None
        self._entry = None


def simulate(runner, broker: ReplayBroker, sleep: float = 0.0) -> list[Trade]:
    """Replay every bar through the live runner. Returns the trades produced."""
    for i in range(len(broker.bars)):
        broker.advance_to(i)
        runner.poll_once(broker.bars.index[i])
        if sleep:
            _time.sleep(sleep)
    # Safety: never leave the sim holding overnight.
    if broker._pos_qty != 0.0:
        broker._fill_close(broker._mark(), broker._now(), is_stop=False, reason="eod_flat")
    return broker.trades


def et_hhmm(ts: pd.Timestamp) -> str:
    return ts.tz_convert(ET).strftime("%Y-%m-%d %H:%M")
