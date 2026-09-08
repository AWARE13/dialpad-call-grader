#!/usr/bin/env python3
"""
pull_week_range_cet.py — Same as pull_week_range.py but sources the CET-only roster
(cet-agenda-opener-roster.json) instead of the full 34-person sales roster. Built for
Amanda's 9/7 correction: the Jeff-rubric rollout is CET only, not the whole sales team.
"""
import os, json, subprocess, argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROSTER_PATH = Path.home() / "Documents/GitHub/cos-amanda/data/cet-agenda-opener-roster.json"
OUTPUT_DIR  = Path(__file__).parent.parent / "output"
MIN_DURATION_MS = 300000
CT_OFFSET_HOURS = -5

def get_api_key():
    key = os.environ.get("DIALPAD_API_KEY")
    if not key:
        raise EnvironmentError("DIALPAD_API_KEY not set. Run: source ~/.zshrc")
    return key

def api_get(endpoint, api_key):
    result = subprocess.run(["curl", "-s", "-m", "30", "-H", f"Authorization: Bearer {api_key}",
        f"https://dialpad.com/api/v2/{endpoint}"], capture_output=True, text=True)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}

def load_roster():
    with open(ROSTER_PATH) as f:
        data = json.load(f)
    return data["reps"]

def ct_date_to_utc_ms(date_str, end_of_day=False):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    if end_of_day:
        dt = dt.replace(hour=23, minute=59, second=59)
    dt_utc = (dt - timedelta(hours=CT_OFFSET_HOURS)).replace(tzinfo=timezone.utc)
    return int(dt_utc.timestamp() * 1000)

def pull_calls_for_rep(rep, api_key, start_ms, end_ms):
    calls = []
    cursor = None
    pages = 0
    while pages < 20:
        url = f"call?target_type=user&target_id={rep['dialpad_id']}&limit=50"
        if cursor:
            url += f"&cursor={cursor}"
        data = api_get(url, api_key)
        items = data.get("items", [])
        cursor = data.get("cursor")
        pages += 1
        if not items:
            break
        for c in items:
            started = int(c.get("date_started") or 0)
            if started < start_ms:
                return calls
            if started > end_ms:
                continue
            dur = float(c.get("duration") or 0)
            state = c.get("state", "")
            entry_type = c.get("entry_point_target", {}).get("type", "")
            if dur >= MIN_DURATION_MS and state == "hangup" and entry_type == "call_center":
                dt = datetime.fromtimestamp(started / 1000, tz=timezone.utc)
                calls.append({
                    "rep_name": rep["name"], "rep_id": rep["dialpad_id"],
                    "call_id": c["call_id"], "duration_min": round(dur / 60000, 1),
                    "datetime_utc": dt.isoformat(), "datetime_ct": dt.strftime("%Y-%m-%d %H:%M CT"),
                    "branch": c.get("entry_point_target", {}).get("name", "Unknown"),
                    "external_number": c.get("external_number", ""),
                })
        if not cursor:
            break
    return calls

def pull_week_range(start_date, end_date):
    api_key = get_api_key()
    reps = load_roster()
    start_ms = ct_date_to_utc_ms(start_date, end_of_day=False)
    end_ms   = ct_date_to_utc_ms(end_date, end_of_day=True)
    print(f"\nCET week-range pull — {start_date} to {end_date} (CT)")
    print(f"Roster: {len(reps)} CET reps\n")
    all_candidates = []
    no_calls = []
    for rep in reps:
        calls = pull_calls_for_rep(rep, api_key, start_ms, end_ms)
        if calls:
            all_candidates.extend(calls)
            print(f"  {rep['name']:<30} {len(calls)} call(s)")
        else:
            no_calls.append(rep["name"])
            print(f"  {rep['name']:<30} — no qualifying calls")
    output_path = OUTPUT_DIR / f"roster_candidates_cet_week_{start_date}_{end_date}.json"
    with open(output_path, "w") as f:
        json.dump({"week_start": start_date, "week_end": end_date, "total_reps": len(reps),
                   "reps_with_calls": len(reps) - len(no_calls), "reps_no_calls": no_calls,
                   "total_calls": len(all_candidates), "candidates": all_candidates}, f, indent=2)
    print(f"\nTotal: {len(all_candidates)} calls across {len(reps) - len(no_calls)} reps")
    if no_calls:
        print(f"No calls: {', '.join(no_calls)}")
    print(f"Saved to {output_path}")
    return str(output_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    args = parser.parse_args()
    pull_week_range(args.start, args.end)
