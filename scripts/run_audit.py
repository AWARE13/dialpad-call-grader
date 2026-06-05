#!/usr/bin/env python3
"""
run_audit.py — Full audit pipeline: pull candidates → grade top calls → produce report.

Usage:
    python3 scripts/run_audit.py               # Grade top 5 candidates
    python3 scripts/run_audit.py --count 10    # Grade top 10
    python3 scripts/run_audit.py --branch "Dallas" --count 3

What it does:
    1. Pulls candidates from all branches (or filtered branch)
    2. Sorts by duration descending (longer = more likely full sales call)
    3. Prints candidates for Gary to review + classify
    4. Gary grades each qualifying call against config/rubric.md
    5. Saves grades to output/grades/

Gary's role in this loop:
    - Reads each transcript
    - Classifies: full sales call / walkthrough scheduler / skip
    - Grades against the rubric section by section
    - Notes pattern-level findings across calls
    - Posts summary to Monday Sky Board pulse 12206626312
"""

import os, json, argparse
from datetime import datetime
from pathlib import Path

# Import pull function
import sys
sys.path.insert(0, str(Path(__file__).parent))
from pull_candidates import pull_candidates, print_table
from grade_call import fetch_transcript, format_transcript

RUBRIC_PATH   = Path(__file__).parent.parent / "config" / "rubric.md"
OUTPUT_DIR    = Path(__file__).parent.parent / "output" / "grades"
PATTERNS_FILE = Path(__file__).parent.parent / "output" / "patterns.json"

def load_rubric():
    with open(RUBRIC_PATH) as f:
        return f.read()

def load_patterns():
    if PATTERNS_FILE.exists():
        with open(PATTERNS_FILE) as f:
            return json.load(f)
    return {
        "total_calls_graded": 0,
        "save_your_ass_hit": 0,
        "meet_your_mover_hit": 0,
        "on_time_guarantee_hit": 0,
        "email_handoff_hit": 0,
        "agenda_opener_hit": 0,
        "scores": []
    }

def save_patterns(patterns):
    PATTERNS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PATTERNS_FILE, "w") as f:
        json.dump(patterns, f, indent=2)

def run_audit(branch_filter=None, count=5):
    api_key = os.environ.get("DIALPAD_API_KEY")
    if not api_key:
        raise EnvironmentError("DIALPAD_API_KEY not set. Run: source ~/.zshrc")

    rubric = load_rubric()
    patterns = load_patterns()

    print(f"\n{'='*60}")
    print(f"DIALPAD CALL AUDIT — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    # Step 1: Pull candidates
    print("Step 1: Pulling candidates from all branches...")
    candidates = pull_candidates(branch_filter=branch_filter)
    print_table(candidates[:20])

    # Step 2: Select top N by duration (longest = most likely full sales call)
    top = candidates[:count]
    print(f"\nStep 2: Pulling transcripts for top {count} by duration...")
    print("Gary will classify and grade each one.\n")

    for i, c in enumerate(top, 1):
        print(f"\n{'='*60}")
        print(f"CALL {i}/{count}: {c['branch']} | {c['duration_min']} min | {c['datetime_ct']}")
        print(f"Call ID: {c['call_id']}")
        print(f"{'='*60}")

        raw = fetch_transcript(c["call_id"], api_key)
        formatted = format_transcript(raw)

        print(f"Speakers: {', '.join(formatted['speakers'])}")
        print(f"Lines: {len(formatted['transcript_lines'])} | Moments: {len(formatted['moments'])}")
        print("\n--- TRANSCRIPT ---")
        print(formatted["full_text"])
        print("\n--- KEY AI MOMENTS ---")
        for m in formatted["moments"][:10]:
            print(m)
        print(f"\n[Gary: classify this call and grade against config/rubric.md]")
        print(f"[Then save grade to output/grades/ and update output/patterns.json]")

    print(f"\n{'='*60}")
    print("AUDIT COMPLETE")
    print(f"Candidates found: {len(candidates)}")
    print(f"Calls reviewed: {count}")
    print(f"\nPattern tracker (all-time, n={patterns['total_calls_graded']}):")
    if patterns["total_calls_graded"] > 0:
        n = patterns["total_calls_graded"]
        print(f"  Save Your Ass:       {patterns['save_your_ass_hit']}/{n} ({round(patterns['save_your_ass_hit']/n*100)}%)")
        print(f"  Meet Your Mover:     {patterns['meet_your_mover_hit']}/{n} ({round(patterns['meet_your_mover_hit']/n*100)}%)")
        print(f"  On-Time Guarantee:   {patterns['on_time_guarantee_hit']}/{n} ({round(patterns['on_time_guarantee_hit']/n*100)}%)")
        print(f"  Email handoff:       {patterns['email_handoff_hit']}/{n} ({round(patterns['email_handoff_hit']/n*100)}%)")
        print(f"  Agenda opener:       {patterns['agenda_opener_hit']}/{n} ({round(patterns['agenda_opener_hit']/n*100)}%)")
    print(f"\nPost findings to Monday: https://einsteinmoving.monday.com/boards/1146915251/pulses/12206626312")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a full Dialpad call audit")
    parser.add_argument("--branch", help="Filter to specific branch")
    parser.add_argument("--count", type=int, default=5, help="Number of calls to grade (default: 5)")
    args = parser.parse_args()

    run_audit(branch_filter=args.branch, count=args.count)
