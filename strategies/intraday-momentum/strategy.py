"""Intraday momentum (market intraday momentum / MIM).

Trade in the direction of the early-session return, entered late in the day,
flat by the close. See SPEC.md for the full contract; this file implements it
against the core ``Strategy`` interface.

Signal (all point-in-time, computed from today's bars only at the decision):
  r_ref     = P(ref_end) / session_open - 1
  sigma_open = stdev of the 5-min log-returns inside the reference window
  ATR_open  = mean true range of the reference-window bars
Entry at ``entry_time`` iff |r_ref| > k * sigma_open, direction = sign(r_ref),
stop at stop_mult * ATR_open from fill. Flat at ``exit_time``.
"""

from __future__ import annotations

from datetime import time

import numpy as np
import pandas as pd

from core.strategy import Action, Context, Order


def _parse_time(hhmm: str) -> time:
    h, m = (int(x) for x in hhmm.split(":"))
    return time(h, m)


class IntradayMomentum:
    def __init__(self, params: dict):
        self.entry_time = _parse_time(params.get("entry_time", "15:00"))
        self.exit_time = _parse_time(params.get("exit_time", "15:55"))
        self.ref_start = _parse_time(params.get("ref_start", "09:30"))
        self.ref_end = _parse_time(params.get("ref_end", "10:00"))
        self.k = float(params.get("k", 0.5))
        self.stop_mult = float(params.get("stop_mult", 2.0))
        self._traded_day = None  # ET date of the last entry (one entry/day)

    def on_bar(self, ctx: Context) -> list[Order]:
        now = ctx.now_et
        t = now.time()

        # Time exit takes precedence: flatten at the exit bar if still in.
        if t >= self.exit_time and not ctx.position.is_flat:
            return [Order(action=Action.CLOSE, tag="time_exit")]

        if t != self.entry_time:
            return []
        if not ctx.position.is_flat or self._traded_day == now.date():
            return []

        sig = self._signal(ctx)
        if sig is None:
            return []
        r_ref, sigma_open, atr_open = sig
        if sigma_open <= 0 or abs(r_ref) <= self.k * sigma_open:
            return []  # gate not met — sit out a low-conviction morning

        self._traded_day = now.date()
        action = Action.ENTER_LONG if r_ref > 0 else Action.ENTER_SHORT
        return [Order(action=action, stop_distance=self.stop_mult * atr_open, tag="mim_entry")]

    def _signal(self, ctx: Context) -> tuple[float, float, float] | None:
        today = ctx.today_et()
        if today.empty:
            return None
        times = pd.Index([ts.time() for ts in today.index])
        ref = today[(times > self.ref_start) & (times <= self.ref_end)]
        if len(ref) < 2 or self.ref_end not in list(times):
            return None

        session_open = float(today["open"].iloc[0])
        p_end = float(ref["close"].iloc[-1])
        r_ref = p_end / session_open - 1.0

        prev_close = np.concatenate([[session_open], ref["close"].to_numpy()[:-1]])
        log_ret = np.log(ref["close"].to_numpy() / prev_close)
        sigma_open = float(np.std(log_ret, ddof=1))

        true_range = np.maximum.reduce(
            [
                ref["high"].to_numpy() - ref["low"].to_numpy(),
                np.abs(ref["high"].to_numpy() - prev_close),
                np.abs(ref["low"].to_numpy() - prev_close),
            ]
        )
        atr_open = float(true_range.mean())
        return r_ref, sigma_open, atr_open


def build(params: dict) -> IntradayMomentum:
    return IntradayMomentum(params)
