#!/usr/bin/env python3
"""
append_history_v3.py — Appends one week's results from a patterns_v3_cet_week_*.json
summary into the persistent output/patterns_v3_history.json (company avg by week +
per-rep trend), which build_report_v3.py reads for week-over-week deltas and
build_trend_report_v3.py renders as the trend page.

If an entry for the same (week_start, week_end) already exists, it is replaced rather
than duplicated — makes this safe to rerun for a corrected/combined week.

Usage:
    python3 scripts/append_history_v3.py output/patterns_v3_cet_week_2026-09-28_2026-10-04.json
"""
import json, sys
from pathlib import Path

BASE = Path(__file__).parent.parent
HISTORY_PATH = BASE / "output" / "patterns_v3_history.json"

def append_history(summary_path):
    with open(summary_path) as f:
        summary = json.load(f)

    week_start = summary["week_start"]
    week_end = summary["week_end"]

    if HISTORY_PATH.exists():
        history = json.load(open(HISTORY_PATH))
    else:
        history = {"company_avg_by_week": [], "per_rep_trend": {}}

    weeks = [w for w in history["company_avg_by_week"] if not (w["week_start"] == week_start and w["week_end"] == week_end)]
    weeks.append({"week_start": week_start, "week_end": week_end, "avg": summary["company_avg_score"]})
    weeks.sort(key=lambda w: w["week_start"])
    history["company_avg_by_week"] = weeks

    for rep, avg in summary["per_rep_avg_score"].items():
        entries = [e for e in history["per_rep_trend"].get(rep, []) if not (e["week_start"] == week_start and e["week_end"] == week_end)]
        entries.append({"week_start": week_start, "week_end": week_end, "avg_score": avg})
        entries.sort(key=lambda e: e["week_start"])
        history["per_rep_trend"][rep] = entries

    with open(HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=2)

    print(f"History updated: {week_start} to {week_end}, company avg {summary['company_avg_score']}")
    print(f"Written: {HISTORY_PATH}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/append_history_v3.py <patterns_v3_cet_week_*.json>")
        sys.exit(1)
    append_history(sys.argv[1])
