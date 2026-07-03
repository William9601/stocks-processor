"""Event-driven backtest loop.

For each bar, in order:
  1. fill previous bar's NEXT_OPEN orders at this bar's open;
  2. check the resting protective stop against this bar's range;
  3. fill previous bar's NEXT_CLOSE (market-on-close) orders at this bar's close;
  4. hand the strategy a point-in-time Context (bars up to *and including* this
     bar) and collect its order intents;
  5. size/veto each intent via risk, and queue survivors for the next bar.

Steps 1-3 settle only orders queued on *earlier* bars, so a strategy can never
fill on the bar it decided on: a decision made on this bar's close (step 4)
fills at the earliest on the next bar (its open or its close). Within a bar,
open precedes close, and a resting stop (step 2) is checked before the closing
auction (step 3).
"""

from __future__ import annotations

from dataclasses import dataclass

from core.backtest.costs import CostModel
from core.backtest.metrics import compute_metrics
from core.data.feed import DataFeed
from core.execution.broker import BacktestBroker, Trade
from core.risk.sizing import RiskManager
from core.strategy import Context, Strategy


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

        for i in range(len(bars)):
            bar = bars.iloc[i]
            ts = idx[i]

            # 1-3: settle the previous bar's decisions against this bar
            # (open fills, then resting stops, then market-on-close fills).
            self.broker.process_open(bar, ts)
            self.broker.check_stops(bar, ts)
            self.broker.process_close(bar, ts)

            # 4: point-in-time context (no future rows).
            close_px = float(bar["close"])
            equity = self.broker.equity(close_px)
            ctx = Context(
                symbol=symbol,
                history=bars.iloc[: i + 1],
                position=self.broker.position(),
                cash=self.broker.cash,
                equity=equity,
            )
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

        start_date = str(idx[0].tz_convert("America/New_York").date())
        end_date = str(idx[-1].tz_convert("America/New_York").date())
        metrics = compute_metrics(
            self.broker.trades, self.starting_cash, self.sample, start_date, end_date
        )
        return BacktestResult(
            trades=self.broker.trades,
            metrics=metrics,
            equity_end=self.broker.equity(float(bars.iloc[-1]["close"])),
        )
