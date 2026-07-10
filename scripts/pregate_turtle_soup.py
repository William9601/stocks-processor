"""Pre-scoring diagnostic for turtle-soup (SPEC.md frozen 2026-07-10 before this ran).

Simulates the single pre-registered Street Smarts Plus One configuration — 20-day
Donchian failed-breakout fade, long/short, across the audited 8-ETF basket — OUTSIDE
the backtest engine and on the IS WINDOW ONLY, recording signed GROSS per-trade
returns in bps.

Binding gate (frozen in SPEC.md before this script existed) — REJECT at
spec-validation if:
  * IS mean gross return per trade <= 5.0 bps   (the locked cost bar), OR
  * EDGE(IS) <= 0                               (gross, vs the matched same-instrument
                                                 /same-direction/same-holding-clock
                                                 unconditional drift baseline), OR
  * IS filled trades < 200                      (inconclusive-reject: cannot power OOS)

**OOS (2017-01 -> 2024-12) and WF (2025->) are NOT read here.** Bars are hard-sliced
to <= 2016-12-31 before any computation. Setups whose full 4-session hold cannot
resolve inside IS are skipped (counted), so no exit ever reads past the IS boundary.

Frozen rule (never swept): 20d Donchian prior extremes (excl. today); previous extreme
>= 4 sessions old (most-recent-argmin); Plus-One close condition (C_s <= DCL_s longs /
C_s >= DCH_s shorts); entry stop 1 tick beyond the prior extreme, session s+1 only,
gap-through fills at the open; protective stop 1 tick beyond the setup-day extreme;
MOC time exit at close of hold-session 4 (fill day = session 1); no re-entry rule;
one position/order per instrument; 4-slot concurrency cap, alphabetical tie-break;
LOCKED worst-case intrabar ordering (entered-then-stopped on any spanning bar; stop
before time exit).

    uv run python scripts/pregate_turtle_soup.py --out experiments/turtle-soup/2026-07-10-pregate
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]

# --- frozen spec parameters (SPEC.md 2026-07-10; never swept) ---
BASKET = ["DBC", "EEM", "EFA", "GLD", "IEF", "SPY", "TLT", "UUP"]  # alphabetical
ASSET_CLASS = {"SPY": "equity", "EFA": "equity", "EEM": "equity",
               "IEF": "bond", "TLT": "bond", "DBC": "commodity", "GLD": "commodity",
               "UUP": "dollar"}
COMMON_START = "2007-03-01"    # basket common start (UUP inception)
SIGNAL_START = "2007-04-01"    # first scored setups, past the 20d warm-up
IS_END = "2016-12-31"          # OOS starts 2017-01-01 and is NOT read here
CHANNEL = 20                   # Donchian lookback (prior 20 sessions, excl. today)
SEP_MIN = 4                    # previous extreme >= 4 sessions earlier
TICK = 0.01                    # entry/stop offset, US-listed ETF penny tick
HOLD_SESSIONS = 4              # fill day = session 1 -> MOC exit close of fill_idx+3
MAX_SLOTS = 4                  # positions + pending entry orders combined
COST_BAR_BPS = 5.0             # locked round-trip cost bar the mean gross must clear
MIN_TRADES = 200               # gate 3


def file_sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def load_bars(data_dir: Path) -> dict[str, pd.DataFrame]:
    """Adjusted OHLC per instrument on the common calendar, HARD-SLICED to IS."""
    frames = {}
    for tk in BASKET:
        df = pd.read_parquet(data_dir / f"{tk}_daily_adj.parquet")[
            ["open", "high", "low", "close"]]
        df.index = pd.DatetimeIndex(df.index.tz_convert("America/New_York").date)
        df = df[~df.index.duplicated(keep="last")].sort_index()
        # HARD IS SLICE before any computation
        frames[tk] = df[(df.index >= pd.Timestamp(COMMON_START))
                        & (df.index <= pd.Timestamp(IS_END))]
    cal = None
    for df in frames.values():
        cal = df.index if cal is None else cal.intersection(df.index)
    return {tk: df.reindex(cal) for tk, df in frames.items()}, cal


def detect_setups(df: pd.DataFrame) -> pd.DataFrame:
    """Setup flags per session per the frozen rule. All inputs strictly prior bars
    except the setup-day bar itself (used only after it completes)."""
    lo, hi, cl = df["low"].to_numpy(), df["high"].to_numpy(), df["close"].to_numpy()
    n = len(df)
    long_setup = np.zeros(n, bool)
    short_setup = np.zeros(n, bool)
    dcl = np.full(n, np.nan)
    dch = np.full(n, np.nan)
    for t in range(CHANNEL, n):
        wlo = lo[t - CHANNEL:t]
        whi = hi[t - CHANNEL:t]
        dcl_t = wlo.min()
        dch_t = whi.max()
        dcl[t], dch[t] = dcl_t, dch_t
        # most-recent argmin/argmax inside the window -> session offset from t
        sep_lo = CHANNEL - int(np.flatnonzero(wlo == dcl_t)[-1])   # t - m_L(t)
        sep_hi = CHANNEL - int(np.flatnonzero(whi == dch_t)[-1])   # t - m_H(t)
        if lo[t] < dcl_t and sep_lo >= SEP_MIN and cl[t] <= dcl_t:
            long_setup[t] = True
        if hi[t] > dch_t and sep_hi >= SEP_MIN and cl[t] >= dch_t:
            short_setup[t] = True
    return pd.DataFrame({"long_setup": long_setup, "short_setup": short_setup,
                         "dcl": dcl, "dch": dch}, index=df.index)


def simulate(bars: dict[str, pd.DataFrame], cal: pd.DatetimeIndex,
             setups: dict[str, pd.DataFrame], optimistic: bool = False) -> tuple[list[dict], dict]:
    """Day loop: arm orders at the open (slots checked then), fill/exit on the bar
    under the LOCKED worst-case intrabar ordering. Returns trades + flow counters.

    optimistic=True is a DIAGNOSTIC-ONLY ceiling (never a gate; the SPEC forbids
    optimistic orderings for scoring): spanning entry bars survive un-stopped, and a
    stop touch on the time-exit bar yields the MOC instead. Physically unattainable
    best case; used only to test whether a verdict is an artifact of bar ambiguity."""
    n = len(cal)
    last_idx = n - 1
    sig_start = pd.Timestamp(SIGNAL_START)
    positions: dict[str, dict] = {}          # tk -> open position
    trades: list[dict] = []
    counters = {"setups_scored": 0, "both_sides_same_day_skipped": 0,
                "skipped_instrument_busy": 0, "skipped_no_slot": 0,
                "skipped_is_boundary": 0, "orders_armed": 0, "orders_unfilled": 0}
    daily_open_positions = np.zeros(n, int)

    for j in range(1, n):
        # --- 1. arm orders at the open of day j from setups on day j-1 ---
        armed: dict[str, dict] = {}
        candidates = []
        for tk in BASKET:                     # alphabetical priority by construction
            row = setups[tk].iloc[j - 1]
            if cal[j - 1] < sig_start:
                continue
            is_long, is_short = bool(row["long_setup"]), bool(row["short_setup"])
            if not (is_long or is_short):
                continue
            if is_long and is_short:          # degenerate; pre-declared skip
                counters["both_sides_same_day_skipped"] += 1
                continue
            counters["setups_scored"] += 1
            if j + HOLD_SESSIONS - 1 > last_idx:
                counters["skipped_is_boundary"] += 1   # hold can't resolve inside IS
                continue
            candidates.append((tk, +1 if is_long else -1, row))
        for tk, d, row in candidates:
            if tk in positions:
                counters["skipped_instrument_busy"] += 1
                continue
            if len(positions) + len(armed) >= MAX_SLOTS:
                counters["skipped_no_slot"] += 1
                continue
            sbar = bars[tk].iloc[j - 1]
            if d == +1:
                level, stop = row["dcl"] + TICK, sbar["low"] - TICK
            else:
                level, stop = row["dch"] - TICK, sbar["high"] + TICK
            armed[tk] = {"dir": d, "level": level, "stop": stop,
                         "setup_date": cal[j - 1],
                         "penetration": (row["dcl"] - sbar["low"]) if d == +1
                                        else (sbar["high"] - row["dch"])}
            counters["orders_armed"] += 1

        # --- 2. manage open positions on bar j (stop first, then time exit) ---
        for tk in list(positions):
            pos = positions[tk]
            b = bars[tk].iloc[j]
            d, stop = pos["dir"], pos["stop"]
            exit_px = exit_type = None
            gap_through = (b["open"] < stop) if d == +1 else (b["open"] > stop)
            touched = (b["low"] <= stop) if d == +1 else (b["high"] >= stop)
            last_day = j == pos["fill_idx"] + HOLD_SESSIONS - 1
            if gap_through:
                exit_px, exit_type = b["open"], "stop_gap"
            elif touched and not (optimistic and last_day):
                exit_px, exit_type = stop, "stop"   # LOCKED: stop before time exit
            elif last_day:
                exit_px, exit_type = b["close"], "time_moc"
            if exit_px is not None:
                trades.append(_close(pos, tk, cal[j], j, exit_px, exit_type))
                del positions[tk]

        # --- 3. entry orders on bar j (their only validity session) ---
        for tk, o in armed.items():
            b = bars[tk].iloc[j]
            d, level, stop = o["dir"], o["level"], o["stop"]
            gap_in = (b["open"] > level) if d == +1 else (b["open"] < level)
            traded_through = (b["high"] >= level) if d == +1 else (b["low"] <= level)
            if not (gap_in or traded_through):
                counters["orders_unfilled"] += 1
                continue
            entry_px = b["open"] if gap_in else level
            pos = {"dir": d, "entry_px": entry_px, "stop": stop, "fill_idx": j,
                   "fill_date": cal[j], "setup_date": o["setup_date"],
                   "penetration": o["penetration"], "tk": tk}
            spans_stop = (b["low"] <= stop) if d == +1 else (b["high"] >= stop)
            if spans_stop and not optimistic: # LOCKED worst case: entered then stopped
                trades.append(_close(pos, tk, cal[j], j, stop, "stop_samebar"))
            else:
                positions[tk] = pos

        daily_open_positions[j] = len(positions)

    counters["open_at_is_end"] = len(positions)   # should be 0 given boundary skip
    counters["avg_concurrent_positions"] = round(float(daily_open_positions.mean()), 3)
    counters["max_concurrent_positions"] = int(daily_open_positions.max())
    return trades, counters


def _close(pos: dict, tk: str, exit_date, exit_idx: int,
           exit_px: float, exit_type: str) -> dict:
    d, entry = pos["dir"], pos["entry_px"]
    gross = d * (exit_px / entry - 1.0)
    risk_frac = d * (entry - pos["stop"]) / entry     # per-share risk / entry (R of 1)
    return {"ticker": tk, "dir": "long" if d == +1 else "short",
            "setup_date": str(pos["setup_date"].date()),
            "fill_date": str(pos["fill_date"].date()),
            "exit_date": str(exit_date.date()), "exit_type": exit_type,
            "entry_px": round(float(entry), 4), "exit_px": round(float(exit_px), 4),
            "stop_px": round(float(pos["stop"]), 4),
            "hold_sessions": exit_idx - pos["fill_idx"],
            "gross_bps": round(float(gross * 1e4), 3),
            "risk_bps": round(float(risk_frac * 1e4), 3),
            "r_multiple": round(float(gross / risk_frac), 3) if risk_frac > 0 else np.nan,
            "penetration_bps": round(float(pos["penetration"] / entry * 1e4), 3),
            "asset_class": ASSET_CLASS[tk]}


def matched_baseline(bars: dict[str, pd.DataFrame], cal: pd.DatetimeIndex,
                     trades: list[dict]) -> tuple[float, list[float]]:
    """EDGE(IS) = mean(trade gross - d * mean h-session close-to-close return of the
    same instrument over ALL sessions in the scored window). h=0 -> 0."""
    scored = cal[cal >= pd.Timestamp(SIGNAL_START)]
    mean_h: dict[str, dict[int, float]] = {}
    for tk in BASKET:
        c = bars[tk]["close"].reindex(scored).to_numpy()
        mean_h[tk] = {}
        for h in sorted({t["hold_sessions"] for t in trades}):
            mean_h[tk][h] = 0.0 if h == 0 else float(np.nanmean(c[h:] / c[:-h] - 1.0))
    terms = []
    for t in trades:
        d = +1 if t["dir"] == "long" else -1
        base = d * mean_h[t["ticker"]][t["hold_sessions"]]
        terms.append(t["gross_bps"] - base * 1e4)
    return float(np.mean(terms)), terms


def hold_mark_curve(bars: dict[str, pd.DataFrame], cal: pd.DatetimeIndex,
                    trades: list[dict]) -> dict[int, float]:
    """Diagnostic ONLY (never a gate): mean gross bps if every fill were held to the
    close of hold-day k, ignoring the stop. Marks landing past IS are skipped."""
    idx_of = {d: i for i, d in enumerate(cal)}
    curve = {}
    for k in range(1, 7):
        marks = []
        for t in trades:
            i = idx_of[pd.Timestamp(t["fill_date"])] + (k - 1)
            if i >= len(cal):
                continue
            d = +1 if t["dir"] == "long" else -1
            c = bars[t["ticker"]]["close"].iloc[i]
            marks.append(d * (c / t["entry_px"] - 1.0) * 1e4)
        curve[k] = round(float(np.mean(marks)), 3) if marks else float("nan")
    return curve


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=REPO / "data/tsmom")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ordering", choices=["worst", "optimistic"], default="worst",
                    help="'optimistic' = diagnostic-only ceiling, never a gate")
    args = ap.parse_args()

    bars, cal = load_bars(args.data_dir)
    setups = {tk: detect_setups(bars[tk]) for tk in BASKET}
    trades, counters = simulate(bars, cal, setups,
                                optimistic=args.ordering == "optimistic")

    tdf = pd.DataFrame(trades)
    n = len(tdf)
    g = tdf["gross_bps"].to_numpy() if n else np.array([])
    mean_gross = float(g.mean()) if n else float("nan")
    t_stat = float(g.mean() / g.std(ddof=1) * np.sqrt(n)) if n > 1 else float("nan")
    edge, _ = matched_baseline(bars, cal, trades) if n else (float("nan"), [])

    # --- gate (frozen SPEC rule) ---
    reasons = []
    if not (mean_gross > COST_BAR_BPS):
        reasons.append(f"IS mean gross {mean_gross:.3f} bps <= {COST_BAR_BPS} bps cost bar")
    if not (edge > 0):
        reasons.append(f"EDGE(IS) {edge:.3f} bps <= 0 vs matched drift baseline")
    if n < MIN_TRADES:
        reasons.append(f"IS filled trades {n} < {MIN_TRADES} (inconclusive-reject)")
    if reasons:
        verdict = ("REJECT at spec-validation (binding rule frozen in SPEC.md before "
                   "this ran): " + "; ".join(reasons) + ". No parameter/variant/universe "
                   "shopping; OOS/WF stay unread; post-mortem in the SPEC.")
    else:
        verdict = ("PASS pre-scoring gate — proceed to engine implementation, engine IS "
                   "cross-check to rounding, then the ONE OOS look + 1.5x-cost companion.")

    def split(mask) -> dict:
        s = tdf[mask]["gross_bps"]
        return {"n": int(len(s)), "mean_gross_bps": round(float(s.mean()), 3) if len(s) else None}

    losses = (tdf["gross_bps"] < 0).to_numpy() if n else np.array([])
    max_consec = 0
    run = 0
    for x in losses:
        run = run + 1 if x else 0
        max_consec = max(max_consec, run)

    out = {
        "strategy": "turtle-soup",
        "gate_scope": f"IS ONLY ({SIGNAL_START} -> {IS_END}). OOS (2017-01->2024-12)/WF NOT read.",
        "data_dir": str(args.data_dir),
        "bars_sha256_16": {tk: file_sha(args.data_dir / f"{tk}_daily_adj.parquet")
                           for tk in BASKET},
        "calendar": [str(cal[0].date()), str(cal[-1].date()), int(len(cal))],
        "params": {"channel": CHANNEL, "sep_min": SEP_MIN, "tick": TICK,
                   "hold_sessions": HOLD_SESSIONS, "max_slots": MAX_SLOTS,
                   "cost_bar_bps": COST_BAR_BPS, "min_trades": MIN_TRADES,
                   "variant": "plus_one", "entry_validity": "s+1 only",
                   "re_entry": "excluded", "ordering": "locked worst-case"},
        "gate_rule": ("REJECT if mean gross <= 5.0 bps OR EDGE(IS) <= 0 OR n < 200"),
        "n_filled_trades": n,
        "IS_mean_gross_bps": round(mean_gross, 3),
        "IS_t_stat": round(t_stat, 2),
        "EDGE_IS_bps": round(edge, 3),
        "verdict": verdict,
        "flow": counters,
        "diagnostics_NOT_GATES": {
            "hit_rate": round(float((g > 0).mean()), 3) if n else None,
            "median_gross_bps": round(float(np.median(g)), 3) if n else None,
            "by_exit_type": {k: split(tdf["exit_type"] == k)
                             for k in sorted(tdf["exit_type"].unique())} if n else {},
            "by_side": {k: split(tdf["dir"] == k) for k in ["long", "short"]} if n else {},
            "by_instrument": {tk: split(tdf["ticker"] == tk) for tk in BASKET} if n else {},
            "by_asset_class": {c: split(tdf["asset_class"] == c)
                               for c in sorted(set(ASSET_CLASS.values()))} if n else {},
            "by_year_mean_gross_bps": {
                int(y): round(float(s.mean()), 3)
                for y, s in tdf.groupby(tdf["fill_date"].str[:4])["gross_bps"]} if n else {},
            "hold_mark_curve_bps_ignoring_stop": hold_mark_curve(bars, cal, trades) if n else {},
            "median_risk_bps": round(float(tdf["risk_bps"].median()), 3) if n else None,
            "median_penetration_bps": round(float(tdf["penetration_bps"].median()), 3) if n else None,
            "worst_trade_bps": round(float(g.min()), 3) if n else None,
            "worst_trade_r": round(float(tdf["r_multiple"].min()), 3) if n else None,
            "max_consecutive_losses": int(max_consec),
            "entry_fill_rate": round(1.0 - counters["orders_unfilled"]
                                     / max(counters["orders_armed"], 1), 3),
            "mean_hold_sessions": round(float(tdf["hold_sessions"].mean()), 2) if n else None,
        },
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                                     capture_output=True, text=True).stdout.strip(),
    }
    if args.ordering == "optimistic":
        out["DIAGNOSTIC_ONLY"] = ("Optimistic-ordering ceiling — physically "
                                  "unattainable; the locked worst-case run is the "
                                  "gate. This output can never overturn a verdict.")
    args.out.mkdir(parents=True, exist_ok=True)
    suffix = "" if args.ordering == "worst" else "_optimistic_ceiling"
    (args.out / f"pregate_results{suffix}.json").write_text(json.dumps(out, indent=2) + "\n")
    if n:
        tdf.to_csv(args.out / f"trades_is{suffix}.csv", index=False)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
