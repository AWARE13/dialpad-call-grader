#!/usr/bin/env python3
"""
grade_call.py — Pull a transcript and grade a single call against the 85-pt rubric.

Usage:
    python3 scripts/grade_call.py --call_id 6581645196206080 --branch "Dallas"
    python3 scripts/grade_call.py --call_id 6581645196206080  (branch auto-detected if omitted)

Output:
    Prints scorecard to stdout.
    Saves markdown + JSON to output/grades/YYYY-MM-DD_branch_callid.md
"""

import os, json, subprocess, argparse
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "output"
RUBRIC_PATH = Path(__file__).parent.parent / "config" / "rubric.md"
TRANSCRIPT_CACHE = Path(__file__).parent.parent / "output" / "transcripts"

def get_api_key():
    key = os.environ.get("DIALPAD_API_KEY")
    if not key:
        raise EnvironmentError("DIALPAD_API_KEY not set. Run: source ~/.zshrc")
    return key

def fetch_transcript(call_id, api_key):
    # Check cache first
    cache_file = TRANSCRIPT_CACHE / f"{call_id}.json"
    if cache_file.exists():
        print(f"  (using cached transcript)")
        with open(cache_file) as f:
            return json.load(f)

    result = subprocess.run([
        "curl", "-s", "-H", f"Authorization: Bearer {api_key}",
        f"https://dialpad.com/api/v2/transcripts/{call_id}"
    ], capture_output=True, text=True)
    data = json.loads(result.stdout)

    # Cache it
    TRANSCRIPT_CACHE.mkdir(parents=True, exist_ok=True)
    with open(cache_file, "w") as f:
        json.dump(data, f, indent=2)

    return data

def format_transcript(data):
    lines = data.get("lines", [])
    transcript = []
    moments = []
    speakers = set()

    for l in lines:
        if l.get("type") == "transcript":
            speaker = l.get("name", "?")
            speakers.add(speaker)
            transcript.append(f"{speaker}: {l.get('content', '')}")
        elif l.get("type") == "moment":
            moments.append(f"{l.get('name','?')}: {l.get('content','')}")

    return {
        "speakers": list(speakers),
        "transcript_lines": transcript,
        "moments": moments,
        "full_text": "\n".join(transcript)
    }

def grade_with_claude(call_id, branch, transcript_data, rubric_text):
    """
    Gary reads the transcript and grades against the rubric.
    This function is the entry point for the AI grading step.
    In a Claude Code session, Gary reads the transcript and rubric directly.
    """
    print(f"\n=== TRANSCRIPT: {call_id} ({branch}) ===")
    print(f"Speakers: {', '.join(transcript_data['speakers'])}")
    print(f"Lines: {len(transcript_data['transcript_lines'])}")
    print("\n--- FULL TRANSCRIPT ---")
    print(transcript_data["full_text"])
    print("\n--- AI MOMENTS ---")
    for m in transcript_data["moments"][:15]:
        print(m)
    print("\n[Gary grades this call against config/rubric.md]")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Grade a single Dialpad sales call")
    parser.add_argument("--call_id", required=True, help="Dialpad call ID")
    parser.add_argument("--branch", default="Unknown", help="Branch name")
    args = parser.parse_args()

    api_key = get_api_key()

    print(f"\nFetching transcript for call {args.call_id}...")
    raw = fetch_transcript(args.call_id, api_key)
    formatted = format_transcript(raw)

    with open(RUBRIC_PATH) as f:
        rubric = f.read()

    grade_with_claude(args.call_id, args.branch, formatted, rubric)
