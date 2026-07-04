"""Overnight-long — single-leg harvest of the equity-index overnight premium.

Buy a liquid index ETF at the regular-session close (MOC), hold through the
closed market, sell at the next regular-session open (MOO). Long-only,
overnight-only, flat during the day. Optionally gated by a risk-on trend
regime (hold only when the most recent completed daily close is above its
200-day SMA); the ungated variant holds every night.

This is the retired ``overnight-drift`` strategy with the intraday-short leg
removed — the short leg had no gross edge and carried the entire net loss, while
the overnight-long leg alone was ~breakeven under the same costs. See SPEC.md.

There is no intraday stop (the market is closed overnight), so the position is
sized off a gap budget rather than a stop, and rests no protective stop.

Decision times are OFFSETS from the session's true close (which the engine or
runner supplies as ``ctx.extra["session_close_et"]``; 13:00 ET on half-days),
never hardcoded clock times:

  - MOC entry: decided on the bar closing ``decision_offset_minutes`` before
    the session close (default 20 -> the 15:40 bar on a full day, safely ahead
    of Alpaca's ~15:45 MOC submission cutoff; 12:40 on a half-day). The order
    rests until the closing auction (FillTiming.NEXT_CLOSE fills only on the
    session-final bar). The regime gate uses the *prior day's* completed close,
    so deciding 20 minutes early loses no information.
  - MOO exit: decided on the session-close bar, fills at the next session's
    open (NEXT_OPEN).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from core.strategy import Action, Context, FillTiming, Order

REPO = Path(__file__).resolve().parents[2]


class OvernightLong:
    def __init__(self, params: dict):
        # Decision bar closes this many minutes before the session close.
        self.decision_offset = pd.Timedelta(minutes=int(params.get("decision_offset_minutes", 20)))

        self.use_regime_gate = bool(params.get("use_regime_gate", True))
        self.sma_window = int(params.get("sma_window", 200))
        self.overnight_vol_window = int(params.get("overnight_vol_window", 20))

        # Gap budget (overnight sizing basis): G = max(gap_vol_mult * sigma, gap_floor).
        self.gap_vol_mult = float(params.get("gap_vol_mult", 3.0))
        self.gap_floor = float(params.get("gap_floor", 0.05))

        self._daily = self._load_daily(params["daily_source"])

    # --- daily regime / gap-vol inputs (computed once, looked up causally) ---
    def _load_daily(self, source: str) -> pd.DataFrame:
        path = Path(source)
        if not path.is_absolute():
            path = REPO / path
        d = pd.read_parquet(path).sort_index()
        d.index = pd.DatetimeIndex(d.index).tz_convert("America/New_York").date

        close, open_ = d["close"], d["open"]
        prev_close = close.shift(1)

        regime_on = close > close.rolling(self.sma_window).mean()
        overnight_ret = open_ / prev_close - 1.0
        sigma_overnight = overnight_ret.rolling(self.overnight_vol_window).std()

        return pd.DataFrame({"regime_on": regime_on, "sigma_overnight": sigma_overnight})

    def _prior_row(self, d: date) -> pd.Series | None:
        """The most recent daily row strictly before session date ``d``."""
        pos = self._daily.index.searchsorted(d, side="left")
        if pos == 0:
            return None
        return self._daily.iloc[pos - 1]

    def _hold_tonight(self, d: date) -> bool:
        if not self.use_regime_gate:
            return True
        row = self._prior_row(d)
        return bool(row is not None and row["regime_on"] == True)  # noqa: E712 (NaN-safe)

    def _gap_budget_frac(self, d: date) -> float:
        row = self._prior_row(d)
        sigma = float(row["sigma_overnight"]) if row is not None else np.nan
        if not np.isfinite(sigma):
            return self.gap_floor
        return max(self.gap_vol_mult * sigma, self.gap_floor)

    # --- per-bar decision ---
    def on_bar(self, ctx: Context) -> list[Order]:
        now = ctx.now_et
        session_close = ctx.extra.get("session_close_et")
        if session_close is None:  # no calendar supplied: assume a full 16:00 session
            session_close = now.normalize() + pd.Timedelta(hours=16)

        # close - offset — enter the overnight long at today's close (MOC), if holding.
        if now == session_close - self.decision_offset:
            d = now.date()
            if ctx.position.is_flat and self._hold_tonight(d):
                price = float(ctx.history["close"].iloc[-1])
                g = self._gap_budget_frac(d) * price
                return [
                    Order(
                        Action.ENTER_LONG,
                        stop_distance=g,
                        resting_stop=False,  # cannot stop overnight — G is a sizing basis
                        fill=FillTiming.NEXT_CLOSE,
                        tag="overnight_entry",
                    )
                ]
            return []

        # Session-close bar — exit the overnight long at the next open (MOO).
        if now == session_close:
            if not ctx.position.is_flat:
                return [Order(Action.CLOSE, fill=FillTiming.NEXT_OPEN, tag="overnight_exit")]
            return []

        return []


def build(params: dict) -> OvernightLong:
    return OvernightLong(params)
