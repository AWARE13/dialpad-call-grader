#!/usr/bin/env python3
"""
grade_week_range.py — Grade every call in a roster_candidates_week_*.json file against
rubric_v2.md, save per-call grade files, and roll up a company-wide pattern summary.

Usage:
    python3 scripts/grade_week_range.py output/roster_candidates_week_2026-08-30_2026-09-05.json
"""

import json, re, sys, statistics
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from grade_call_auto_v2 import grade_call_auto_v2

OUTPUT_DIR = Path(__file__).parent.parent / "output"

def safe_filename(name):
    return re.sub(r'[^A-Za-z0-9]', '', name)

def grade_week_range(candidates_path):
    with open(candidates_path) as f:
        run_data = json.load(f)

    week_start = run_data["week_start"]
    week_end = run_data["week_end"]
    candidates = run_data["candidates"]

    grades_dir = OUTPUT_DIR / "weekly" / "grades" / f"v2_week_{week_start}_{week_end}"
    grades_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nGrading {len(candidates)} calls against rubric_v2 (Jeff Call Map)...\n")

    all_grades = []
    failed = []

    for i, c in enumerate(candidates, 1):
        print(f"  [{i:3}/{len(candidates)}] {c['rep_name']:<30} {c['duration_min']:>5.1f} min  ", end="", flush=True)
        try:
            grade = grade_call_auto_v2(
                call_id=c["call_id"],
                rep_name=c["rep_name"],
                branch=c["branch"],
                duration_min=c["duration_min"],
                datetime_ct=c.get("datetime_ct"),
                external_number=c.get("external_number"),
            )
        except Exception as e:
            print(f"FAILED — {e}")
            failed.append({"call_id": c["call_id"], "rep_name": c["rep_name"], "error": str(e)})
            continue

        all_grades.append(grade)

        out_path = grades_dir / f"{safe_filename(c['rep_name'])}_{c['call_id']}.json"
        with open(out_path, "w") as f:
            json.dump(grade, f, indent=2)

        if grade.get("total_score") is not None:
            print(f"{grade['total_score']}/100 {'PASS' if grade['pass'] else ''}")
        else:
            print(f"skip — {grade.get('skip_reason')}")

    # roll-up
    scored = [g for g in all_grades if g.get("total_score") is not None]
    scores = [g["total_score"] for g in scored]

    by_rep = {}
    for g in scored:
        by_rep.setdefault(g["rep_name"], []).append(g["total_score"])

    per_rep_avg = {rep: round(statistics.mean(v), 1) for rep, v in by_rep.items()}

    summary = {
        "rubric_version": "v2-jeff-call-map",
        "week_start": week_start,
        "week_end": week_end,
        "total_calls_pulled": len(candidates),
        "total_graded": len(scored),
        "total_skipped": len(all_grades) - len(scored),
        "total_failed": len(failed),
        "company_avg_score": round(statistics.mean(scores), 1) if scores else None,
        "company_median_score": round(statistics.median(scores), 1) if scores else None,
        "pass_rate_pct": round(100 * sum(1 for s in scores if s >= 80) / len(scores), 1) if scores else None,
        "per_rep_avg_score": dict(sorted(per_rep_avg.items(), key=lambda x: -x[1])),
        "failed_calls": failed,
    }

    summary_path = OUTPUT_DIR / f"patterns_v2_week_{week_start}_{week_end}.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Graded: {len(scored)} / {len(candidates)}  |  Skipped: {summary['total_skipped']}  |  Failed: {len(failed)}")
    if scores:
        print(f"Company avg: {summary['company_avg_score']}/100  |  Median: {summary['company_median_score']}  |  Pass rate (80+): {summary['pass_rate_pct']}%")
    print(f"Per-call grades: {grades_dir}")
    print(f"Summary: {summary_path}")

    return str(summary_path)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/grade_week_range.py <roster_candidates_week_*.json>")
        sys.exit(1)
    grade_week_range(sys.argv[1])
