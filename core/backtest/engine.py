"""Event-driven backtest loop.

For each bar, in order:
  1. fill pending NEXT_OPEN orders at this bar's open;
  2. check the resting protective stop against this bar's range;
  3. if this bar is the session's final bar, fill pending NEXT_CLOSE
     (market-on-close) orders at its close — MOC orders rest until the
     closing auction, they never fill mid-session;
  4. hand the strategy a point-in-time Context (bars up to *and including* this
     bar) and collect its order intents;
  5. size/veto each intent via risk, and queue survivors.

Steps 1-3 settle only orders queued on *earlier* bars, so a strategy can never
fill on the bar it decided on: a decision made on this bar's close (step 4)
fills strictly later (the next bar's open, or this session's closing print).
Within a bar, open precedes close, and a resting stop (step 2) is checked
before the closing auction (step 3).

Sessions are calendar-aware: each date's true close comes from the XNYS
calendar (13:00 ET half-days included), the strategy sees it as
``ctx.extra["session_close_et"]``, and an MOC order that finds no
session-close bar expires at the session roll instead of filling on a later
day.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.backtest.costs import CostModel
from core.backtest.metrics import compute_metrics
from core.data.calendar import session_closes
from core.data.feed import DataFeed
from core.execution.broker import BacktestBroker, Trade
from core.risk.sizing import RiskManager
from core.strategy import ET, Context, FillTiming, Strategy


@dataclass
class BacktestResult:
    trades: list[Trade]
    metrics: dict
    equity_end: float


class BacktestEngine:
    def __init__(
        self,
        strategy: Strategy,
        feed: DataFeed,
        risk: RiskManager,
        costs: CostModel,
        starting_cash: float = 100_000.0,
        sample: str = "is",
    ):
        self.strategy = strategy
        self.feed = feed
        self.risk = risk
        self.broker = BacktestBroker(feed.symbol, starting_cash, costs)
        self.starting_cash = starting_cash
        self.sample = sample

    def run(self) -> BacktestResult:
        bars = self.feed.bars
        symbol = self.feed.symbol
        idx = bars.index
        et_index = idx.tz_convert(ET)
        # True close per session date (calendar knowledge, not price data).
        closes = session_closes(et_index)

        prev_day = None
        for i in range(len(bars)):
            bar = bars.iloc[i]
            ts = idx[i]
            day = et_index[i].date()
            if prev_day is not None and day != prev_day:
                # An MOC order that never met its session-close bar (data gap,
                # early close) must not fill on a later day's close.
                self.broker.expire_pending(FillTiming.NEXT_CLOSE)
            prev_day = day

            # 1-3: settle earlier decisions against this bar (open fills,
            # then resting stops, then — on the session-final bar — MOC fills).
            self.broker.process_open(bar, ts)
            self.broker.check_stops(bar, ts)
            self.broker.process_close(bar, ts, is_session_close=(et_index[i] == closes[day]))

            # 4: point-in-time context (no future rows).
            close_px = float(bar["close"])
            equity = self.broker.equity(close_px)
            ctx = Context(
                symbol=symbol,
                history=bars.iloc[: i + 1],
                position=self.broker.position(),
                cash=self.broker.cash,
                equity=equity,
                extra={"session_close_et": closes[day]},
            )
            # Risk sees every bar (day-roll + circuit breakers), not just
            # order-emitting ones — a sparse-order strategy would otherwise
            # never trip the daily-loss limit.
            self.risk.on_bar(ctx)
            orders = self.strategy.on_bar(ctx)

            # 5: size/veto and queue for the next bar.
            for order in orders:
                sized = self.risk.size(order, ctx, ref_price=close_px)
                if sized is not None:
                    self.broker.submit(sized)

        # Force-flat any position left dangling at the end of the series.
        if not self.broker.position().is_flat:
            last = bars.iloc[-1]
            self.broker._close(float(last["close"]), idx[-1], is_stop=False, reason="eod_flat")

        et_dates = idx.tz_convert("America/New_York").date
        session_days = sorted(set(et_dates))
        start_date = str(session_days[0])
        end_date = str(session_days[-1])
        metrics = compute_metrics(
            self.broker.trades,
            self.starting_cash,
            self.sample,
            start_date,
            end_date,
            session_days=session_days,
        )
        return BacktestResult(
            trades=self.broker.trades,
            metrics=metrics,
            equity_end=self.broker.equity(float(bars.iloc[-1]["close"])),
        )
