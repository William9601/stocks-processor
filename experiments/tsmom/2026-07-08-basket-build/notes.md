# TSMOM basket build — 2026-07-08

Data pipeline for the multi-asset time-series-momentum candidate, which passed the
research screen 2026-07-08 (`experiments/tsmom/2026-07-08-research-screen/prereg.md`).
No spec or strategy code yet — this is the data-infra step the screen authorized.

Builder: `scripts/build_tsmom_basket.py`. Audit evidence: `basket_report.json` (this
dir). Series: `data/tsmom/<TICKER>_daily_adj.parquet` (gitignored — `/data` is never
committed; re-run the builder to regenerate).

## Basket (the screen's diversified set — four asset classes)

| Class | Instruments | Why |
|---|---|---|
| Equity | SPY, EFA, EEM | US large cap, developed ex-US, emerging |
| Bonds | IEF, TLT | 7–10y and 20y+ US Treasuries |
| Commodity | DBC, GLD | broad commodities, gold |
| FX | UUP | US dollar index (bullish) |

**Common start = 2007-03-01** (UUP inception is the binding constraint). The
2007→present window deliberately spans the regimes the screen requires the eventual
OOS to include: 2008, the 2011–2019 lean decade, 2020 COVID, the 2022 revival, and the
2024–2025 drawdown — no way to cherry-pick only the good years. Individual series carry
their full history back to 2003 (2004/2006 for GLD/DBC) for lookback warm-up.

## Method (house data discipline: raw prints + self-adjust + audit)

Base = Yahoo `auto_adjust=False` Close/OHLC, which is **split-adjusted but
dividend-unadjusted**. Self-apply a CRSP total-return back-adjustment
(`1 − dist/prev_close` per ex-date, anchored at the latest bar) from the distribution
record = **Dividends + Capital Gains** (commodity/bond ETFs distribute cap gains with
ex-dates; both are cash off NAV). Alpaca SIP is a cross-check only, never in the price
path.

**The one landmine — split × dividend basis — verified empirically before trusting it.**
EEM (and EFA) have 3:1 splits in-sample. Yahoo's Close is split-adjusted to the current
basis, *and its Dividends are reported on that same basis*: raw dividend ÷ split-adjusted
prev_close reproduces Yahoo's own adjustment step to <0.02 bps across the EEM splits, so
**no split conversion of the distribution is applied**. (A first pass that divided
dividends by the trailing split factor was wrong and was caught by audit-2 failing only
on the two split names — the audit did its job.) For the six split-free instruments the
method is identical to the SPY EOD splice.

## Audits — all PASS

1. **Per-event distribution audit** — our per-ex-date factor vs Yahoo's own
   (reciprocal of the Adj Close/Close step). Zero disputed events across all 8.
2. **Self-adjust vs Yahoo Adj Close** (full overlap, boundary-rescaled) — the strict
   arithmetic bar. **Daily-return divergence max ≤ 0.02 bps for every instrument**,
   including EEM/EFA post-fix. Our total-return construction equals Yahoo's to rounding.
3. **Cross-vendor vs Alpaca SIP `adjustment=all`, 2016+** — sanity guard on *typical*
   agreement (median < 2 bps, p99 < 25 bps), not the worst day. **Median 0.0–1.6 bps
   for all 8.** The few >25 bps days are COVID-crash sessions and ex-div dates where
   Alpaca's print / ex-div handling differs — expected, and Alpaca is not in the price
   path. Largest-divergence dates are listed per instrument in the report.

## Economic sanity (2007-03 → 2026-07, common window)

Confirms the series are correct across crises and, crucially, that the cross-asset
**diversification structure TSMOM depends on is present**:

| tk | CAGR% | Sharpe | corr(SPY) | 2008 | 2022 |
|----|------:|-------:|----------:|-----:|-----:|
| SPY | 13.2 | 0.67 | 1.00 | −36.2 | −18.6 |
| EFA | 7.4 | 0.34 | 0.89 | −40.8 | −14.9 |
| EEM | 9.5 | 0.34 | 0.82 | −48.0 | −21.1 |
| IEF | 3.4 | 0.49 | −0.30 | +17.1 | −14.4 |
| TLT | 4.0 | 0.26 | −0.31 | +32.0 | −29.4 |
| DBC | 3.5 | 0.18 | 0.40 | −33.6 | +18.9 |
| GLD | 11.2 | 0.62 | 0.06 | +2.0 | +0.8 |
| UUP | 2.0 | 0.25 | −0.19 | +5.8 | +8.8 |

2008 flight-to-quality (equities down, Treasuries +17/+32, USD +5.8), the 2022 bond
crash (TLT −29.4) alongside commodity/USD strength (DBC +18.9, UUP +8.8), and the
negative bond / near-zero gold / negative USD correlations to SPY all check out.

## Status / next

Basket data is built, audited, and loads through the engine's canonical loader
(`core.data.feed.load_bars` → UTC `ts` index, OHLCV, monotonic + unique). **This does
not touch the strategy edge** — it only makes the multi-asset universe available.

Next, per the screen: hand strategy-designer a SPEC with (1) the 12-month TSMOM rule
frozen ex-ante, (2) the benchmark gate restated as a diversifier gate — trend must add
risk-adjusted return AND negative-crisis-correlation vs a **static** multi-asset
buy-and-hold, not just beat SPY — locked before any OOS look, and (3) a pre-registered
OOS window that includes a lean stretch. The two logged downstream killers remain
lean-regime OOS Sharpe below bar and "diversification beta, not alpha."
