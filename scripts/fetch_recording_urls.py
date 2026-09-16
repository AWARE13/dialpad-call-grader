#!/usr/bin/env python3
"""
fetch_recording_urls.py — Fetches the REAL recording URL per call from the
Dialpad /call/{call_id} endpoint and caches it to output/recordings/{call_id}.json.

Why this exists: the report builder used to guess the recording URL as
https://dialpad.com/blob/adminrecording/{call_id}.mp3 — but the recording has
its own internal ID, separate from the call_id. That guess was wrong for
every single call. This fetches the real admin_recording_urls / recording_url
fields instead.

Usage:
    python3 scripts/fetch_recording_urls.py output/weekly/grades/v2_cet_week_2026-09-06_2026-09-12
"""
import json, subprocess, sys, os
from pathlib import Path

BASE = Path(__file__).parent.parent
REC_DIR = BASE / "output" / "recordings"
REC_DIR.mkdir(parents=True, exist_ok=True)

def get_dialpad_key():
    key = os.environ.get("DIALPAD_API_KEY")
    if not key:
        raise EnvironmentError("DIALPAD_API_KEY not set. Run: source ~/.zshrc")
    return key

def fetch_one(call_id, api_key):
    cache_file = REC_DIR / f"{call_id}.json"
    if cache_file.exists():
        return json.load(open(cache_file))
    result = subprocess.run(
        ["curl", "-s", "-m", "20", "-H", f"Authorization: Bearer {api_key}",
         f"https://dialpad.com/api/v2/call/{call_id}"],
        capture_output=True, text=True,
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        data = {}
    admin_urls = data.get("admin_recording_urls") or []
    rec_urls = data.get("recording_url") or []
    record = {
        "call_id": call_id,
        "admin_recording_url": admin_urls[0] if admin_urls else None,
        "recording_url": rec_urls[0] if rec_urls else None,
    }
    with open(cache_file, "w") as f:
        json.dump(record, f, indent=2)
    return record

def main():
    grades_dir = Path(sys.argv[1])
    api_key = get_dialpad_key()
    call_ids = sorted({json.load(open(f))["call_id"] for f in grades_dir.glob("*.json")})
    found, missing, cached = 0, 0, 0
    for i, cid in enumerate(call_ids, 1):
        was_cached = (REC_DIR / f"{cid}.json").exists()
        rec = fetch_one(cid, api_key)
        if was_cached:
            cached += 1
        if rec.get("admin_recording_url") or rec.get("recording_url"):
            found += 1
        else:
            missing += 1
        if i % 50 == 0:
            print(f"  [{i}/{len(call_ids)}] found={found} missing={missing}")
    print(f"Done. {len(call_ids)} calls, {found} with a real recording URL, {missing} with none, {cached} already cached.")

if __name__ == "__main__":
    main()
