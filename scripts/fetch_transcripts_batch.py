#!/usr/bin/env python3
"""
fetch_transcripts_batch.py — Fetch and cache transcripts for all candidates in a roster run.

Usage:
    python3 scripts/fetch_transcripts_batch.py output/roster_candidates_2026-06-11.json

Reads a roster_candidates JSON file, fetches each transcript from Dialpad, and saves to
output/transcripts/{call_id}.json. Skips already-cached transcripts.

Output:
    Prints fetch status per call.
    Returns path to a grading_queue JSON with transcript text embedded — ready for Gary to grade.
"""

import os, json, subprocess, argparse, sys
from datetime import datetime
from pathlib import Path

TRANSCRIPT_DIR = Path(__file__).parent.parent / "output" / "transcripts"
OUTPUT_DIR     = Path(__file__).parent.parent / "output"

def get_api_key():
    key = os.environ.get("DIALPAD_API_KEY")
    if not key:
        raise EnvironmentError("DIALPAD_API_KEY not set. Run: source ~/.zshrc")
    return key

def fetch_transcript(call_id, api_key):
    cache_file = TRANSCRIPT_DIR / f"{call_id}.json"
    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f), True

    result = subprocess.run([
        "curl", "-s", "-H", f"Authorization: Bearer {api_key}",
        f"https://dialpad.com/api/v2/transcripts/{call_id}"
    ], capture_output=True, text=True)

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None, False

    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache_file, "w") as f:
        json.dump(data, f, indent=2)

    return data, False

def format_transcript(data):
    lines = data.get("lines", [])
    transcript = []
    speakers = set()

    for l in lines:
        if l.get("type") == "transcript":
            speaker = l.get("name", "?")
            speakers.add(speaker)
            transcript.append(f"{speaker}: {l.get('content', '')}")

    return {
        "speakers": sorted(speakers),
        "full_text": "\n".join(transcript),
        "line_count": len(transcript),
    }

def build_grading_queue(candidates_path):
    api_key = get_api_key()

    with open(candidates_path) as f:
        run_data = json.load(f)

    candidates = run_data.get("candidates", [])
    today = datetime.now().strftime("%Y-%m-%d")
    queue = []
    skipped = []

    print(f"\nFetching transcripts for {len(candidates)} calls...\n")

    for i, c in enumerate(candidates, 1):
        call_id = c["call_id"]
        print(f"  [{i:2}/{len(candidates)}] {c['rep_name']:<30} {c['duration_min']} min  ", end="", flush=True)

        raw, cached = fetch_transcript(call_id, api_key)

        if raw is None:
            print("FAILED — no transcript")
            skipped.append(call_id)
            continue

        formatted = format_transcript(raw)

        if formatted["line_count"] < 5:
            print(f"SKIP — transcript too short ({formatted['line_count']} lines)")
            skipped.append(call_id)
            continue

        status = "cached" if cached else "fetched"
        print(f"{status} ({formatted['line_count']} lines)")

        queue.append({
            "rep_name":     c["rep_name"],
            "rep_id":       c["rep_id"],
            "rep_title":    c.get("rep_title", ""),
            "call_id":      call_id,
            "branch":       c["branch"],
            "duration_min": c["duration_min"],
            "datetime_ct":  c["datetime_ct"],
            "speakers":     formatted["speakers"],
            "transcript":   formatted["full_text"],
            "line_count":   formatted["line_count"],
        })

    queue_path = OUTPUT_DIR / f"grading_queue_{today}.json"
    with open(queue_path, "w") as f:
        json.dump({
            "run_date":      today,
            "total_calls":   len(candidates),
            "gradeable":     len(queue),
            "skipped":       len(skipped),
            "skipped_ids":   skipped,
            "calls":         queue,
        }, f, indent=2)

    print(f"\nGrading queue ready: {len(queue)} calls")
    print(f"Saved to: output/grading_queue_{today}.json")
    return str(queue_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch transcripts for a roster candidate run")
    parser.add_argument("candidates_file", help="Path to roster_candidates_YYYY-MM-DD.json")
    args = parser.parse_args()

    build_grading_queue(args.candidates_file)
