"""Build + audit the scheduled-FOMC calendar for fomc-drift (SPEC.md, Data
requirements). Writes strategies/fomc-drift/fomc_calendar.csv (committed — it is
public record, not market data) and an audit JSON to --out-dir.

Source of record: the Federal Reserve's own pages, transcribed 2026-07-06 —
per-year historical pages https://www.federalreserve.gov/monetarypolicy/
fomchistorical<YYYY>.htm for 1994-2020 and the current calendar page
https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm for 2021-2026.
Only `type == scheduled` rows are tradeable per the SPEC; conference calls,
emergency sessions, and notation votes are recorded (never traded), and the
cancelled 2020-03-17/18 meeting carries type=cancelled per the SPEC's
point-in-time cancellation rule (superseded by the 2020-03-15 emergency session,
announced before the would-be entry).

Press-conference flag is DIAGNOSTIC ONLY (never a gate): none before 2011-04;
2011: Apr/Jun/Nov; 2012: Jan/Apr/Jun/Sep/Dec (transition year, 5); 2013-2018:
Mar/Jun/Sep/Dec; every scheduled meeting since 2019-01.

Audit (blocking, per SPEC):
  1. scheduled meetings per year == 8 for every full year (2020: 7 held + 1
     cancelled — documented) — any other deviation fails the audit;
  2. weekday of every scheduled T reported; non-Tue/Wed T's listed as exceptions
     for manual verification (they exist: e.g. 1994-02-04 Fri, 1995-07-06 Thu);
  3. every scheduled T and its T-1 must map to sessions in the spliced SPY
     series (data/SPY_daily_adj_spliced.parquet) through its last date;
  4. monotone, no duplicates, no overlapping meetings.

    uv run python scripts/build_fomc_calendar.py \
        --out-dir experiments/fomc-drift/2026-07-06-pregate
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
CSV_OUT = REPO / "strategies/fomc-drift/fomc_calendar.csv"
SPLICE = REPO / "data/SPY_daily_adj_spliced.parquet"

HIST = "https://www.federalreserve.gov/monetarypolicy/fomchistorical%d.htm"
CAL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"

# Scheduled meetings, (start MMDD, end MMDD) per year. T = end date.
SCHEDULED: dict[int, list[tuple[str, str]]] = {
    1994: [("0203", "0204"), ("0322", "0322"), ("0517", "0517"), ("0705", "0706"),
           ("0816", "0816"), ("0927", "0927"), ("1115", "1115"), ("1220", "1220")],
    1995: [("0131", "0201"), ("0328", "0328"), ("0523", "0523"), ("0705", "0706"),
           ("0822", "0822"), ("0926", "0926"), ("1115", "1115"), ("1219", "1219")],
    1996: [("0130", "0131"), ("0326", "0326"), ("0521", "0521"), ("0702", "0703"),
           ("0820", "0820"), ("0924", "0924"), ("1113", "1113"), ("1217", "1217")],
    1997: [("0204", "0205"), ("0325", "0325"), ("0520", "0520"), ("0701", "0702"),
           ("0819", "0819"), ("0930", "0930"), ("1112", "1112"), ("1216", "1216")],
    1998: [("0203", "0204"), ("0331", "0331"), ("0519", "0519"), ("0630", "0701"),
           ("0818", "0818"), ("0929", "0929"), ("1117", "1117"), ("1222", "1222")],
    1999: [("0202", "0203"), ("0330", "0330"), ("0518", "0518"), ("0629", "0630"),
           ("0824", "0824"), ("1005", "1005"), ("1116", "1116"), ("1221", "1221")],
    2000: [("0201", "0202"), ("0321", "0321"), ("0516", "0516"), ("0627", "0628"),
           ("0822", "0822"), ("1003", "1003"), ("1115", "1115"), ("1219", "1219")],
    2001: [("0130", "0131"), ("0320", "0320"), ("0515", "0515"), ("0626", "0627"),
           ("0821", "0821"), ("1002", "1002"), ("1106", "1106"), ("1211", "1211")],
    2002: [("0129", "0130"), ("0319", "0319"), ("0507", "0507"), ("0625", "0626"),
           ("0813", "0813"), ("0924", "0924"), ("1106", "1106"), ("1210", "1210")],
    2003: [("0128", "0129"), ("0318", "0318"), ("0506", "0506"), ("0624", "0625"),
           ("0812", "0812"), ("0915", "0916"), ("1028", "1028"), ("1209", "1209")],
    2004: [("0127", "0128"), ("0316", "0316"), ("0504", "0504"), ("0629", "0630"),
           ("0810", "0810"), ("0921", "0921"), ("1110", "1110"), ("1214", "1214")],
    2005: [("0201", "0202"), ("0322", "0322"), ("0503", "0503"), ("0629", "0630"),
           ("0809", "0809"), ("0920", "0920"), ("1101", "1101"), ("1213", "1213")],
    2006: [("0131", "0131"), ("0327", "0328"), ("0510", "0510"), ("0628", "0629"),
           ("0808", "0808"), ("0920", "0920"), ("1024", "1025"), ("1212", "1212")],
    2007: [("0130", "0131"), ("0320", "0321"), ("0509", "0509"), ("0627", "0628"),
           ("0807", "0807"), ("0918", "0918"), ("1030", "1031"), ("1211", "1211")],
    2008: [("0129", "0130"), ("0318", "0318"), ("0429", "0430"), ("0624", "0625"),
           ("0805", "0805"), ("0916", "0916"), ("1028", "1029"), ("1215", "1216")],
    2009: [("0127", "0128"), ("0317", "0318"), ("0428", "0429"), ("0623", "0624"),
           ("0811", "0812"), ("0922", "0923"), ("1103", "1104"), ("1215", "1216")],
    2010: [("0126", "0127"), ("0316", "0316"), ("0427", "0428"), ("0622", "0623"),
           ("0810", "0810"), ("0921", "0921"), ("1102", "1103"), ("1214", "1214")],
    2011: [("0125", "0126"), ("0315", "0315"), ("0426", "0427"), ("0621", "0622"),
           ("0809", "0809"), ("0920", "0921"), ("1101", "1102"), ("1213", "1213")],
    2012: [("0124", "0125"), ("0313", "0313"), ("0424", "0425"), ("0619", "0620"),
           ("0731", "0801"), ("0912", "0913"), ("1023", "1024"), ("1211", "1212")],
    2013: [("0129", "0130"), ("0319", "0320"), ("0430", "0501"), ("0618", "0619"),
           ("0730", "0731"), ("0917", "0918"), ("1029", "1030"), ("1217", "1218")],
    2014: [("0128", "0129"), ("0318", "0319"), ("0429", "0430"), ("0617", "0618"),
           ("0729", "0730"), ("0916", "0917"), ("1028", "1029"), ("1216", "1217")],
    2015: [("0127", "0128"), ("0317", "0318"), ("0428", "0429"), ("0616", "0617"),
           ("0728", "0729"), ("0916", "0917"), ("1027", "1028"), ("1215", "1216")],
    2016: [("0126", "0127"), ("0315", "0316"), ("0426", "0427"), ("0614", "0615"),
           ("0726", "0727"), ("0920", "0921"), ("1101", "1102"), ("1213", "1214")],
    2017: [("0131", "0201"), ("0314", "0315"), ("0502", "0503"), ("0613", "0614"),
           ("0725", "0726"), ("0919", "0920"), ("1031", "1101"), ("1212", "1213")],
    2018: [("0130", "0131"), ("0320", "0321"), ("0501", "0502"), ("0612", "0613"),
           ("0731", "0801"), ("0925", "0926"), ("1107", "1108"), ("1218", "1219")],
    2019: [("0129", "0130"), ("0319", "0320"), ("0430", "0501"), ("0618", "0619"),
           ("0730", "0731"), ("0917", "0918"), ("1029", "1030"), ("1210", "1211")],
    2020: [("0128", "0129"), ("0428", "0429"), ("0609", "0610"), ("0728", "0729"),
           ("0915", "0916"), ("1104", "1105"), ("1215", "1216")],  # +1 cancelled below
    2021: [("0126", "0127"), ("0316", "0317"), ("0427", "0428"), ("0615", "0616"),
           ("0727", "0728"), ("0921", "0922"), ("1102", "1103"), ("1214", "1215")],
    2022: [("0125", "0126"), ("0315", "0316"), ("0503", "0504"), ("0614", "0615"),
           ("0726", "0727"), ("0920", "0921"), ("1101", "1102"), ("1213", "1214")],
    2023: [("0131", "0201"), ("0321", "0322"), ("0502", "0503"), ("0613", "0614"),
           ("0725", "0726"), ("0919", "0920"), ("1031", "1101"), ("1212", "1213")],
    2024: [("0130", "0131"), ("0319", "0320"), ("0430", "0501"), ("0611", "0612"),
           ("0730", "0731"), ("0917", "0918"), ("1106", "1107"), ("1217", "1218")],
    2025: [("0128", "0129"), ("0318", "0319"), ("0506", "0507"), ("0617", "0618"),
           ("0729", "0730"), ("0916", "0917"), ("1028", "1029"), ("1209", "1210")],
    2026: [("0127", "0128"), ("0317", "0318"), ("0428", "0429"), ("0616", "0617"),
           ("0728", "0729"), ("0915", "0916"), ("1027", "1028"), ("1208", "1209")],
}

CANCELLED = [("2020-03-17", "2020-03-18",
              "superseded by the 2020-03-15 emergency session, announced before "
              "the would-be T-1 entry (Fed 2020 historical page: 'cancelled')")]

# Conference calls / emergency sessions / notation votes — recorded, never traded.
UNSCHEDULED: dict[str, list[str]] = {
    "conference_call": [
        "1994-02-28", "1994-03-24", "1994-04-18", "1994-07-20", "1994-12-30",
        "1995-01-13", "1995-03-10", "1995-04-28",
        "1998-09-21", "1998-10-15",
        "2001-01-03", "2001-04-11", "2001-04-18", "2001-09-13", "2001-09-17",
        "2003-03-25", "2003-04-01", "2003-04-08", "2003-04-16",
        "2007-08-10", "2007-08-16", "2007-12-06",
        "2008-01-09", "2008-01-21", "2008-03-10", "2008-07-24", "2008-09-29",
        "2008-10-07",
        "2009-01-16", "2009-02-07", "2009-06-03",
        "2010-05-09", "2010-10-15",
        "2011-08-01", "2011-11-28",
        "2013-10-16", "2014-03-04", "2019-10-04",
        "2020-03-02",  # statement 2020-03-03 (50 bps emergency cut)
    ],
    "emergency": ["2020-03-15"],
    "notation_vote": ["2020-03-19", "2020-03-23", "2020-03-31", "2020-08-27",
                      "2025-08-22"],
}

PC_2011_2018 = {
    "2011-04-27", "2011-06-22", "2011-11-02",
    "2012-01-25", "2012-04-25", "2012-06-20", "2012-09-13", "2012-12-12",
    "2013-03-20", "2013-06-19", "2013-09-18", "2013-12-18",
    "2014-03-19", "2014-06-18", "2014-09-17", "2014-12-17",
    "2015-03-18", "2015-06-17", "2015-09-17", "2015-12-16",
    "2016-03-16", "2016-06-15", "2016-09-21", "2016-12-14",
    "2017-03-15", "2017-06-14", "2017-09-20", "2017-12-13",
    "2018-03-21", "2018-06-13", "2018-09-26", "2018-12-19",
}


def press_conference(end: str) -> bool:
    if end >= "2019-01-01":
        return True
    return end in PC_2011_2018


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    rows = []
    for year, meetings in sorted(SCHEDULED.items()):
        src = HIST % year if year <= 2020 else CAL
        for mmdd_s, mmdd_e in meetings:
            s = f"{year}-{mmdd_s[:2]}-{mmdd_s[2:]}"
            e = f"{year}-{mmdd_e[:2]}-{mmdd_e[2:]}"
            rows.append((s, e, "scheduled", press_conference(e), src))
    for s, e, note in CANCELLED:
        rows.append((s, e, "cancelled", False, f"{HIST % 2020} — {note}"))
    for typ, dates in UNSCHEDULED.items():
        for d in dates:
            rows.append((d, d, typ, False, HIST % int(d[:4]) if int(d[:4]) <= 2020 else CAL))
    rows.sort()

    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    with CSV_OUT.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["start_date", "end_date", "type", "press_conference", "source_note"])
        w.writerows(rows)

    # ---- Audit ----
    spl = pd.read_parquet(SPLICE)
    sessions = pd.DatetimeIndex(
        [t.tz_convert("America/New_York").date() for t in spl.index]
    ).astype("datetime64[ns]")
    last_session = sessions[-1]

    sched = [(pd.Timestamp(s), pd.Timestamp(e)) for s, e, t, _, _ in rows if t == "scheduled"]
    per_year = pd.Series([e.year for _, e in sched]).value_counts().sort_index()
    count_ok = all(
        n == 8 or (y == 2020 and n == 7) or (y == sched[-1][1].year)
        for y, n in per_year.items()
    )

    weekday_exceptions = [
        str(e.date()) + " " + e.day_name() for _, e in sched
        if e.day_name() not in ("Tuesday", "Wednesday")
    ]

    mapping_errors, t1_map = [], {}
    for s, e in sched:
        if e > last_session:
            continue  # future meetings can't be mapped yet
        if e not in sessions:
            mapping_errors.append(f"T {e.date()} not a trading session")
            continue
        pos = sessions.get_loc(e)
        prior = sessions[pos - 1]
        t1_map[str(e.date())] = str(prior.date())
        if not (s - pd.Timedelta(days=5) <= prior < e):
            mapping_errors.append(f"T-1 {prior.date()} suspicious for T {e.date()}")

    starts = [s for s, _ in sched]
    overlap_ok = all(sched[i][1] < sched[i + 1][0] for i in range(len(sched) - 1))

    report = {
        "csv": str(CSV_OUT),
        "sources": {"historical_1994_2020": HIST % 0 + " (per year)", "calendar_2021_2026": CAL},
        "rows_total": len(rows),
        "scheduled_total": len(sched),
        "scheduled_per_year": {int(y): int(n) for y, n in per_year.items()},
        "per_year_count_check": "PASS (8/yr; 2020 = 7 held + 1 cancelled, documented; "
        "final year partial-by-schedule)" if count_ok else "FAIL",
        "cancelled": [f"{s} -> {e}" for s, e, _ in CANCELLED],
        "unscheduled_recorded": {k: len(v) for k, v in UNSCHEDULED.items()},
        "weekday_of_T_exceptions_manual_verify": weekday_exceptions,
        "t_minus_1_mapping_errors": mapping_errors,
        "t_minus_1_mapping_checked": len(t1_map),
        "monotone_no_overlap": bool(overlap_ok and pd.Index(starts).is_monotonic_increasing),
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True
        ).stdout.strip(),
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "fomc_calendar_audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))

    if not count_ok or mapping_errors or not report["monotone_no_overlap"]:
        raise SystemExit("\nCalendar audit FAILED — fix before the pregate.")
    print(f"\nCalendar audit PASS — {len(sched)} scheduled meetings -> {CSV_OUT}")


if __name__ == "__main__":
    main()
