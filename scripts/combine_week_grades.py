#!/usr/bin/env python3
"""
combine_week_grades.py — One-off helper: combines per-call grade JSONs from two or more
existing v3_cet_week_* grade folders into a single combined-week folder, and writes a
recomputed patterns_v3_cet_week_*.json summary for that combined window. Used to stitch
the initial partial v3 pilot window (2026-09-23 to 2026-09-24) together with the
remainder of that calendar week (2026-09-25 to 2026-09-27) into one 2026-09-23 to
2026-09-27 baseline, without re-grading calls that were already graded.

Not part of the normal weekly routine — normal weeks pull/grade their own full
Mon-Sun window in one pass via grade_week_range_v3.py.

Usage:
    python3 scripts/combine_week_grades.py 2026-09-23 2026-09-27 \\
        output/weekly/grades/v3_cet_week_2026-09-23_2026-09-24 \\
        output/weekly/grades/v3_cet_week_2026-09-25_2026-09-27
"""
import json, shutil, statistics, sys
from pathlib import Path

BASE = Path(__file__).parent.parent
OUTPUT_DIR = BASE / "output"

def combine(combined_start, combined_end, source_dirs):
    combined_dir = OUTPUT_DIR / "weekly" / "grades" / f"v3_cet_week_{combined_start}_{combined_end}"
    combined_dir.mkdir(parents=True, exist_ok=True)

    all_grades = []
    total_pulled = 0
    for src in source_dirs:
        src_path = Path(src)
        for f in src_path.glob("*.json"):
            shutil.copy(f, combined_dir / f.name)
            with open(f) as fh:
                all_grades.append(json.load(fh))
        total_pulled += len(list(src_path.glob("*.json")))

    scored = [g for g in all_grades if g.get("total_score") is not None]
    scores = [g["total_score"] for g in scored]

    by_rep = {}
    for g in scored:
        by_rep.setdefault(g["rep_name"], []).append(g["total_score"])
    per_rep_avg = {rep: round(statistics.mean(v), 1) for rep, v in by_rep.items()}

    summary = {
        "rubric_version": "v3-section-map",
        "week_start": combined_start,
        "week_end": combined_end,
        "total_calls_pulled": total_pulled,
        "total_graded": len(scored),
        "total_skipped": len(all_grades) - len(scored),
        "total_failed": 0,
        "company_avg_score": round(statistics.mean(scores), 1) if scores else None,
        "company_median_score": round(statistics.median(scores), 1) if scores else None,
        "pass_rate_pct": round(100 * sum(1 for s in scores if s >= 80) / len(scores), 1) if scores else None,
        "per_rep_avg_score": dict(sorted(per_rep_avg.items(), key=lambda x: -x[1])),
        "failed_calls": [],
        "note": f"Combined from: {', '.join(str(s) for s in source_dirs)} — no calls re-graded.",
    }

    summary_path = OUTPUT_DIR / f"patterns_v3_cet_week_{combined_start}_{combined_end}.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Combined {len(all_grades)} calls into {combined_dir}")
    print(f"Company avg: {summary['company_avg_score']}/100 | Median: {summary['company_median_score']} | Pass rate: {summary['pass_rate_pct']}%")
    print(f"Summary: {summary_path}")
    return str(summary_path)

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python3 scripts/combine_week_grades.py <start> <end> <source_dir1> [<source_dir2> ...]")
        sys.exit(1)
    combine(sys.argv[1], sys.argv[2], sys.argv[3:])
