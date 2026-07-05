# orb — OOS 1.5× cost sensitivity (pre-registered companion run)

- SPEC sign-off #2: the OOS result must remain net-positive at 1.5× the
  locked cost model (3.0 bps weighted round trip). Costs here: 0.15 / 0.6 /
  1.5 bps. Same window, same data, same code as `2026-07-05-1639-oos`.
- Result: net return **−2.03%**, net zero-filled Sharpe **−0.069** →
  **FAILS the 1.5×-cost gate**. At ~1.9 bps gross per trade the OOS edge is
  thinner than even the 1.0× cost load it was required to carry with margin.
- This is one of five hard fails; full verdict table in the locked-cost run's
  notes and in `strategies/orb/SPEC.md`.
