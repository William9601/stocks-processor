"""Engine invariants: no lookahead, next-bar-open fills, risk veto."""

from __future__ import annotations

from core.backtest.costs import CostModel
from core.backtest.engine import BacktestEngine
from core.data.feed import DataFeed
from core.data.synthetic import make_intraday_bars
from core.execution.broker import BacktestBroker
from core.risk.sizing import RiskLimits, RiskManager
from core.strategy import Action, Context, FillTiming, Order, Side


class _Probe:
    """Records what each Context exposed; never trades."""

    def __init__(self):
        self.seen: list[tuple] = []

    def on_bar(self, ctx: Context) -> list[Order]:
        self.seen.append((ctx.now, ctx.history.index[-1], len(ctx.history)))
        return []


def _feed(days=5):
    bars = make_intraday_bars(days=days, momentum=0.0)
    return DataFeed("SPY", bars)


def test_context_never_sees_the_future():
    feed = _feed()
    probe = _Probe()
    BacktestEngine(probe, feed, RiskManager(), CostModel()).run()

    # Current bar is always the last visible row, and history grows by one.
    for i, (now, last, length) in enumerate(probe.seen):
        assert now == last
        assert length == i + 1
    assert len(probe.seen) == len(feed.bars)


class _EnterOnce:
    """Enters long on the very first bar, then does nothing."""

    def __init__(self):
        self.done = False

    def on_bar(self, ctx):
        if not self.done:
            self.done = True
            return [Order(action=Action.ENTER_LONG, stop_distance=1.0, tag="t")]
        return []


def test_market_order_fills_at_next_bar_open():
    feed = _feed()
    costs = CostModel(half_spread_bps=1.0, slippage_bps=1.0)
    engine = BacktestEngine(_EnterOnce(), feed, RiskManager(), costs)
    engine.run()

    entry = engine.broker.fills[0]
    idx = feed.bars.index
    assert entry.time == idx[1]  # decided on bar 0, filled on bar 1
    expected = float(feed.bars.iloc[1]["open"]) * (1 + 2 / 10_000)
    assert abs(entry.price - expected) < 1e-6


class _EnterOnceMOC:
    """Enters long once with a market-on-close fill and no resting stop."""

    def __init__(self):
        self.done = False

    def on_bar(self, ctx):
        if not self.done:
            self.done = True
            return [
                Order(
                    action=Action.ENTER_LONG,
                    stop_distance=1.0,
                    resting_stop=False,
                    fill=FillTiming.NEXT_CLOSE,
                    tag="moc",
                )
            ]
        return []


def test_market_on_close_fills_at_session_close():
    feed = _feed()
    costs = CostModel(half_spread_bps=1.0, slippage_bps=1.0, close_slippage_bps=2.0)
    engine = BacktestEngine(_EnterOnceMOC(), feed, RiskManager(), costs)
    engine.run()

    entry = engine.broker.fills[0]
    # Decided on bar 0 (09:35), the MOC order rests until the closing auction:
    # it fills at the CLOSE of the session's final bar, never mid-session.
    session_last = feed.bars.index[feed.bars.index.tz_convert("America/New_York").date
                                   == feed.bars.index[0].tz_convert("America/New_York").date()][-1]
    assert entry.time == session_last
    close_px = float(feed.bars.loc[session_last, "close"])
    expected = close_px * (1 + (1.0 + 2.0) / 10_000)  # close-auction bps
    assert abs(entry.price - expected) < 1e-6


def test_unfilled_moc_expires_at_session_roll():
    """An MOC order whose session-close bar never arrives (truncated data)
    must die at the session roll, not fill on a later day's close."""
    import numpy as np
    import pandas as pd

    def _day(day, end):
        idx = pd.date_range(f"{day} 09:35", f"{day} {end}", freq="5min",
                            tz="America/New_York").tz_convert("UTC")
        px = np.full(len(idx), 300.0)
        return pd.DataFrame({"open": px, "high": px, "low": px, "close": px,
                             "volume": np.full(len(idx), 1e5)}, index=idx)

    # Real XNYS sessions; day 1's data is truncated at 15:55 (no 16:00 bar).
    bars = pd.concat([_day("2024-06-03", "15:55"), _day("2024-06-04", "16:00")])
    bars.index.name = "ts"
    engine = BacktestEngine(_EnterOnceMOC(), DataFeed("SPY", bars), RiskManager(), CostModel())
    engine.run()
    assert engine.broker.fills == []
    assert engine.broker.trades == []


def test_resting_stop_false_places_no_stop():
    """An un-stoppable entry sizes off stop_distance but rests no protective stop."""
    feed = _feed()
    broker = BacktestBroker("SPY", 100_000.0, CostModel())
    broker.submit(
        Order(action=Action.ENTER_LONG, qty=10.0, stop_distance=1.0, resting_stop=False)
    )
    bar, ts = feed.bars.iloc[0], feed.bars.index[0]
    broker.process_open(bar, ts)  # fills at this bar's open (NEXT_OPEN default)
    assert broker.position().qty == 10.0
    assert broker.position().stop_price is None  # no stop despite stop_distance


def test_close_then_enter_flip_on_same_print():
    """A [CLOSE, ENTER_SHORT] pair queued together flips the book on one open."""
    feed = _feed()
    broker = BacktestBroker("SPY", 100_000.0, CostModel())
    # Start long.
    broker.submit(Order(action=Action.ENTER_LONG, qty=5.0, stop_distance=1.0))
    broker.process_open(feed.bars.iloc[0], feed.bars.index[0])
    assert broker.position().side is Side.LONG
    # Flip: close the long and open a short at the very next open, in one batch.
    broker.submit(Order(action=Action.CLOSE))
    broker.submit(Order(action=Action.ENTER_SHORT, qty=7.0, stop_distance=1.0))
    broker.process_open(feed.bars.iloc[1], feed.bars.index[1])
    assert broker.position().side is Side.SHORT
    assert broker.position().qty == 7.0


def test_risk_vetoes_when_stop_too_wide_for_account():
    feed = _feed()
    # Tiny account: risking 0.5% on a huge stop distance -> 0 shares -> veto.
    risk = RiskManager(RiskLimits(risk_per_trade=0.005))
    engine = BacktestEngine(_EnterOnce(), feed, risk, CostModel(), starting_cash=100.0)
    engine.run()
    assert engine.broker.trades == []


def test_context_now_is_eastern_close():
    feed = _feed(days=1)
    probe = _Probe()
    BacktestEngine(probe, feed, RiskManager(), CostModel()).run()
    first_close = feed.bars.index[0].tz_convert("America/New_York")
    assert first_close.strftime("%H:%M") == "09:35"
