"""fomc-drift — harvest the pre-FOMC announcement drift on SPY (daily bars).

Hold SPY long over the one implementable daily-bar window around each
*scheduled* FOMC announcement: MOC buy at ``close(T-1)`` -> MOC sell at
``close(T)``, where ``T`` is the announcement day (final day of the meeting).
Long-only, one position at a time, flat ~97% of days. Every rule (window,
scheduled-only, MOC both legs, unconditional entry, gap-budget sizing) is
pre-registered and LOCKED in SPEC.md — this strategy exposes NO tunable
params and ``build`` rejects any (orb discipline; no sweeps, ever).

The signal is a CALENDAR, known in advance — zero lookahead by construction.
No market data enters the entry/exit decision; market data enters only the
position size (completed daily bars, causally).

Daily-bar fill mapping (the off-by-one that must be exact) — the engine's
``FillTiming.NEXT_CLOSE`` fills at the close of the bar *after* the decision
bar, and every daily bar is a session close (bars re-stamped to 16:00 ET by
``scripts/build_spy_daily_moc.py``), so:

  * BUY MOC decided on bar ``T-2`` -> fills at ``close(T-1)``  (the entry)
  * SELL MOC decided on bar ``T-1`` -> fills at ``close(T)``   (the exit)

Both decisions use only the known-in-advance FOMC calendar and completed bars
strictly before the fill print. ``T-1`` and ``T-2`` are the exchange-calendar
sessions immediately before ``T`` (verified session-for-session against the
audited splice: zero mismatches across all 259 mapped events), so the engine
reconciles event-by-event to the pregate (``pregate_events_is.csv``).

On the announcement bar ``T-1`` the queued BUY (decided on ``T-2``) fills at
that bar's close *before* the strategy runs, so ``on_bar`` sees the long
position already open and queues the exit — one clean round trip per event.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from core.strategy import Action, Context, FillTiming, Order

REPO = Path(__file__).resolve().parents[2]
DEFAULT_CALENDAR = Path(__file__).resolve().parent / "fomc_calendar.csv"

# --- LOCKED constants (SPEC.md, sign-off 2026-07-06; never swept) ---
# Gap-budget sizing reused verbatim from overnight-long: G = max(3*sigma20, 5%).
GAP_VOL_MULT = 3.0        # 3 * trailing 20-day close-to-close stdev
GAP_FLOOR = 0.05          # 5% floor (binds in normal vol; the event is where tails live)
VOL_WINDOW = 20           # trailing 20 completed daily returns
# One tick sizing-basis floor, so a degenerate sigma can never divide by zero.
# With the no-leverage notional cap this floor can never change the sized qty.
MIN_GAP_FRAC = 1e-4


class FomcDrift:
    def __init__(self, calendar_source: str | Path = DEFAULT_CALENDAR):
        # Announcement days T (scheduled meetings only) and the two derived
        # decision days per event, all as ET dates known in advance.
        anns = self._load_announcements(calendar_source)
        self._buy_map, self._sell_days, self._sell_to_T = self._decision_days(anns)
        # Guard state: the announcement day T we are currently positioned for.
        self._await_T: date | None = None

    # --- calendar inputs (known in advance; no market data) ---
    @staticmethod
    def _load_announcements(source: str | Path) -> list[pd.Timestamp]:
        path = Path(source)
        if not path.is_absolute():
            path = REPO / path
        cal = pd.read_csv(path, parse_dates=["start_date", "end_date"])
        sched = cal[cal["type"] == "scheduled"]
        # T = end_date (the day the statement is released). Sorted, unique.
        return sorted(pd.Timestamp(t) for t in sched["end_date"].unique())

    @staticmethod
    def _decision_days(
        anns: list[pd.Timestamp],
    ) -> tuple[dict[date, date], set[date], dict[date, date]]:
        """Map each announcement T to its entry day T-1 and buy-decision day T-2.

        T-1 / T-2 are the exchange-calendar (XNYS) sessions immediately before
        T — the SPEC's definition ("last trading session strictly before T per
        the exchange calendar"). The exchange calendar is a published schedule
        known in advance, so consulting it is calendar knowledge, never
        lookahead. Uses its own early-start XNYS instance (core's cached one
        starts 2015; the IS window reaches back to 1994).

        Returns ``(buy_map, sell_days, sell_to_T)``:
          * ``buy_map``   : T-2 -> T-1  (bars where a BUY is decided)
          * ``sell_days`` : {T-1}       (bars where a SELL is decided)
          * ``sell_to_T`` : T-1 -> T    (the announcement each sell targets)
        """
        import exchange_calendars as xcals

        xnys = xcals.get_calendar("XNYS", start="1990-01-01")
        buy_map: dict[date, date] = {}    # T-2 -> T-1 (decide BUY here)
        sell_to_T: dict[date, date] = {}  # T-1 -> T   (decide SELL here)
        for T in anns:
            prev1 = xnys.previous_session(T)          # T-1
            prev2 = xnys.previous_session(prev1)      # T-2
            buy_map[prev2.date()] = prev1.date()
            sell_to_T[prev1.date()] = T.date()
        return buy_map, set(sell_to_T), sell_to_T

    # --- causal gap-budget sizing from completed daily bars ---
    def _gap_frac(self, history: pd.DataFrame) -> float:
        """G = max(3*sigma20, 5%) from the last VOL_WINDOW completed daily
        close-to-close returns (history ends at the decision bar, whose close is
        completed at the MOC decision time — the last completed close)."""
        close = history["close"]
        rets = close.pct_change().dropna()
        if len(rets) < VOL_WINDOW:
            return GAP_FLOOR  # not enough history yet -> the floor
        sigma = float(rets.iloc[-VOL_WINDOW:].std(ddof=1))
        if not np.isfinite(sigma):
            return GAP_FLOOR
        return max(max(GAP_VOL_MULT * sigma, GAP_FLOOR), MIN_GAP_FRAC)

    # --- per-bar decision ---
    def on_bar(self, ctx: Context) -> list[Order]:
        d = ctx.now_et.date()

        # Exit leg: on T-1 the BUY queued on T-2 has already filled at this
        # bar's close (process_close runs before on_bar), so we are long and
        # queue the MOC sell to fill at close(T). Unconditional — fires
        # regardless of P&L or what the Fed said.
        if d in self._sell_days and not ctx.position.is_flat:
            self._await_T = None
            return [Order(Action.CLOSE, fill=FillTiming.NEXT_CLOSE, tag="fomc_exit")]

        # Entry leg: on T-2, queue the MOC buy to fill at close(T-1). Sized off
        # the gap budget; no resting stop (a daily hold spanning a closed market
        # and the announcement day cannot be stopped — G is a sizing basis).
        if d in self._buy_map and ctx.position.is_flat:
            price = float(ctx.history["close"].iloc[-1])
            g = self._gap_frac(ctx.history) * price
            self._await_T = self._sell_to_T[self._buy_map[d]]
            return [
                Order(
                    Action.ENTER_LONG,
                    stop_distance=g,
                    resting_stop=False,
                    fill=FillTiming.NEXT_CLOSE,
                    tag="fomc_entry",
                )
            ]

        # Pathology guard: a position that outlives its announcement day (a data
        # gap swallowed the T-1 sell bar or the T close bar) violates the
        # one-event-per-hold contract — flatten at the first chance. Never fires
        # on the complete audited splice.
        if not ctx.position.is_flat and self._await_T is not None and d > self._await_T:
            self._await_T = None
            return [Order(Action.CLOSE, fill=FillTiming.NEXT_CLOSE, tag="stale_flat_guard")]

        return []


def build(params: dict) -> FomcDrift:
    # Zero tunable params (SPEC lock, no sweeps ever). Only the calendar file
    # location is accepted — a data-input path, not a knob — so tests can inject
    # a fixture; production runs pass nothing and use the committed calendar.
    allowed = {"calendar_source"}
    extra = set(params) - allowed
    if extra:
        raise ValueError(
            f"fomc-drift is fully pre-registered (SPEC lock); refusing params {sorted(extra)}"
        )
    return FomcDrift(**params)
