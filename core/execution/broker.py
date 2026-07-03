"""BacktestBroker: fills orders against bars and keeps the book.

Fill discipline (matches the SPEC, avoids lookahead):
- Market orders queued on bar *i* fill at the **open of bar i+1**. A strategy
  can never fill on the bar it made its decision on.
- A protective stop is placed ``stop_distance`` from the actual entry fill and
  rests until touched. If a later bar's range crosses it, it fills at the stop
  price with adverse stop-slippage (optimistic-but-flagged intrabar assumption,
  per SPEC).
- Time-exit CLOSE orders are processed at the next open *before* stops, so a
  scheduled flat always wins over a same-bar stop.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pandas as pd

from core.strategy import Action, Order, Position, Side

if TYPE_CHECKING:
    from core.backtest.costs import CostModel


@dataclass
class Fill:
    time: pd.Timestamp
    price: float
    qty: float  # signed: + buy, - sell
    commission: float
    slippage: float  # $ given up to spread + slippage vs the mid/ref price
    reason: str


@dataclass
class Trade:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    side: Side
    qty: float
    entry_price: float
    exit_price: float
    costs: float
    net_pnl: float
    exit_reason: str

    @property
    def day(self) -> object:
        return self.exit_time.tz_convert("America/New_York").date()


class BacktestBroker:
    def __init__(self, symbol: str, starting_cash: float, costs: CostModel):
        self.symbol = symbol
        self.cash = starting_cash
        self.costs = costs
        self._pos_qty = 0.0  # signed
        self._avg_price = 0.0
        self._stop_price: float | None = None
        self._stop_distance: float | None = None
        self._pending: list[Order] = []
        self._open_fill: Fill | None = None  # entry fill of the current trade
        self.trades: list[Trade] = []
        self.fills: list[Fill] = []

    # --- state exposed to the engine / risk / strategy ---
    def position(self) -> Position:
        if self._pos_qty == 0.0:
            return Position()
        side = Side.LONG if self._pos_qty > 0 else Side.SHORT
        return Position(side=side, qty=abs(self._pos_qty), avg_price=self._avg_price,
                        stop_price=self._stop_price)

    def equity(self, mark_price: float) -> float:
        return self.cash + self._pos_qty * mark_price

    def submit(self, order: Order) -> None:
        """Queue a (already risk-sized) order to fill at the next bar open."""
        self._pending.append(order)

    # --- per-bar processing, called by the engine in this order ---
    def process_open(self, bar: pd.Series, ts: pd.Timestamp) -> None:
        """Fill queued market orders at this bar's open."""
        if not self._pending:
            return
        open_px = float(bar["open"])
        for order in self._pending:
            if order.action is Action.CLOSE:
                self._close(open_px, ts, is_stop=False, reason=order.tag or "time_exit")
            elif order.action in (Action.ENTER_LONG, Action.ENTER_SHORT):
                if self._pos_qty != 0.0:
                    continue  # one position at a time
                self._open(order, open_px, ts)
        self._pending.clear()

    def check_stops(self, bar: pd.Series, ts: pd.Timestamp) -> None:
        """Fill a resting protective stop if this bar's range crosses it."""
        if self._pos_qty == 0.0 or self._stop_price is None:
            return
        low, high = float(bar["low"]), float(bar["high"])
        hit = (self._pos_qty > 0 and low <= self._stop_price) or (
            self._pos_qty < 0 and high >= self._stop_price
        )
        if hit:
            self._close(self._stop_price, ts, is_stop=True, reason="stop")

    # --- internal fill mechanics (signed cash accounting) ---
    def _open(self, order: Order, ref_px: float, ts: pd.Timestamp) -> None:
        is_buy = order.action is Action.ENTER_LONG
        qty = order.qty * (1 if is_buy else -1)
        price = self.costs.adverse_price(ref_px, is_buy=is_buy)
        comm = self.costs.commission(qty)
        slip = abs(price - ref_px) * abs(qty)
        self.cash -= qty * price + comm
        self._pos_qty = qty
        self._avg_price = price
        self._stop_distance = order.stop_distance
        if order.stop_distance is not None:
            sign = -1 if is_buy else 1
            self._stop_price = price + sign * order.stop_distance
        fill = Fill(ts, price, qty, comm, slip, reason=order.tag or "entry")
        self._open_fill = fill
        self.fills.append(fill)

    def _close(self, ref_px: float, ts: pd.Timestamp, is_stop: bool, reason: str) -> None:
        if self._pos_qty == 0.0:
            return
        is_buy = self._pos_qty < 0  # buy to cover a short
        price = self.costs.adverse_price(ref_px, is_buy=is_buy, is_stop=is_stop)
        close_qty = -self._pos_qty
        comm = self.costs.commission(close_qty)
        exit_slip = abs(price - ref_px) * abs(close_qty)
        self.cash -= close_qty * price + comm
        entry = self._open_fill
        side = Side.LONG if entry.qty > 0 else Side.SHORT
        gross = (price - entry.price) * entry.qty  # realized at actual (adverse) prices
        # costs = everything a frictionless mid-price fill would have saved.
        total_costs = entry.commission + comm + entry.slippage + exit_slip
        self.trades.append(
            Trade(
                entry_time=entry.time,
                exit_time=ts,
                side=side,
                qty=abs(entry.qty),
                entry_price=entry.price,
                exit_price=price,
                costs=total_costs,
                net_pnl=gross - entry.commission - comm,
                exit_reason=reason,
            )
        )
        self.fills.append(Fill(ts, price, close_qty, comm, exit_slip, reason=reason))
        self._pos_qty = 0.0
        self._avg_price = 0.0
        self._stop_price = None
        self._stop_distance = None
        self._open_fill = None
