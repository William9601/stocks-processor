# Architecture

Monorepo, Python ≥3.12, managed with `uv`. One shared core; strategies are thin
plugins on top of it. The point of this shape: every strategy runs through identical
data, cost, and risk machinery, so performance differences are attributable to the
strategy — not to who wired up their backtest more optimistically.

## Layout

```
core/
  data/        # ingestion, storage (parquet under data/), a single DataFeed API
  backtest/    # event-driven engine, cost models, metrics, walk-forward runner
  risk/        # position sizing, limits, kill switch — enforced OUTSIDE strategies
  execution/   # broker abstraction: BacktestBroker, PaperBroker, (LiveBroker later)
strategies/
  _template/   # SPEC.md template; copied by /new-strategy
  <name>/      # SPEC.md, strategy.py, config.yaml, tests/
experiments/   # committed run outputs; see experiments/README.md
data/          # market data cache, gitignored
```

## The Strategy contract

Every strategy implements the same minimal interface (to be created in
`core/strategy.py` when implementation starts):

```python
class Strategy(Protocol):
    def on_bar(self, ctx: Context) -> list[Order]: ...
```

- `Context` exposes point-in-time data only (bars up to and including the current
  one, current positions, cash). It is structurally incapable of serving future data —
  lookahead prevention lives in the interface, not in code review alone.
- Strategies emit `Order` intents; they never size positions or place trades directly.
  `core/risk` sizes and vetoes; `core/execution` fills.
- Strategy parameters come from the strategy's `config.yaml`, so backtests and
  paper trading run the exact same code with the exact same config file.

## Backtest engine choice (deferred)

Decision deliberately deferred until first implementation (ADR to follow). Options:
build a thin event-driven loop ourselves (~few hundred lines, full control, no dark
corners) vs. adopt `vectorbt`/`backtrader`/`nautilus_trader`. Whatever the choice, it
stays behind `core/backtest` so strategies never depend on it directly.

## Data

Start with end-of-day + intraday bars from a single provider (Alpaca, Polygon, or
Databento — decide when needed) cached as parquet in `data/`. `core/data` owns the
schema (UTC timestamps, explicit session calendar) so provider swaps don't touch
strategies.

## Broker

Paper trading first via a broker with a decent paper API (Alpaca is the usual
default). `LiveBroker` does not exist until paper results have validated backtests.
