"""Opening range breakout (orb) — 5-minute ORB on QQQ, EoD-only exit.

Trade in the direction of the completed 09:30-09:35 ET bar from the open of
the second bar; absolute stop at the opening bar's opposite extreme (broker
intrabar semantics, LOCKED in SPEC.md); forced flat at the open of the
session's final 5-minute bar. One trade per day, no re-entry, both directions.

Every parameter (5-minute range, direction rule, stop placement, EoD exit)
is pre-registered and LOCKED in SPEC.md (Decisions record 2026-07-05), so
this strategy intentionally exposes NO tunable params — no duration sweeps,
ever. ``build`` rejects any attempt to pass some.

Fill mapping onto the core:
  - signal on bar 1 (close-stamped 09:35) -> NEXT_OPEN entry at bar 2's open
  - Order.stop_price = L1/H1: born-stopped cancel, touch -> stop price,
    gap-through -> bar open (core intrabar semantics)
  - EoD: CLOSE decided on the (session_close - 5min) bar -> NEXT_OPEN fill at
    the final bar's open (15:55 ET print on full days, 12:55 on early closes)
  - session_only entries: a data gap can never turn the entry into an
    overnight fill
"""

from __future__ import annotations

from datetime import time, timedelta

from core.strategy import Action, Context, Order

BAR1_STAMP = time(9, 35)  # close-stamp of the 09:30-09:35 ET opening bar (LOCKED)
BAR_MINUTES = 5
# Sizing-basis floor of one tick. The sizing estimate |C1 - stop| can be 0
# when bar 1 closes exactly at its extreme, which would veto a trade the
# entry print may still validly take (entry is O2, not C1). With the
# no-leverage notional cap the floor can never change the sized qty: for any
# stop distance under ~R * price the cap branch binds.
MIN_STOP_ESTIMATE = 0.01


class Orb:
    def __init__(self):
        self._signal_day = None  # ET date of the last entry emission

    def on_bar(self, ctx: Context) -> list[Order]:
        now = ctx.now_et
        d = now.date()

        # Pathology guard: a position surviving past its entry session (data
        # gap swallowed the EoD decision bar, or a stale book at restart)
        # violates the never-overnight contract — flatten at the first
        # opportunity. Never fires on clean data.
        if not ctx.position.is_flat and self._signal_day != d:
            return [Order(Action.CLOSE, tag="gap_flat_guard")]

        session_close = ctx.extra["session_close_et"]
        eod_decision = session_close - timedelta(minutes=BAR_MINUTES)

        # EoD exit: decided one bar before the close, fills at the open of
        # the session's final bar (calendar-aware, early closes included).
        if not ctx.position.is_flat and now >= eod_decision:
            return [Order(Action.CLOSE, tag="eod_flat")]

        # Entry evaluation: exactly once per session, on bar 1 only.
        if now.time() != BAR1_STAMP or now >= eod_decision:
            return []
        if not ctx.position.is_flat or self._signal_day == d:
            return []
        today = ctx.today_et()
        if len(today) != 1:
            return []  # bar 1 missing (first bar of the day is a later stamp)

        bar1 = today.iloc[0]
        o1, h1 = float(bar1["open"]), float(bar1["high"])
        l1, c1 = float(bar1["low"]), float(bar1["close"])
        if c1 == o1 or h1 == l1:
            return []  # doji / zero-range skip

        long_side = c1 > o1
        stop_level = l1 if long_side else h1
        self._signal_day = d
        return [
            Order(
                Action.ENTER_LONG if long_side else Action.ENTER_SHORT,
                stop_distance=max(abs(c1 - stop_level), MIN_STOP_ESTIMATE),
                stop_price=stop_level,
                session_only=True,
                tag="orb_entry",
            )
        ]


def build(params: dict) -> Orb:
    if params:
        raise ValueError(
            f"orb is fully pre-registered (SPEC lock); refusing params {sorted(params)}"
        )
    return Orb()
