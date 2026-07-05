"""AlpacaPaperBroker: the Alpaca-backed implementation of LiveBroker.

Paper trading only. This is the single place that imports ``alpaca-py`` (lazily,
so the backtest path never needs it) and the single place that talks to a real
account. Live trading is intentionally not implemented here.

Requires the ``paper`` extra (``uv sync --extra paper``) and credentials in the
environment (loaded from ``.env``): ALPACA_API_KEY, ALPACA_SECRET_KEY.

NOTE: This class cannot be exercised without live Alpaca credentials, so it is
covered by the LiveRunner unit tests via a fake broker, not directly. Treat its
first real run as a smoke test (see scripts/run_paper.py).
"""

from __future__ import annotations

import time as _time

import pandas as pd

from core.data.alpaca import bars_to_canonical, filter_rth
from core.data.calendar import filter_to_sessions
from core.strategy import Position, Side


class AlpacaPaperBroker:
    def __init__(self, api_key: str, secret_key: str, feed: str = "iex"):
        try:
            from alpaca.data.enums import DataFeed
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.trading.client import TradingClient
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise ImportError(
                "alpaca-py is required for paper trading. Install with: uv sync --extra paper"
            ) from exc

        # paper=True is not negotiable in this class — no live endpoint here.
        self._trading = TradingClient(api_key, secret_key, paper=True)
        self._data = StockHistoricalDataClient(api_key, secret_key)
        self._feed = DataFeed.SIP if feed.lower() == "sip" else DataFeed.IEX
        self._sip_realtime: bool | None = None  # probed lazily, see _has_realtime_sip

    # --- data ---
    def recent_bars(self, symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame(5, TimeFrameUnit.Minute),
            start=start.to_pydatetime(),
            end=end.to_pydatetime(),
            feed=self._feed,
        )
        bars = self._data.get_stock_bars(req)
        canonical = bars_to_canonical(bars.df, symbol, bar_minutes=5, timestamp="open")
        # filter_to_sessions drops after-hours prints past a half-day's 13:00
        # close that filter_rth's fixed 09:35..16:00 window would let through.
        return filter_to_sessions(filter_rth(canonical))

    # --- account / position ---
    def account(self) -> tuple[float, float]:
        acct = self._trading.get_account()
        return float(acct.equity), float(acct.cash)

    def position(self, symbol: str) -> Position:
        try:
            p = self._trading.get_open_position(symbol)
        except Exception:
            return Position()  # flat (Alpaca raises when there is no position)
        qty = float(p.qty)
        side = Side.LONG if qty > 0 else Side.SHORT
        return Position(side=side, qty=abs(qty), avg_price=float(p.avg_entry_price))

    # --- orders ---
    def submit_market(self, symbol: str, qty: float, is_buy: bool, tif: str = "day") -> str:
        """Market order. ``tif`` maps to Alpaca time-in-force: ``day`` (regular
        market order), ``cls`` (market-on-close — submit before ~15:45 ET),
        ``opg`` (market-on-open — submit before ~09:28 ET)."""
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        tif_map = {"day": "DAY", "cls": "CLS", "opg": "OPG"}
        order = self._trading.submit_order(
            MarketOrderRequest(
                symbol=symbol,
                qty=abs(qty),
                side=OrderSide.BUY if is_buy else OrderSide.SELL,
                time_in_force=TimeInForce[tif_map[tif.lower()]],
            )
        )
        return str(order.id)

    def _has_realtime_sip(self, symbol: str) -> bool:
        """Whether this key may query SIP data from the last ~15 minutes
        (Algo Trader Plus). Probed once with a latest-trade request and
        cached; a failed probe degrades to the free-tier recency clamp in
        auction_prints (slower but correct), never to an error."""
        if self._sip_realtime is None:
            from alpaca.data.enums import DataFeed
            from alpaca.data.requests import StockLatestTradeRequest

            try:
                self._data.get_stock_latest_trade(
                    StockLatestTradeRequest(symbol_or_symbols=symbol, feed=DataFeed.SIP)
                )
                self._sip_realtime = True
            except Exception:
                self._sip_realtime = False
        return self._sip_realtime

    def auction_prints(self, symbol: str, day) -> tuple[float | None, float | None]:
        """(official open, official close) of ``day``'s daily bar — the
        auction prints the paper fill log measures slippage against.

        Always fetched from SIP (an IEX daily bar is not the consolidated
        official print), independent of the bar feed. Recency handling is
        entitlement-aware: keys without real-time SIP cannot query the most
        recent ~15 minutes, so for them the request end is clamped to
        now-16min; entitled keys query right up to now. Right after an
        auction this returns (None, None) until the print is old enough —
        callers retry (see OvernightAuctionRunner._official_print)."""
        from alpaca.data.enums import DataFeed
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        from core.data.calendar import session_close_et, session_open_et

        start = pd.Timestamp(day).tz_localize("America/New_York").tz_convert("UTC")
        end = start + pd.Timedelta(days=1)
        now = pd.Timestamp.now(tz="UTC")
        if not self._has_realtime_sip(symbol):
            end = min(end, now - pd.Timedelta(minutes=16))
            if end <= start:
                return None, None
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=start.to_pydatetime(),
            end=end.to_pydatetime(),
            feed=DataFeed.SIP,
        )
        try:
            df = self._data.get_stock_bars(req).df
            if isinstance(df.index, pd.MultiIndex):
                df = df.xs(symbol, level=0)
            if df.empty:
                return None, None
            row = df.iloc[0]
        except Exception:
            return None, None
        # Partial-day guard (correct on ANY feed): the bar has a valid OPEN
        # once the opening print is inside the data window, but its CLOSE is
        # just the latest trade — only report each print once the data can
        # extend safely past it. The window ends at the request end on the
        # clamped free-tier path and at wall-clock now on the entitled path.
        lag = pd.Timedelta(minutes=5)
        window_end = min(end, now)
        open_et, close_et = session_open_et(day), session_close_et(day)
        open_px = float(row["open"]) if open_et is None or window_end >= open_et + lag else None
        close_px = float(row["close"]) if close_et is None or window_end >= close_et + lag else None
        return open_px, close_px

    def wait_fill(self, order_id: str, timeout: float = 30.0) -> float:
        deadline = _time.time() + timeout
        while _time.time() < deadline:
            order = self._trading.get_order_by_id(order_id)
            if order.filled_avg_price is not None and float(order.filled_qty or 0) > 0:
                return float(order.filled_avg_price)
            _time.sleep(0.5)
        raise TimeoutError(f"Order {order_id} not filled within {timeout}s")

    def submit_stop(self, symbol: str, qty: float, is_buy: bool, stop_price: float) -> str:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import StopOrderRequest

        order = self._trading.submit_order(
            StopOrderRequest(
                symbol=symbol,
                qty=abs(qty),
                side=OrderSide.BUY if is_buy else OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
                stop_price=round(stop_price, 2),
            )
        )
        return str(order.id)

    def cancel(self, order_id: str) -> None:
        try:
            self._trading.cancel_order_by_id(order_id)
        except Exception:
            pass  # already filled/cancelled

    def close_position(self, symbol: str) -> None:
        self._trading.close_position(symbol)
