#!/usr/bin/env python3
"""
pull_candidates.py — Pull and filter sales call candidates from all Dialpad call centers.

Usage:
    python3 scripts/pull_candidates.py
    python3 scripts/pull_candidates.py --branch "North Austin"
    python3 scripts/pull_candidates.py --limit 100

Output:
    Prints a table of candidates to stdout.
    Saves candidates to output/candidates_YYYY-MM-DD.json
"""

import os, json, subprocess, argparse
from datetime import datetime, timezone
from pathlib import Path

# Load call center config
CONFIG_PATH = Path(__file__).parent.parent / "config" / "call_centers.json"
OUTPUT_DIR  = Path(__file__).parent.parent / "output"

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
    return json.loads(result.stdout)

def pull_candidates(branch_filter=None, limit=50):
    api_key = get_api_key()
    with open(CONFIG_PATH) as f:
        config = json.load(f)

    call_centers = config["call_centers"]
    if branch_filter:
        call_centers = {k: v for k, v in call_centers.items() if branch_filter.lower() in k.lower()}

    candidates = []
    seen = set()

    for branch, cc_id in call_centers.items():
        print(f"  Pulling {branch}...", end=" ", flush=True)
        data = api_get(f"call?target_type=callcenter&target_id={cc_id}&limit={limit}", api_key)
        calls = data.get("items", [])
        branch_candidates = 0

        for c in calls:
            dur = float(c.get("duration") or 0)
            direction = c.get("direction", "")
            state = c.get("state", "")
            call_id = c.get("call_id", "")
            started = c.get("date_started", 0)
            ext_num = c.get("external_number", "")

            # Dedupe by (external_number, minute)
            key = (ext_num, round(int(started) / 60000))
            if key in seen:
                continue
            seen.add(key)

            # Pre-filter: inbound, >5 min, hangup state
            if direction == "inbound" and dur > 300000 and state == "hangup":
                dt = datetime.fromtimestamp(int(started) / 1000, tz=timezone.utc)
                candidates.append({
                    "branch": branch,
                    "call_id": call_id,
                    "duration_min": round(dur / 60000, 1),
                    "datetime_utc": dt.isoformat(),
                    "datetime_ct": dt.strftime("%Y-%m-%d %H:%M CT"),
                    "external_number": ext_num
                })
                branch_candidates += 1

        print(f"{branch_candidates} candidates")

    # Sort by most recent first
    candidates.sort(key=lambda x: x["datetime_utc"], reverse=True)

    # Save output
    today = datetime.now().strftime("%Y-%m-%d")
    output_path = OUTPUT_DIR / f"candidates_{today}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(candidates, f, indent=2)

    return candidates

def print_table(candidates):
    print(f"\n{'Date/Time CT':<20} {'Branch':<15} {'Min':>5}  {'Call ID'}")
    print("-" * 70)
    for c in candidates:
        dt = c["datetime_ct"].replace(" CT", "")
        print(f"{dt:<20} {c['branch']:<15} {c['duration_min']:>5}  {c['call_id']}")
    print(f"\nTotal: {len(candidates)} candidates")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pull Dialpad sales call candidates")
    parser.add_argument("--branch", help="Filter to specific branch (partial match)")
    parser.add_argument("--limit", type=int, default=50, help="Calls to pull per branch (default: 50)")
    args = parser.parse_args()

    print(f"\nPulling candidates from {'all branches' if not args.branch else args.branch}...")
    candidates = pull_candidates(branch_filter=args.branch, limit=args.limit)
    print_table(candidates)
    print(f"\nSaved to output/candidates_{datetime.now().strftime('%Y-%m-%d')}.json")
