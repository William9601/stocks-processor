# ADR 0004: Broker — Alpaca paper first, live behind an explicit flag

- **Date**: 2026-07-03
- **Status**: accepted

## Decision

Use **Alpaca** as the broker. Two implementations behind the common execution interface:

- `BacktestBroker` — implemented; fills against historical bars with the cost model.
- `PaperBroker` (Alpaca) — the next step; same interface, backed by Alpaca's paper
  account and live data. `LiveBroker` does not exist until paper results validate the
  backtest.

## Why

- Alpaca has a first-class paper API and the user already has a paper account.
- Keeping paper and backtest behind one interface means the strategy runs identically in
  both — the runner just constructs a different broker.

## Rules (enforced)

- **Paper before live. Live never by default.** Anything touching a live account requires
  an explicit, per-session confirmation from the user.
- **No API keys in the repo.** Alpaca keys live in `.env` (gitignored); the paper/live
  runner reads them from the environment.
- `alpaca-py` is an optional dependency (`pip install -e '.[paper]'`) — the backtest path
  never imports it.

## Status of the paper path

**Built.** `core/execution/live_runner.py` (`LiveRunner`) is the live/paper twin of the
backtest engine — it builds the identical `Context` and reuses the same strategy and
risk sizing. `core/execution/paper.py` (`AlpacaPaperBroker`) is the Alpaca-backed
`LiveBroker` implementation, and `scripts/run_paper.py` is the runner (paper-only, with
a per-session confirmation). The loop logic is unit-tested with a fake broker
(`core/tests/test_live_runner.py`); the Alpaca API surface (v0.43.x) is verified at
import/construction level.

**Remaining:** a credentialed smoke test — put paper keys in `.env`, `uv sync --extra
paper`, run one session (ideally on SIP data), and confirm real fills. Live trading
remains out of scope (separate future ADR + explicit flag).
