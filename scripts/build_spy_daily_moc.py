"""Re-stamp the audited SPY daily splice to true session-close timestamps.

The backtest engine fills a market-on-close (``FillTiming.NEXT_CLOSE``) order
only on a bar whose timestamp equals that session's official close
(``core.data.calendar.session_closes``: XNYS 16:00 ET, 13:00 ET half-days). The
audited splice ``data/SPY_daily_adj_spliced.parquet`` stamps each daily bar at
**00:00 ET** (midnight of the session date), so on every post-2015 session the
engine's MOC path never fires and a daily-bar MOC strategy would silently book
ZERO trades. (Empirically confirmed: midnight-stamped bars give
``is_session_close = False`` on 2016+ sessions.)

This script rewrites each daily bar's timestamp to its **true session close**
so ``et_index[i] == session_closes[day]`` holds for every bar and MOC orders
fill at the daily close. Nothing else changes — OHLCV values are copied
verbatim; the transform is a pure, lossless re-stamp of the index.

Close time per date:
  * XNYS session close (``session_close_et``) when the exchange calendar knows
    the date — this correctly yields 13:00 ET on half-days;
  * else 16:00 ET *local* (America/New_York, so DST is handled) for dates
    before the calendar's 2015 start. The engine falls back to the bar's own
    stamp (``last_bar[d]``) on those dates, so any self-consistent stamp works;
    16:00 ET local is the honest close.

Output ``data/SPY_daily_moc.parquet`` is gitignored and rebuilt from the
committed splice; its sha256 is printed and must be recorded per experiment
(house rule 5). It is a derived file — rebuild it whenever the splice changes.

    uv run python scripts/build_spy_daily_moc.py \
        --in data/SPY_daily_adj_spliced.parquet \
        --out data/SPY_daily_moc.parquet
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import pandas as pd

from core.data.calendar import filter_to_sessions, session_close_et
from core.strategy import BAR_COLUMNS, ET

REPO = Path(__file__).resolve().parents[1]


def restamp_to_session_close(bars: pd.DataFrame) -> pd.DataFrame:
    """Return ``bars`` with each row's timestamp moved to its session close."""
    et_dates = bars.index.tz_convert(ET).normalize()
    new_index = []
    for ts in et_dates:
        d = ts.date()
        close = session_close_et(d)
        if close is None:
            # Pre-2015 (outside the XNYS calendar's range): 16:00 ET local.
            close = pd.Timestamp(f"{d} 16:00", tz=ET)
        new_index.append(close.tz_convert("UTC"))
    out = bars.copy()
    out.index = pd.DatetimeIndex(new_index, name="ts")
    return out.sort_index()


def _assert_no_missing_sessions(bars: pd.DataFrame) -> None:
    """Abort if the series is not exactly the XNYS sessions over its range."""
    import exchange_calendars as xcals

    et = bars.index.tz_convert(ET)
    bdates = {pd.Timestamp(d) for d in et.normalize().date}
    cal = xcals.get_calendar("XNYS", start=str(min(bdates).date()))
    xsess = set(cal.sessions_in_range(min(bdates), max(bdates)))
    missing = sorted(xsess - bdates)
    if missing:
        raise SystemExit(
            f"{len(missing)} XNYS session(s) missing from the series — a daily-bar "
            f"MOC would fill on the wrong close. First: {[str(m.date()) for m in missing[:10]]}"
        )


def file_sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", type=Path,
                    default=REPO / "data/SPY_daily_adj_spliced.parquet")
    ap.add_argument("--out", type=Path, default=REPO / "data/SPY_daily_moc.parquet")
    args = ap.parse_args()

    src = pd.read_parquet(args.src)
    n_in = len(src)
    restamped = restamp_to_session_close(src)

    # The engine loads bars via DataFeed.from_source, which runs
    # filter_to_sessions (drops bars stamped AFTER their official close). A
    # correct re-stamp lands exactly ON the close, so every bar must survive.
    kept = filter_to_sessions(restamped)
    dropped = n_in - len(kept)
    if dropped:
        raise SystemExit(
            f"{dropped} bar(s) dropped by filter_to_sessions — re-stamp landed "
            "past a session close (a half-day was stamped 16:00). Aborting."
        )
    if len(kept) != n_in:
        raise SystemExit(f"row count changed: {n_in} -> {len(kept)} (re-stamp is lossy)")

    # Missing-session guard (quant-reviewer follow-up): the engine fills a
    # daily-bar MOC at the NEXT PRESENT bar's close. If a session were missing
    # from the series, a BUY decided on T-2 would fill at the wrong close
    # (close(T) instead of close(T-1)) silently. Assert the series is exactly
    # the XNYS sessions over its range, so any daily-bar MOC strategy built on
    # this file is safe by construction.
    _assert_no_missing_sessions(kept)

    kept = kept[BAR_COLUMNS].astype(float)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    kept.to_parquet(args.out)

    # Audit: every bar must now register as its session close, so the engine's
    # MOC path fires on every daily bar (spot-check a few 2016+ sessions).
    from core.data.calendar import session_closes

    et_index = kept.index.tz_convert(ET)
    closes = session_closes(et_index)
    matches = sum(et_index[i] == closes[et_index[i].date()] for i in range(len(et_index)))

    print(f"in : {args.src}  rows={n_in}")
    print(f"out: {args.out}  rows={len(kept)}")
    print(f"range: {et_index[0].date()} -> {et_index[-1].date()}")
    print(f"is_session_close matches: {matches}/{len(et_index)} "
          f"({'ALL' if matches == len(et_index) else 'MISMATCH — MOC will not fill everywhere'})")
    print(f"sha256: {file_sha(args.out)}")
    if matches != len(et_index):
        raise SystemExit("not every bar is stamped at its session close — MOC path broken")


if __name__ == "__main__":
    main()
