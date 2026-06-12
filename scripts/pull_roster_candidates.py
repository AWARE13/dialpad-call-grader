#!/usr/bin/env python3
"""
pull_roster_candidates.py — Pull up to 2 qualifying sales calls per rep from the grading roster.

Usage:
    python3 scripts/pull_roster_candidates.py
    python3 scripts/pull_roster_candidates.py --days 14       # look back 14 days (default: 7)
    python3 scripts/pull_roster_candidates.py --calls 3       # up to 3 calls per rep (default: 2)
    python3 scripts/pull_roster_candidates.py --rep "Nicole"  # single rep (partial name match)

Output:
    Prints per-rep summary to stdout.
    Saves to output/roster_candidates_YYYY-MM-DD.json
"""

import os, json, subprocess, argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROSTER_PATH = Path.home() / "Documents/GitHub/cos-amanda/data/dialpad-grading-roster.json"
OUTPUT_DIR  = Path(__file__).parent.parent / "output"
MIN_DURATION_MS = 300000  # 5 minutes

def get_api_key():
    key = os.environ.get("DIALPAD_API_KEY")
    if not key:
        raise EnvironmentError("DIALPAD_API_KEY not set. Run: source ~/.zshrc")
    return key

def api_get(endpoint, api_key):
    result = subprocess.run([
        "curl", "-s", "-H", f"Authorization: Bearer {api_key}",
        f"https://dialpad.com/api/v2/{endpoint}"
    ], capture_output=True, text=True)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}

def load_roster(rep_filter=None):
    with open(ROSTER_PATH) as f:
        data = json.load(f)
    reps = [r for r in data["reps"] if r.get("active", True)]
    if rep_filter:
        reps = [r for r in reps if rep_filter.lower() in r["name"].lower()]
    return reps

def pull_calls_for_rep(rep, api_key, cutoff_ms, calls_per_rep):
    calls = []
    cursor = None
    pages = 0

    while len(calls) < calls_per_rep and pages < 5:
        url = f"call?target_type=user&target_id={rep['dialpad_id']}&limit=50"
        if cursor:
            url += f"&cursor={cursor}"

        data = api_get(url, api_key)
        items = data.get("items", [])
        cursor = data.get("cursor")
        pages += 1

        for c in items:
            started = int(c.get("date_started") or 0)

            if started < cutoff_ms:
                return calls

            dur = float(c.get("duration") or 0)
            state = c.get("state", "")
            entry_type = c.get("entry_point_target", {}).get("type", "")

            if dur >= MIN_DURATION_MS and state == "hangup" and entry_type == "call_center":
                dt = datetime.fromtimestamp(started / 1000, tz=timezone.utc)
                calls.append({
                    "rep_name":    rep["name"],
                    "rep_id":      rep["dialpad_id"],
                    "rep_title":   rep.get("title", ""),
                    "call_id":     c["call_id"],
                    "duration_min": round(dur / 60000, 1),
                    "datetime_utc": dt.isoformat(),
                    "datetime_ct":  dt.strftime("%Y-%m-%d %H:%M CT"),
                    "branch":      c.get("entry_point_target", {}).get("name", "Unknown"),
                    "external_number": c.get("external_number", ""),
                })
                if len(calls) >= calls_per_rep:
                    break

        if not cursor:
            break

    return calls

def pull_roster_candidates(rep_filter=None, days=7, calls_per_rep=2):
    api_key = get_api_key()
    reps = load_roster(rep_filter)
    cutoff_ms = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)

    print(f"\nWeekly grading run — {datetime.now().strftime('%Y-%m-%d')}")
    print(f"Lookback: {days} days | Target: {calls_per_rep} calls/rep | Roster: {len(reps)} reps\n")

    all_candidates = []
    no_calls = []

    for rep in reps:
        calls = pull_calls_for_rep(rep, api_key, cutoff_ms, calls_per_rep)
        if calls:
            all_candidates.extend(calls)
            print(f"  {rep['name']:<30} {len(calls)} call(s)")
        else:
            no_calls.append(rep["name"])
            print(f"  {rep['name']:<30} — no qualifying calls")

    today = datetime.now().strftime("%Y-%m-%d")
    output_path = OUTPUT_DIR / f"roster_candidates_{today}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({
            "run_date": today,
            "lookback_days": days,
            "calls_per_rep": calls_per_rep,
            "total_reps": len(reps),
            "reps_with_calls": len(reps) - len(no_calls),
            "reps_no_calls": no_calls,
            "total_calls": len(all_candidates),
            "candidates": all_candidates,
        }, f, indent=2)

    print(f"\nTotal: {len(all_candidates)} calls across {len(reps) - len(no_calls)} reps")
    if no_calls:
        print(f"No calls ({len(no_calls)} reps): {', '.join(no_calls)}")
    print(f"Saved to output/roster_candidates_{today}.json")

    return all_candidates

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pull weekly grading candidates from roster")
    parser.add_argument("--days",  type=int, default=7, help="Lookback window in days (default: 7)")
    parser.add_argument("--calls", type=int, default=2, help="Max calls per rep (default: 2)")
    parser.add_argument("--rep",   help="Filter to one rep (partial name match)")
    args = parser.parse_args()

    pull_roster_candidates(rep_filter=args.rep, days=args.days, calls_per_rep=args.calls)
