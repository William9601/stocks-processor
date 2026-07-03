# experiments/

Every backtest run writes one directory here. Committed to git — results without
provenance don't count.

## Layout

```
experiments/
  <strategy-name>/
    <YYYY-MM-DD-HHMM>-<tag>/     # tag: e.g. "is-tune", "oos", "walkforward"
      config.yaml                # full params, data range, cost model, seed, git commit
      metrics.json               # the standard metric set (see below)
      notes.md                   # what was tried, what was learned
  comparisons/
    <YYYY-MM-DD>-comparison.md   # output of /compare-strategies
```

## metrics.json standard fields

`net_return`, `gross_return`, `annualized_return`, `sharpe`, `sortino`,
`max_drawdown`, `max_drawdown_days`, `win_rate`, `profit_factor`, `avg_win`,
`avg_loss`, `trade_count`, `turnover`, `cost_drag`, `start_date`, `end_date`,
`sample` ("is" | "oos" | "walkforward").

## Rules

- Never overwrite a run directory; new run, new directory.
- `config.yaml` must include the git commit hash of the code that produced it.
- In-sample tuning runs are kept too — they document the search, which is exactly
  what a future overfitting review needs to see.
