"""Overnight drift ("night effect") — the full close/open decomposition.

Trade the documented equity-index overnight premium on one ETF, gated by a
risk-on trend regime:

  Leg 1 (overnight LONG)  : buy at the session close (MOC), exit at the next
                            open (MOO). No stop — the market is closed — so the
                            position is sized off a gap budget, not a stop.
  Leg 2 (intraday SHORT)  : short at the open (MOO), cover at the close (MOC),
                            protected by an intraday ATR%-based stop.

Both legs fire only when the regime is risk-on: the most recent *completed*
daily close is above its 200-day SMA. All regime/vol inputs come from a
separate daily-bar series looked up strictly before the current session date,
so nothing here can see the future. See SPEC.md for the full contract.

Fill timing maps onto the core's FillTiming:
  - MOC (fill at the coming close)  -> decided on the 15:55 bar, NEXT_CLOSE
  - MOO (fill at the coming open)   -> decided on the 16:00 bar, NEXT_OPEN
"""

from __future__ import annotations

from datetime import date, time
from pathlib import Path

import numpy as np
import pandas as pd

from core.strategy import Action, Context, FillTiming, Order

REPO = Path(__file__).resolve().parents[2]


def _parse_time(hhmm: str) -> time:
    h, m = (int(x) for x in hhmm.split(":"))
    return time(h, m)


class OvernightDrift:
    def __init__(self, params: dict):
        # Decision bars. MOC orders are decided one bar before the close; the
        # MOO-for-next-open orders are decided on the closing (last) bar.
        self.close_decision_time = _parse_time(params.get("close_decision_time", "15:55"))
        self.session_close_time = _parse_time(params.get("session_close_time", "16:00"))

        self.sma_window = int(params.get("sma_window", 200))
        self.atr_window = int(params.get("atr_window", 20))
        self.overnight_vol_window = int(params.get("overnight_vol_window", 20))

        # Gap budget (overnight sizing basis): G = max(gap_vol_mult * sigma, gap_floor).
        self.gap_vol_mult = float(params.get("gap_vol_mult", 3.0))
        self.gap_floor = float(params.get("gap_floor", 0.05))
        # Intraday short stop: s = clip(atr_stop_mult * ATR%, stop_floor, stop_cap).
        self.atr_stop_mult = float(params.get("atr_stop_mult", 1.0))
        self.stop_floor = float(params.get("stop_floor", 0.0075))
        self.stop_cap = float(params.get("stop_cap", 0.03))

        self._daily = self._load_daily(params["daily_source"])

    # --- daily regime / volatility inputs (computed once, looked up causally) ---
    def _load_daily(self, source: str) -> pd.DataFrame:
        path = Path(source)
        if not path.is_absolute():
            path = REPO / path
        d = pd.read_parquet(path)
        # Index the daily inputs by ET calendar date for session-relative lookup.
        d = d.sort_index()
        d.index = pd.DatetimeIndex(d.index).tz_convert("America/New_York").date

        close, high, low, open_ = d["close"], d["high"], d["low"], d["open"]
        prev_close = close.shift(1)

        sma = close.rolling(self.sma_window).mean()
        regime_on = close > sma

        tr = pd.concat(
            [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
        ).max(axis=1)
        atr_pct = tr.rolling(self.atr_window).mean() / close

        overnight_ret = open_ / prev_close - 1.0
        sigma_overnight = overnight_ret.rolling(self.overnight_vol_window).std()

        out = pd.DataFrame(
            {"regime_on": regime_on, "atr_pct": atr_pct, "sigma_overnight": sigma_overnight}
        )
        return out

    def _prior_row(self, d: date) -> pd.Series | None:
        """The most recent daily row strictly before session date ``d``."""
        pos = self._daily.index.searchsorted(d, side="left")
        if pos == 0:
            return None
        return self._daily.iloc[pos - 1]

    def _regime_on(self, d: date) -> bool:
        row = self._prior_row(d)
        return bool(row is not None and row["regime_on"] == True)  # noqa: E712 (NaN-safe)

    def _gap_budget_frac(self, d: date) -> float:
        row = self._prior_row(d)
        sigma = float(row["sigma_overnight"]) if row is not None else np.nan
        if not np.isfinite(sigma):
            return self.gap_floor
        return max(self.gap_vol_mult * sigma, self.gap_floor)

    def _intraday_stop_frac(self, d: date) -> float:
        row = self._prior_row(d)
        atr_pct = float(row["atr_pct"]) if row is not None else np.nan
        if not np.isfinite(atr_pct):
            return self.stop_floor
        return float(np.clip(self.atr_stop_mult * atr_pct, self.stop_floor, self.stop_cap))

    # --- per-bar decision ---
    def on_bar(self, ctx: Context) -> list[Order]:
        now = ctx.now_et
        t = now.time()
        d = now.date()
        price = float(ctx.history["close"].iloc[-1])

        # 15:55 — schedule market-on-close fills at today's 16:00 close.
        if t == self.close_decision_time:
            orders: list[Order] = []
            # Always cover the intraday short (flat-by-close), regardless of regime.
            if not ctx.position.is_flat:
                orders.append(Order(Action.CLOSE, fill=FillTiming.NEXT_CLOSE, tag="cover_intraday"))
            # Establish tonight's overnight long only in a risk-on regime.
            if self._regime_on(d):
                g = self._gap_budget_frac(d) * price
                orders.append(
                    Order(
                        Action.ENTER_LONG,
                        stop_distance=g,
                        resting_stop=False,  # cannot stop overnight — G is a sizing basis
                        fill=FillTiming.NEXT_CLOSE,
                        tag="overnight_entry",
                    )
                )
            return orders

        # 16:00 (last bar) — schedule market-on-open fills at the next open.
        if t == self.session_close_time:
            orders = []
            # Always exit the overnight long at the open (overnight-only leg).
            if not ctx.position.is_flat:
                orders.append(Order(Action.CLOSE, fill=FillTiming.NEXT_OPEN, tag="overnight_exit"))
            # Enter the intraday short only in a risk-on regime.
            if self._regime_on(d):
                s = self._intraday_stop_frac(d) * price
                orders.append(
                    Order(
                        Action.ENTER_SHORT,
                        stop_distance=s,
                        resting_stop=True,
                        fill=FillTiming.NEXT_OPEN,
                        tag="intraday_entry",
                    )
                )
            return orders

        return []


def build(params: dict) -> OvernightDrift:
    return OvernightDrift(params)
