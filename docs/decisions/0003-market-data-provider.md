# ADR 0003: Market data provider — Alpaca for live, historical vendor for backtest

- **Date**: 2026-07-03
- **Status**: accepted

## Decision

Split data by stage:

- **Live / paper: Alpaca.** The first strategy (intraday-momentum) trades SPY, and the
  user already has an Alpaca paper account. Alpaca provides both the data feed and the
  paper/live broker, so one integration covers data → paper → live.
- **Backtest: a dedicated historical bar vendor** (Alpaca SIP export, Polygon, or
  Databento — final choice open), exported to parquet/CSV and loaded through
  `core/data`. The canonical UTC/OHLCV schema in `core/data` isolates strategies from
  the vendor, so this can be swapped without touching strategy code.

## Why

- Alpaca trades equities/ETFs but **not futures**, which is why v1 uses SPY (see the
  strategy SPEC) — but it means one vendor spans the whole live path.
- Free Alpaca data is IEX-only (~2–3% of consolidated volume) — too thin for
  cost-sensitive 5-min bars. Trustworthy backtests need full **SIP** data (Alpaca Algo
  Trader Plus tier, or another consolidated-tape vendor).

## Consequences

- Backtest and live may use different data sources; provenance in each experiment must
  record which vendor/feed produced the bars.
- A paid SIP data tier is required before any backtest number is trusted. Until then,
  `scripts/run_backtest.py` runs on clearly-labeled synthetic bars for plumbing only.

## Open

- Which historical vendor for the backtest (Alpaca SIP export vs Polygon vs Databento).
