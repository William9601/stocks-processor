# overnight-long — corr-basis-for-orb (NOT a new look at overnight-long)

Re-run of the already-validated overnight-long OOS configuration, executed
solely to reconstruct the book's daily P&L series (trades.csv) for the orb
SPEC's locked reporting requirement: "daily-return correlation vs the
overnight-long book over the identical dates".

- No overnight-long decision rides on this run; its verdict history is
  unchanged. The run exists because trades.csv persistence was added to
  run_backtest.py after overnight-long's original runs.
- Result used: daily P&L correlation orb vs overnight-long over 2023-01-03 →
  2024-12-30 (n=501 sessions) = **0.008** — see
  `experiments/orb/2026-07-05-1639-oos/notes.md`.
- Numbers differ slightly in framing from the committed 2026-07-03 runs (this
  window is the config's 2022–2024 OOS; only the 2023–2024 overlap was used
  for the correlation).
