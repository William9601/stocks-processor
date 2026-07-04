"""BacktestBroker: fills orders against bars and keeps the book.

Fill discipline (matches the SPEC, avoids lookahead):
- Orders queued on bar *i* fill on bar *i+1* — never on the bar the strategy
  decided on. The fill *site* on bar i+1 depends on the order's
  :class:`~core.strategy.FillTiming`: ``NEXT_OPEN`` fills at that bar's open (a
  market-on-open fill, the original behavior); ``NEXT_CLOSE`` fills at that
  bar's close (a market-on-close fill — the decision was committed on the prior
  bar's close, strictly before the fill print).
- A protective stop is placed ``stop_distance`` from the actual entry fill and
  rests until touched — but only when the entry order asked for one
  (``resting_stop``). If a later bar's range crosses it, it fills at the stop
  price with adverse stop-slippage (optimistic-but-flagged intrabar assumption,
  per SPEC). Positions that cannot be stopped (e.g. an overnight hold while the
  market is closed) size off ``stop_distance`` but place no resting stop.
- Time-exit CLOSE orders are processed at the next open *before* stops, so a
  scheduled flat always wins over a same-bar stop.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pandas as pd

from core.strategy import Action, FillTiming, Order, Position, Side

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
        """Queue a (already risk-sized) order to fill on the next bar."""
        self._pending.append(order)

    # --- per-bar processing, called by the engine in this order ---
    def process_open(self, bar: pd.Series, ts: pd.Timestamp) -> None:
        """Fill queued NEXT_OPEN orders at this bar's open."""
        self._fill_pending(FillTiming.NEXT_OPEN, float(bar["open"]), ts, is_close=False)

    def process_close(
        self, bar: pd.Series, ts: pd.Timestamp, is_session_close: bool = True
    ) -> None:
        """Fill queued NEXT_CLOSE (MOC) orders at this bar's close.

        A real MOC order fills only in the closing auction, so the engine
        passes ``is_session_close`` and fills happen only on the session's
        final bar — a decision bar earlier in the afternoon (e.g. 15:40, ahead
        of the broker's MOC submission cutoff) queues an order that rests
        until the close prints.
        """
        if not is_session_close:
            return
        self._fill_pending(FillTiming.NEXT_CLOSE, float(bar["close"]), ts, is_close=True)

    def expire_pending(self, timing: FillTiming) -> None:
        """Drop unfilled orders of one timing (engine calls this at session
        roll so an MOC order that never met a session-close bar dies rather
        than filling on a later day's close)."""
        self._pending = [o for o in self._pending if o.fill is not timing]

    def _fill_pending(
        self, timing: FillTiming, ref_px: float, ts: pd.Timestamp, is_close: bool
    ) -> None:
        """Fill the pending orders matching ``timing`` at ``ref_px``, in order.

        Orders of other timings are left queued. In-order iteration lets a
        ``[CLOSE, ENTER_*]`` pair flatten then re-enter on the same print (the
        overnight->intraday leg handoff).
        """
        if not self._pending:
            return
        remaining: list[Order] = []
        for order in self._pending:
            if order.fill is not timing:
                remaining.append(order)
                continue
            if order.action is Action.CLOSE:
                self._close(
                    ref_px, ts, is_stop=False, is_close=is_close, reason=order.tag or "time_exit"
                )
            elif order.action in (Action.ENTER_LONG, Action.ENTER_SHORT):
                if self._pos_qty != 0.0:
                    continue  # one position at a time
                self._open(order, ref_px, ts, is_close=is_close)
        self._pending = remaining

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
    def _open(self, order: Order, ref_px: float, ts: pd.Timestamp, is_close: bool = False) -> None:
        is_buy = order.action is Action.ENTER_LONG
        qty = order.qty * (1 if is_buy else -1)
        price = self.costs.adverse_price(ref_px, is_buy=is_buy, is_close=is_close)
        comm = self.costs.commission(qty)
        slip = abs(price - ref_px) * abs(qty)
        self.cash -= qty * price + comm
        self._pos_qty = qty
        self._avg_price = price
        self._stop_distance = order.stop_distance
        # Only rest a protective stop when the entry asked for one. A position
        # sized off stop_distance but with resting_stop=False (an un-stoppable
        # overnight hold) places no stop.
        if order.stop_distance is not None and order.resting_stop:
            sign = -1 if is_buy else 1
            self._stop_price = price + sign * order.stop_distance
        fill = Fill(ts, price, qty, comm, slip, reason=order.tag or "entry")
        self._open_fill = fill
        self.fills.append(fill)

    def _close(
        self,
        ref_px: float,
        ts: pd.Timestamp,
        is_stop: bool,
        reason: str,
        is_close: bool = False,
    ) -> None:
        if self._pos_qty == 0.0:
            return
        is_buy = self._pos_qty < 0  # buy to cover a short
        price = self.costs.adverse_price(ref_px, is_buy=is_buy, is_stop=is_stop, is_close=is_close)
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
