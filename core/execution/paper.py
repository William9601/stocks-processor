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

from core.data.feed import load_bars
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
        df = bars.df
        if df is None or df.empty:
            return pd.DataFrame()
        # Alpaca returns a (symbol, timestamp) MultiIndex; flatten to timestamp.
        if isinstance(df.index, pd.MultiIndex):
            df = df.xs(symbol, level=0)
        df = df.reset_index().rename(columns={"timestamp": "ts"})
        return load_bars(df)

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
    def submit_market(self, symbol: str, qty: float, is_buy: bool) -> str:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        order = self._trading.submit_order(
            MarketOrderRequest(
                symbol=symbol,
                qty=abs(qty),
                side=OrderSide.BUY if is_buy else OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
            )
        )
        return str(order.id)

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
