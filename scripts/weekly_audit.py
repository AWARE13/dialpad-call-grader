#!/usr/bin/env python3
"""
weekly_audit.py — Weekly grading prep: pull candidates + fetch transcripts → grading queue.

This script handles the DATA COLLECTION step only. Grading happens natively inside
a Gary (Claude Code) session using the Agent tool — no external API key required.

Usage:
    python3 scripts/weekly_audit.py              # full 33-rep roster, 2 calls each, 7-day lookback
    python3 scripts/weekly_audit.py --days 14    # extend lookback window
    python3 scripts/weekly_audit.py --calls 3    # 3 calls per rep
    python3 scripts/weekly_audit.py --rep "Nicole"  # single rep
    python3 scripts/weekly_audit.py --dry-run    # pull candidates only, skip transcript fetch

Output:
    output/roster_candidates_YYYY-MM-DD.json  — raw candidate list
    output/grading_queue_YYYY-MM-DD.json      — transcripts embedded, ready for Gary to grade
"""

import argparse, sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pull_roster_candidates import pull_roster_candidates
from fetch_transcripts_batch import build_grading_queue

OUTPUT_DIR = Path(__file__).parent.parent / "output"

def run_weekly_prep(rep_filter=None, days=7, calls_per_rep=2, dry_run=False):
    today = datetime.now().strftime("%Y-%m-%d")

    print(f"\n{'='*60}")
    print(f"WEEKLY AUDIT PREP — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    print("Step 1: Pulling candidates from roster...\n")
    candidates = pull_roster_candidates(rep_filter=rep_filter, days=days, calls_per_rep=calls_per_rep)

    if not candidates:
        print("\nNo qualifying calls found. Try --days 14")
        return None

    candidates_path = OUTPUT_DIR / f"roster_candidates_{today}.json"

    if dry_run:
        print(f"\nDry run complete. {len(candidates)} calls ready.")
        print(f"Candidate list saved to: output/roster_candidates_{today}.json")
        return str(candidates_path)

    print(f"\nStep 2: Fetching transcripts...\n")
    queue_path = build_grading_queue(candidates_path)

    print(f"\n{'='*60}")
    print(f"PREP COMPLETE — ready for Gary to grade")
    print(f"Grading queue: output/grading_queue_{today}.json")
    print(f"\nGary: read the grading queue and grade each call using the rubric")
    print(f"at config/rubric.md, then build the HTML report.")
    print(f"{'='*60}\n")

    return queue_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prep the weekly Dialpad call grading run")
    parser.add_argument("--days",    type=int, default=7,  help="Lookback window in days (default: 7)")
    parser.add_argument("--calls",   type=int, default=2,  help="Max calls per rep (default: 2)")
    parser.add_argument("--rep",     help="Single rep only (partial name match)")
    parser.add_argument("--dry-run", action="store_true",  help="Pull candidates only, no transcript fetch")
    args = parser.parse_args()

    run_weekly_prep(rep_filter=args.rep, days=args.days, calls_per_rep=args.calls, dry_run=args.dry_run)
