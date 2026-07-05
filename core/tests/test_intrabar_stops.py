"""Absolute intrabar stop semantics (orb SPEC, LOCKED) + DAY-order expiry.

The locked contract the pregate and the engine must agree on:
- the stop is live from the entry bar onward, including the entry bar itself;
- touch (bar range crosses the level) fills at the stop price;
- a bar that *opens* through the level fills at that bar's open, never at the
  stop price;
- an entry whose fill print is already at/through the level is cancelled — a
  position is never born stopped out.

The legacy relative-stop path (fill at stop price even on a gap-through) and
the rest-across-the-session-roll behavior of default orders are pinned here so
the extension stays additive.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.backtest.costs import CostModel
from core.backtest.engine import BacktestEngine
from core.data.feed import DataFeed
from core.execution.broker import BacktestBroker
from core.strategy import Action, Context, Order

ET = "America/New_York"


def _bars(day: str, rows: list[tuple[str, float, float, float, float]]) -> pd.DataFrame:
    """Bar frame from (close-stamp HH:MM, open, high, low, close) rows."""
    idx = pd.DatetimeIndex(
        [pd.Timestamp(f"{day} {hhmm}", tz=ET) for hhmm, *_ in rows]
    ).tz_convert("UTC")
    df = pd.DataFrame(
        [(o, h, lo, c, 1e5) for _, o, h, lo, c in rows],
        index=idx,
        columns=["open", "high", "low", "close", "volume"],
    )
    df.index.name = "ts"
    return df


def _broker(costs: CostModel | None = None) -> BacktestBroker:
    return BacktestBroker("QQQ", 100_000.0, costs or CostModel(0.0, 0.0, 0.0, 0.0))


def _step(broker: BacktestBroker, bars: pd.DataFrame, i: int) -> None:
    broker.process_open(bars.iloc[i], bars.index[i])
    broker.check_stops(bars.iloc[i], bars.index[i])


def test_absolute_stop_touch_fills_at_stop_price():
    bars = _bars("2024-06-03", [
        ("09:40", 100.0, 101.0, 100.0, 100.5),  # entry bar, no touch
        ("09:45", 100.4, 100.6, 98.9, 99.0),    # touches 99.0 from above
    ])
    costs = CostModel(0.0, 0.0, 0.0, stop_slippage_bps=1.0)
    b = _broker(costs)
    b.submit(Order(Action.ENTER_LONG, qty=10.0, stop_distance=1.0, stop_price=99.0))
    _step(b, bars, 0)
    assert b.position().stop_price == 99.0
    _step(b, bars, 1)
    trade = b.trades[0]
    assert trade.exit_reason == "stop"
    assert abs(trade.exit_price - 99.0 * (1 - 1.0 / 10_000)) < 1e-9


def test_absolute_stop_gap_through_fills_at_bar_open():
    bars = _bars("2024-06-03", [
        ("09:40", 100.0, 101.0, 100.0, 100.5),
        ("09:45", 98.0, 98.5, 97.5, 98.0),  # opens well below the 99.0 stop
    ])
    b = _broker()
    b.submit(Order(Action.ENTER_LONG, qty=10.0, stop_distance=1.0, stop_price=99.0))
    _step(b, bars, 0)
    _step(b, bars, 1)
    assert b.trades[0].exit_reason == "stop"
    assert b.trades[0].exit_price == 98.0  # bar open, never the stop price


def test_absolute_stop_gap_through_short_side():
    bars = _bars("2024-06-03", [
        ("09:40", 100.0, 100.2, 99.5, 99.8),
        ("09:45", 102.0, 102.5, 101.5, 102.0),  # opens above the 101.0 stop
    ])
    b = _broker()
    b.submit(Order(Action.ENTER_SHORT, qty=10.0, stop_distance=1.0, stop_price=101.0))
    _step(b, bars, 0)
    _step(b, bars, 1)
    assert b.trades[0].exit_reason == "stop"
    assert b.trades[0].exit_price == 102.0


def test_absolute_stop_is_live_on_the_entry_bar():
    bars = _bars("2024-06-03", [
        ("09:40", 100.0, 100.5, 98.5, 99.0),  # entry bar itself touches 99.5
    ])
    b = _broker()
    b.submit(Order(Action.ENTER_LONG, qty=10.0, stop_distance=0.5, stop_price=99.5))
    _step(b, bars, 0)
    assert b.position().is_flat
    assert b.trades[0].exit_reason == "stop"
    assert b.trades[0].exit_price == 99.5  # open (100.0) was above: touch, not gap


def test_born_stopped_entry_is_cancelled():
    bars = _bars("2024-06-03", [
        ("09:40", 99.0, 100.0, 98.5, 99.5),  # entry print 99.0 <= stop 99.0
    ])
    b = _broker()
    b.submit(Order(Action.ENTER_LONG, qty=10.0, stop_distance=1.0, stop_price=99.0))
    _step(b, bars, 0)
    assert b.position().is_flat
    assert b.trades == [] and b.fills == []
    assert len(b.cancels) == 1 and "born_stopped" in b.cancels[0][1]


def test_legacy_relative_stop_still_fills_at_stop_price_on_gap():
    """Byte-identity pin: the original relative-stop path is NOT given the
    gap-through rule — it keeps filling at the stop price."""
    bars = _bars("2024-06-03", [
        ("09:40", 100.0, 101.0, 100.0, 100.5),
        ("09:45", 97.0, 97.5, 96.5, 97.0),  # opens far through the stop
    ])
    b = _broker()
    b.submit(Order(Action.ENTER_LONG, qty=10.0, stop_distance=1.0))  # stop at 99.0
    _step(b, bars, 0)
    _step(b, bars, 1)
    assert b.trades[0].exit_reason == "stop"
    assert b.trades[0].exit_price == 99.0  # stop price, original behavior


def test_session_only_order_expires_at_session_roll():
    class _EnterOnLastBar:
        def __init__(self, session_only: bool):
            self.session_only = session_only
            self.done = False

        def on_bar(self, ctx: Context) -> list[Order]:
            # Decide on day 1's final bar: the NEXT bar is day 2's first bar.
            if not self.done and ctx.now_et.strftime("%H:%M") == "16:00":
                self.done = True
                return [Order(Action.ENTER_LONG, qty=5.0, stop_distance=1.0,
                              session_only=self.session_only)]
            return []

    def _day(day):
        idx = pd.date_range(f"{day} 09:35", f"{day} 16:00", freq="5min",
                            tz=ET).tz_convert("UTC")
        px = np.full(len(idx), 300.0)
        df = pd.DataFrame({"open": px, "high": px + 0.1, "low": px - 0.1,
                           "close": px, "volume": np.full(len(idx), 1e5)}, index=idx)
        df.index.name = "ts"
        return df

    bars = pd.concat([_day("2024-06-03"), _day("2024-06-04")])

    class _NoSizing:
        def on_bar(self, ctx):  # pre-sized orders pass through untouched
            return None

        def size(self, order, ctx, ref_price):
            return order

    # session_only: the stranded entry dies at the roll, no fill ever.
    eng = BacktestEngine(_EnterOnLastBar(True), DataFeed("QQQ", bars), _NoSizing(), CostModel())
    eng.run()
    assert eng.broker.fills == []
    assert any("session_expiry" in r for _, r in eng.broker.cancels)

    # default: the order rests across the roll and fills on day 2's open
    # (the behavior overnight-drift's MOO exit relies on).
    eng2 = BacktestEngine(_EnterOnLastBar(False), DataFeed("QQQ", bars), _NoSizing(), CostModel())
    eng2.run()
    assert eng2.broker.fills, "default order must still fill across the roll"
    first_fill_day = eng2.broker.fills[0].time.tz_convert(ET).date()
    assert str(first_fill_day) == "2024-06-04"
