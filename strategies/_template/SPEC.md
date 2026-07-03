# Strategy: <name>

- **Status**: draft | approved | implemented | paper | retired
- **Created**: <YYYY-MM-DD>
- **One-liner**: <what it does in one sentence>

## Hypothesis

What inefficiency is exploited, why does it exist, and who is losing money to us?
If you can't answer the mechanism question, the strategy is data-mined.

## Universe & timeframe

- Instruments:
- Bar size / data resolution:
- Trading session (hours, timezone):
- Holding period (intraday only? overnight allowed?):

## Signals

Entry and exit rules, exact enough that two independent implementations would agree.
Every indicator gets a formula and parameters.

- Entry:
- Exit (profit):
- Exit (stop):
- Exit (time — e.g., flat by session close):

## Risk

- Position sizing rule:
- Max concurrent positions:
- Per-trade stop:
- Daily loss limit:
- Max drawdown kill switch:

## Data requirements

- Data types (bars, quotes, news, fundamentals):
- History depth needed:
- Source:

## Cost assumptions

- Commission:
- Spread / slippage model:

## Success criteria (locked before first backtest)

- Minimum out-of-sample Sharpe:
- Maximum drawdown tolerated:
- Minimum trade count for significance:
- In-sample window:            Out-of-sample window:

## Known failure modes

Regimes where this should lose, and what limits the damage.
