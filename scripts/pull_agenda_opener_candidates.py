#!/usr/bin/env python3
"""
pull_agenda_opener_candidates.py — CET-only pull for the new agenda-opener script check
(rollout 2026-08-19). Narrow companion to pull_roster_candidates.py / weekly_audit.py —
NOT the full 85-pt scorecard pipeline.

Usage:
    python3 scripts/pull_agenda_opener_candidates.py
    python3 scripts/pull_agenda_opener_candidates.py --since 2026-08-19
    python3 scripts/pull_agenda_opener_candidates.py --rep "Jules"   # single rep, partial match

Dedupes against output/agenda_opener/graded_call_ids.json so re-running (e.g. the daily
scheduled task) only surfaces calls not already queued/graded.

Output:
    output/agenda_opener/queue_YYYY-MM-DD.json — one entry per new candidate call:
    rep, call_id, recording_url, duration_min, transcript_text, agenda_segment (bounded
    slice of the transcript), talk_ratio_customer_pct (computed from line timestamps).
"""

import os, json, subprocess, argparse, re
from datetime import datetime, timezone
from pathlib import Path

ROSTER_PATH   = Path.home() / "Documents/GitHub/cos-amanda/data/cet-agenda-opener-roster.json"
OUTPUT_DIR    = Path(__file__).parent.parent / "output" / "agenda_opener"
TRANSCRIPT_DIR = Path(__file__).parent.parent / "output" / "transcripts"
GRADED_IDS_PATH = OUTPUT_DIR / "graded_call_ids.json"
MIN_DURATION_MS = 300000  # 5 minutes, same pre-filter as the main pipeline

DEFAULT_SINCE = "2026-08-19"  # script rollout date — never pull calls before this

AGENDA_OPENER_CUES = [
    "biggest concern", "most important thing", "what are your biggest",
    "want answered", "want answers to", "talk about your move",
]
PROBE_CUES = [
    "zip code", "square feet", "sq ft", "bedrooms", "how many stairs",
    "stairs at", "floors at", "storage unit", "packing needs", "how many boxes",
]


def get_api_key():
    key = os.environ.get("DIALPAD_API_KEY")
    if not key:
        raise EnvironmentError("DIALPAD_API_KEY not set. Run: source ~/.zshrc")
    return key


def api_get(endpoint, api_key):
    result = subprocess.run(
        ["curl", "-s", "-m", "30", "-H", f"Authorization: Bearer {api_key}",
         f"https://dialpad.com/api/v2/{endpoint}"],
        capture_output=True, text=True,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}


def load_roster(rep_filter=None):
    with open(ROSTER_PATH) as f:
        data = json.load(f)
    reps = data["reps"]
    if rep_filter:
        reps = [r for r in reps if rep_filter.lower() in r["name"].lower()]
    return reps, data.get("gaps", [])


def load_graded_ids():
    if GRADED_IDS_PATH.exists():
        with open(GRADED_IDS_PATH) as f:
            return set(json.load(f))
    return set()


def save_graded_ids(ids):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(GRADED_IDS_PATH, "w") as f:
        json.dump(sorted(ids), f, indent=2)


def pull_calls_for_rep(rep, api_key, since_ms, already_graded):
    calls = []
    cursor = None
    pages = 0
    while pages < 5:
        url = f"call?target_type=user&target_id={rep['dialpad_id']}&limit=50"
        if cursor:
            url += f"&cursor={cursor}"
        data = api_get(url, api_key)
        items = data.get("items", [])
        for c in items:
            started = int(c.get("date_started", 0) or 0)
            if started < since_ms:
                continue
            if str(c.get("call_id") or c.get("id")) in already_graded:
                continue
            if int(c.get("duration", 0) or 0) < MIN_DURATION_MS:
                continue
            if c.get("direction") != "inbound":
                continue
            calls.append(c)
        cursor = data.get("cursor")
        pages += 1
        if not cursor or not items:
            break
    return calls


def fetch_transcript(call_id, api_key):
    cache_file = TRANSCRIPT_DIR / f"{call_id}.json"
    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)
    result = subprocess.run(
        ["curl", "-s", "-H", f"Authorization: Bearer {api_key}",
         f"https://dialpad.com/api/v2/transcripts/{call_id}"],
        capture_output=True, text=True,
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache_file, "w") as f:
        json.dump(data, f, indent=2)
    return data


def find_agenda_segment(lines, rep_name):
    """
    Locate the agenda-opener exchange: from the rep's opener question through
    the point the rep starts standard probing (or a capped window if probing
    never clearly starts). Returns (start_idx, end_idx, transcript_lines);
    start_idx is None if the opener cue is absent anywhere in the call.
    """
    transcript_lines = [l for l in lines if l.get("type") == "transcript"]
    start_idx = None
    for i, l in enumerate(transcript_lines):
        if l.get("name") != rep_name:
            continue
        content = (l.get("content") or "").lower()
        if any(cue in content for cue in AGENDA_OPENER_CUES):
            start_idx = i
            break
    if start_idx is None:
        return None, None, transcript_lines

    end_idx = None
    for i in range(start_idx + 1, len(transcript_lines)):
        l = transcript_lines[i]
        if l.get("name") != rep_name:
            continue
        content = (l.get("content") or "").lower()
        if any(cue in content for cue in PROBE_CUES):
            end_idx = i
            break
    if end_idx is None:
        # probing never clearly starts — cap the window so one long call
        # doesn't get treated as "all agenda exchange"
        end_idx = min(len(transcript_lines), start_idx + 20)

    return start_idx, end_idx, transcript_lines


def compute_talk_ratio(transcript_lines, start_idx, end_idx, rep_name):
    """
    Talk-time ratio by elapsed wall-clock time per speaker within [start_idx, end_idx),
    using each line's timestamp and the next line's timestamp as that speaker's turn
    duration. Last line in the segment is credited up to the following line's start
    time (or a flat 3s if it's the last line overall).
    """
    segment = transcript_lines[start_idx:end_idx]
    if len(segment) < 2:
        return None

    def parse_ts(l):
        try:
            return datetime.fromisoformat(l["time"])
        except (KeyError, ValueError):
            return None

    customer_ms = 0
    rep_ms = 0
    for i in range(len(segment) - 1):
        t0 = parse_ts(segment[i])
        t1 = parse_ts(segment[i + 1])
        if t0 is None or t1 is None:
            continue
        delta_ms = max((t1 - t0).total_seconds() * 1000, 0)
        if segment[i].get("name") == rep_name:
            rep_ms += delta_ms
        else:
            customer_ms += delta_ms

    total = customer_ms + rep_ms
    if total == 0:
        return None
    return round(100 * customer_ms / total, 1)


def format_full_text(lines):
    out = []
    for l in lines:
        if l.get("type") == "transcript":
            out.append(f"{l.get('name', '?')}: {l.get('content', '')}")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=DEFAULT_SINCE, help="YYYY-MM-DD, calls before this are never pulled")
    ap.add_argument("--rep", default=None, help="partial name match, single rep")
    args = ap.parse_args()

    since_dt = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if since_dt < datetime.strptime(DEFAULT_SINCE, "%Y-%m-%d").replace(tzinfo=timezone.utc):
        raise SystemExit(f"--since cannot precede the script rollout date {DEFAULT_SINCE}")
    since_ms = int(since_dt.timestamp() * 1000)

    api_key = get_api_key()
    roster, gaps = load_roster(args.rep)
    already_graded = load_graded_ids()

    if gaps and not args.rep:
        print(f"NOTE: {len(gaps)} rep(s) excluded from this pull, unresolved roster gaps:")
        for g in gaps:
            print(f"  - {g['pacing_name']}: {g['issue']}")

    candidates = []
    for rep in roster:
        calls = pull_calls_for_rep(rep, api_key, since_ms, already_graded)
        for c in calls:
            call_id = str(c.get("call_id") or c.get("id"))
            raw = fetch_transcript(call_id, api_key)
            if not raw or not raw.get("lines"):
                continue
            speaker_name = rep.get("dialpad_display_name", rep["name"])
            start_idx, end_idx, transcript_only = find_agenda_segment(raw["lines"], speaker_name)
            if start_idx is None:
                talk_ratio = None
                segment_text = None
            else:
                talk_ratio = compute_talk_ratio(transcript_only, start_idx, end_idx, speaker_name)
                segment_text = "\n".join(
                    f"{l.get('name','?')}: {l.get('content','')}" for l in transcript_only[start_idx:end_idx]
                )

            candidates.append({
                "rep": rep["name"],
                "call_id": call_id,
                "recording_url": c.get("recording_url") or c.get("admin_call_recording_urls", [None])[0],
                "duration_min": round(int(c.get("duration", 0) or 0) / 60000, 1),
                "date_started": c.get("date_started"),
                "agenda_opener_found": start_idx is not None,
                "talk_ratio_customer_pct": talk_ratio,
                "agenda_segment_text": segment_text,
                "full_transcript_text": format_full_text(raw["lines"]),
            })
            already_graded.add(call_id)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    out_path = OUTPUT_DIR / f"queue_{today}.json"

    # Merge into today's existing queue file rather than overwrite — a second
    # run the same day (or a retry) must not drop rows an earlier run already
    # wrote, since dedup means those rows won't be re-discovered.
    existing = []
    if out_path.exists():
        with open(out_path) as f:
            existing = json.load(f)
    existing_ids = {c["call_id"] for c in existing}
    merged = existing + [c for c in candidates if c["call_id"] not in existing_ids]

    with open(out_path, "w") as f:
        json.dump(merged, f, indent=2)
    save_graded_ids(already_graded)

    print(f"\n{len(candidates)} new candidate call(s) written to {out_path}")
    for c in candidates:
        flag = "opener found" if c["agenda_opener_found"] else "NO OPENER DETECTED"
        ratio = f"{c['talk_ratio_customer_pct']}% customer talk" if c["talk_ratio_customer_pct"] is not None else "ratio n/a"
        print(f"  - {c['rep']}: {flag}, {ratio}")


if __name__ == "__main__":
    main()
