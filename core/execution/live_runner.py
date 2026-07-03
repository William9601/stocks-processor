"""Live/paper run loop — the streaming twin of the backtest engine.

Same strategy, same Context, same risk sizing as a backtest; the only
difference is that bars arrive from a broker in real time and orders go to a
real (paper) account. All broker I/O sits behind the :class:`LiveBroker`
protocol so this loop is unit-testable with a fake and carries no Alpaca
dependency itself.

Bar discipline mirrors the backtest: the strategy decides on a *completed* bar
and orders are placed immediately after — there is no future bar to peek at
because only closed bars are ever fetched.
"""

from __future__ import annotations

import time as _time
from typing import Protocol

import pandas as pd

from core.risk.sizing import RiskManager
from core.strategy import ET, Action, Context, Order, Position, Side, Strategy


class LiveBroker(Protocol):
    """Everything the loop needs from a broker, kept small and mockable."""

    def recent_bars(self, symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        """Completed bars in [start, end], canonical UTC/OHLCV schema."""
        ...

    def account(self) -> tuple[float, float]:
        """(equity, cash)."""
        ...

    def position(self, symbol: str) -> Position:
        """Current open position, or a flat Position."""
        ...

    def submit_market(self, symbol: str, qty: float, is_buy: bool) -> str: ...
    def wait_fill(self, order_id: str, timeout: float = 30.0) -> float: ...
    def submit_stop(self, symbol: str, qty: float, is_buy: bool, stop_price: float) -> str: ...
    def cancel(self, order_id: str) -> None: ...
    def close_position(self, symbol: str) -> None: ...


class LiveRunner:
    """Drives one strategy on one symbol against a live/paper broker."""

    def __init__(
        self,
        strategy: Strategy,
        risk: RiskManager,
        broker: LiveBroker,
        symbol: str,
        session_start: str = "09:30",
        on_event=None,
    ):
        self.strategy = strategy
        self.risk = risk
        self.broker = broker
        self.symbol = symbol
        self.session_start = session_start
        self.on_event = on_event or (lambda msg: None)
        self._last_bar: pd.Timestamp | None = None
        self._stop_order_id: str | None = None

    def _session_start_utc(self, now: pd.Timestamp) -> pd.Timestamp:
        et_now = now.tz_convert(ET)
        h, m = (int(x) for x in self.session_start.split(":"))
        start_et = et_now.normalize() + pd.Timedelta(hours=h, minutes=m)
        return start_et.tz_convert("UTC")

    def poll_once(self, now: pd.Timestamp) -> bool:
        """Process at most one newly-completed bar. Returns True if it acted."""
        bars = self.broker.recent_bars(self.symbol, self._session_start_utc(now), now)
        if bars is None or bars.empty:
            return False

        last_ts = bars.index[-1]
        if self._last_bar is not None and last_ts <= self._last_bar:
            return False  # no new completed bar since last poll
        self._last_bar = last_ts

        position = self.broker.position(self.symbol)
        if position.is_flat:
            self._stop_order_id = None  # server-side stop must have filled

        equity, cash = self.broker.account()
        ctx = Context(
            symbol=self.symbol,
            history=bars,
            position=position,
            cash=cash,
            equity=equity,
        )
        for order in self.strategy.on_bar(ctx):
            self._execute(order, ctx, ref_price=float(bars["close"].iloc[-1]))
        return True

    def _execute(self, order: Order, ctx: Context, ref_price: float) -> None:
        if order.action is Action.CLOSE:
            if self._stop_order_id is not None:
                self.broker.cancel(self._stop_order_id)
                self._stop_order_id = None
            self.broker.close_position(self.symbol)
            self.on_event(f"CLOSE {self.symbol} ({order.tag})")
            return

        sized = self.risk.size(order, ctx, ref_price=ref_price)
        if sized is None:
            self.on_event(f"VETO {order.action.value} (risk sizing / limits)")
            return

        is_buy = order.action is Action.ENTER_LONG
        oid = self.broker.submit_market(self.symbol, sized.qty, is_buy=is_buy)
        fill = self.broker.wait_fill(oid)
        self.on_event(f"ENTER {'LONG' if is_buy else 'SHORT'} {sized.qty} @ {fill:.4f}")

        if order.stop_distance:
            stop_price = fill - order.stop_distance if is_buy else fill + order.stop_distance
            self._stop_order_id = self.broker.submit_stop(
                self.symbol, sized.qty, is_buy=not is_buy, stop_price=stop_price
            )
            self.on_event(f"STOP {'sell' if is_buy else 'buy'} {sized.qty} @ {stop_price:.4f}")

    def run(self, poll_seconds: float = 30.0, until_et: str = "16:00") -> None:
        """Poll until the session-end time (ET). Paper trading only."""
        end_h, end_m = (int(x) for x in until_et.split(":"))
        self.on_event(f"live loop started for {self.symbol} (poll {poll_seconds}s)")
        while True:
            now = pd.Timestamp.now(tz="UTC")
            et = now.tz_convert(ET)
            if (et.hour, et.minute) >= (end_h, end_m):
                self.on_event("session end reached — stopping")
                return
            try:
                self.poll_once(now)
            except Exception as exc:  # keep the loop alive; surface the error
                self.on_event(f"ERROR in poll: {exc!r}")
            _time.sleep(poll_seconds)


def side_of(position: Position) -> Side | None:
    return position.side
