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

import json
import time as _time
from pathlib import Path
from typing import Protocol

import pandas as pd

from core.data.calendar import next_session, session_close_et, session_open_et
from core.risk.sizing import RiskManager
from core.strategy import ET, Action, Context, FillTiming, Order, Position, Side, Strategy


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

    def submit_market(self, symbol: str, qty: float, is_buy: bool, tif: str = "day") -> str:
        """Market order; ``tif`` in {"day", "cls" (market-on-close), "opg"
        (market-on-open)}."""
        ...

    def wait_fill(self, order_id: str, timeout: float = 30.0) -> float: ...
    def submit_stop(self, symbol: str, qty: float, is_buy: bool, stop_price: float) -> str: ...
    def cancel(self, order_id: str) -> None: ...
    def close_position(self, symbol: str) -> None: ...

    def auction_prints(self, symbol: str, day) -> tuple[float | None, float | None]:
        """(official open, official close) prints for ``day``."""
        ...


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
        self.risk.on_bar(ctx)  # day-roll + breakers on every bar, not just order bars
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


class OvernightAuctionRunner:
    """Paper/live loop for the overnight MOC/MOO cycle (overnight-long).

    One call to :meth:`run` executes ONE full cycle on the paper account:

      afternoon  poll completed bars from launch (user starts ~15:25/15:30 ET);
                 when the strategy's decision bar arrives (session close minus
                 its offset, 15:40 on a full day) it emits an ENTER_LONG with
                 FillTiming.NEXT_CLOSE -> risk-size -> submit MOC (tif="cls",
                 must be in before the ~15:45 ET cutoff);
      close      wait for the auction fill, log it against the official close
                 print;
      overnight  sleep until the next session's pre-open;
      morning    submit the MOO exit (tif="opg") in the ~09:15-09:25 window,
                 wait for the opening-auction fill, log it against the official
                 open print, and return.

    If the gate says no entry, the cycle ends flat after the close. If started
    with a position already open (crash recovery), it skips straight to the
    morning exit. Every auction fill is appended to ``fill_log`` (JSONL):
    that log IS the paper-phase measurement of real MOC/MOO cost vs the
    2.9 bps round-trip hypothesis.
    """

    MOC_CUTOFF_MIN = 15  # stop trying to enter this many minutes before close
    OPG_SUBMIT_MIN = 15  # submit the MOO exit this many minutes before open

    def __init__(
        self,
        strategy: Strategy,
        risk: RiskManager,
        broker: LiveBroker,
        symbol: str,
        fill_log: str,
        poll_seconds: float = 30.0,
        on_event=None,
    ):
        self.strategy = strategy
        self.risk = risk
        self.broker = broker
        self.symbol = symbol
        self.fill_log = Path(fill_log)
        self.poll_seconds = poll_seconds
        self.on_event = on_event or (lambda msg: None)
        self._last_bar: pd.Timestamp | None = None
        # Injectable clock/sleep so the schedule logic is unit-testable.
        self._now = lambda: pd.Timestamp.now(tz="UTC")
        self._sleep = _time.sleep

    # --- fill log (append-only) ---
    def _log_fill(
        self,
        session_date,
        order_type: str,
        is_buy: bool,
        qty: float,
        order_id: str,
        fill_price: float | None,
        official: float | None,
    ) -> None:
        # Positive diff_bps = the fill cost money vs the official auction print.
        diff_bps = None
        if fill_price is not None and official:
            signed = (fill_price - official) if is_buy else (official - fill_price)
            diff_bps = signed / official * 1e4
        entry = {
            "logged_at": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"),
            "session_date": str(session_date),
            "symbol": self.symbol,
            "order_type": order_type,  # MOC | MOO
            "side": "buy" if is_buy else "sell",
            "qty": qty,
            "order_id": order_id,
            "fill_price": fill_price,
            "official_auction_price": official,
            "diff_bps": diff_bps,
        }
        self.fill_log.parent.mkdir(parents=True, exist_ok=True)
        with self.fill_log.open("a") as fh:
            fh.write(json.dumps(entry) + "\n")
        self.on_event(f"LOGGED {order_type} fill: {entry}")

    def _official_print(self, session_date, is_open: bool, retries: int = 6) -> float | None:
        """Official auction print for the day, retried while the daily bar
        propagates (can lag the auction by a minute or two)."""
        for _ in range(retries):
            open_px, close_px = self.broker.auction_prints(self.symbol, session_date)
            px = open_px if is_open else close_px
            if px:
                return px
            _time.sleep(20)
        return None

    # --- afternoon: decide + submit MOC ---
    def _poll_decision(self, now: pd.Timestamp) -> Order | None:
        """One poll: newest completed bar -> strategy. Returns a sized MOC
        entry order if this bar was the decision bar."""
        start = pd.Timestamp(f"{now.tz_convert(ET).date()} 09:30", tz=ET).tz_convert("UTC")
        bars = self.broker.recent_bars(self.symbol, start, now)
        if bars is None or bars.empty:
            return None
        last_ts = bars.index[-1]
        if self._last_bar is not None and last_ts <= self._last_bar:
            return None
        self._last_bar = last_ts

        day = now.tz_convert(ET).date()
        equity, cash = self.broker.account()
        ctx = Context(
            symbol=self.symbol,
            history=bars,
            position=self.broker.position(self.symbol),
            cash=cash,
            equity=equity,
            extra={"session_close_et": session_close_et(day)},
        )
        self.risk.on_bar(ctx)
        for order in self.strategy.on_bar(ctx):
            if order.action is Action.ENTER_LONG and order.fill is FillTiming.NEXT_CLOSE:
                sized = self.risk.size(order, ctx, ref_price=float(bars["close"].iloc[-1]))
                if sized is None:
                    self.on_event("VETO overnight entry (risk sizing / limits)")
                    return None
                return sized
        return None

    def _afternoon(self, today, close_et: pd.Timestamp) -> str | None:
        """Poll until the decision fires or the MOC cutoff passes. Returns the
        submitted MOC order id, or None for a flat night."""
        cutoff = close_et - pd.Timedelta(minutes=self.MOC_CUTOFF_MIN)
        while True:
            now = self._now()
            if now.tz_convert(ET) >= cutoff:
                self.on_event("no entry tonight (gate off or no decision bar before MOC cutoff)")
                return None
            sized = self._poll_decision(now)
            if sized is not None:
                oid = self.broker.submit_market(
                    self.symbol, sized.qty, is_buy=True, tif="cls"
                )
                self.on_event(f"MOC BUY {sized.qty} {self.symbol} submitted (id {oid})")
                return oid
            self._sleep(self.poll_seconds)

    # --- the one-cycle driver ---
    def _sleep_until(self, target_et: pd.Timestamp) -> None:
        while True:
            remaining = (target_et - self._now().tz_convert(ET)).total_seconds()
            if remaining <= 0:
                return
            self._sleep(min(remaining, 300.0))

    def run(self) -> None:
        today = self._now().tz_convert(ET).date()
        close_et = session_close_et(today)

        position = self.broker.position(self.symbol)
        if position.is_flat and close_et is not None:
            self.on_event(f"overnight cycle for {self.symbol}: session close {close_et.time()}")
            oid = self._afternoon(today, close_et)
            if oid is None:
                return  # flat night — nothing to measure
            # Wait out the closing auction, then log the entry fill.
            self._sleep_until(close_et)
            fill = self.broker.wait_fill(oid, timeout=300.0)
            position = self.broker.position(self.symbol)
            self._log_fill(
                today, "MOC", True, position.qty, oid, fill,
                self._official_print(today, is_open=False),
            )
        elif position.is_flat:
            self.on_event(f"{today} is not a trading session — nothing to do")
            return
        else:
            self.on_event(f"recovered an open position ({position.qty} {self.symbol}) — "
                          "skipping to the morning exit")

        # Overnight: hold until the next session's pre-open, then MOO out.
        exit_day = next_session(today)
        open_et = session_open_et(exit_day)
        self._sleep_until(open_et - pd.Timedelta(minutes=self.OPG_SUBMIT_MIN))

        position = self.broker.position(self.symbol)
        if position.is_flat:
            self.on_event("position already flat before the open — nothing to exit")
            return
        oid = self.broker.submit_market(self.symbol, position.qty, is_buy=False, tif="opg")
        self.on_event(f"MOO SELL {position.qty} {self.symbol} submitted (id {oid})")
        self._sleep_until(open_et)
        fill = self.broker.wait_fill(oid, timeout=600.0)
        self._log_fill(
            exit_day, "MOO", False, position.qty, oid, fill,
            self._official_print(exit_day, is_open=True),
        )
        self.on_event("overnight cycle complete — flat")
