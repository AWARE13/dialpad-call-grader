#!/usr/bin/env python3
"""
grade_call_auto.py — Automated grading via Anthropic API. Grades one call and returns structured JSON.

Used by weekly_audit.py. Not intended for direct use — call grade_call_auto() from other scripts.
"""

import os, json, subprocess
from pathlib import Path

RUBRIC_PATH    = Path(__file__).parent.parent / "config" / "rubric.md"
TRANSCRIPT_DIR = Path(__file__).parent.parent / "output" / "transcripts"

SYSTEM_PROMPT = """You are an expert sales call evaluator for Einstein Moving Company.
You grade sales calls against a detailed rubric and return structured JSON.
Be fair but rigorous. Base every score strictly on what is said in the transcript — do not assume items were covered if they are absent.
N/A rule: if a rubric item does not apply to this specific call (e.g. packing pricing when no packing was discussed), award the point automatically."""

def get_anthropic_key():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set. Run: source ~/.zshrc")
    return key

def get_dialpad_key():
    key = os.environ.get("DIALPAD_API_KEY")
    if not key:
        raise EnvironmentError("DIALPAD_API_KEY not set. Run: source ~/.zshrc")
    return key

def fetch_transcript(call_id):
    api_key = get_dialpad_key()
    cache_file = TRANSCRIPT_DIR / f"{call_id}.json"
    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)

    result = subprocess.run([
        "curl", "-s", "-H", f"Authorization: Bearer {api_key}",
        f"https://dialpad.com/api/v2/transcripts/{call_id}"
    ], capture_output=True, text=True)
    data = json.loads(result.stdout)

    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache_file, "w") as f:
        json.dump(data, f, indent=2)

    return data

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
        "speakers": list(speakers),
        "full_text": "\n".join(transcript),
        "line_count": len(transcript),
    }

def grade_call_auto(call_id, rep_name, branch, duration_min):
    """
    Grade a single call via Anthropic API. Returns a grade dict or None if transcript unavailable.
    """
    import anthropic

    anthropic_key = get_anthropic_key()
    client = anthropic.Anthropic(api_key=anthropic_key)

    with open(RUBRIC_PATH) as f:
        rubric = f.read()

    raw = fetch_transcript(call_id)
    formatted = format_transcript(raw)

    if formatted["line_count"] < 5:
        return {
            "call_id": call_id,
            "rep_name": rep_name,
            "branch": branch,
            "duration_min": duration_min,
            "call_type": "skip",
            "skip_reason": "Transcript unavailable or too short",
            "total_score": None,
            "sections": {},
            "top_strength": None,
            "coaching_note": None,
        }

    prompt = f"""Grade this Einstein Moving Company sales call against the rubric below.

Rep: {rep_name}
Branch: {branch}
Duration: {duration_min} min
Call ID: {call_id}

--- RUBRIC ---
{rubric}

--- TRANSCRIPT ---
{formatted["full_text"]}

--- INSTRUCTIONS ---
First, classify the call:
- "full_sales_call" — standard inbound sales call with pricing discussion
- "walkthrough_scheduler" — intake call routing to a virtual walkthrough (>=1800 sqft moves)
- "skip" — not gradeable (complaint, voicemail, availability-only, vendor call, incomplete inquiry)

If "skip": return call_type="skip", skip_reason explaining why, all scores null.
If "walkthrough_scheduler": grade only Set The Agenda, Probe for Info, and Politeness. Mark other sections N/A.
If "full_sales_call": grade all sections.

For each rubric item: 1 = earned, 0 = missed, "na" = not applicable (auto point).
Section score = sum of earned + na points.

Return ONLY valid JSON in this exact structure:
{{
  "call_type": "full_sales_call" | "walkthrough_scheduler" | "skip",
  "skip_reason": null or string,
  "sections": {{
    "set_the_agenda":        {{"score": int, "max": 7,  "items_missed": [list of missed bullet text]}},
    "probe_for_info":        {{"score": int, "max": 9,  "items_missed": []}},
    "pricing_differentiators": {{"score": int, "max": 20, "items_missed": []}},
    "clock":                 {{"score": int, "max": 4,  "items_missed": []}},
    "estimate":              {{"score": int, "max": 13, "items_missed": []}},
    "save_your_ass":         {{"score": int, "max": 10, "items_missed": []}},
    "quote_booking":         {{"score": int, "max": 11, "items_missed": []}},
    "politeness":            {{"score": int, "max": 3,  "items_missed": []}},
    "bonus":                 {{"score": int, "max": 8,  "items_missed": []}}
  }},
  "total_score": int or null,
  "total_max": 85,
  "mastery": true | false | null,
  "save_your_ass_hit": true | false | null,
  "meet_your_mover_hit": true | false | null,
  "on_time_guarantee_hit": true | false | null,
  "email_handoff_hit": true | false | null,
  "agenda_opener_hit": true | false | null,
  "top_strength": "one sentence — the best thing the rep did on this call",
  "coaching_note": "one sentence — the single most important thing to improve"
}}"""

    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_response = message.content[0].text.strip()

    if raw_response.startswith("```"):
        raw_response = raw_response.split("```")[1]
        if raw_response.startswith("json"):
            raw_response = raw_response[4:]
    raw_response = raw_response.strip()

    grade = json.loads(raw_response)
    grade["call_id"]     = call_id
    grade["rep_name"]    = rep_name
    grade["branch"]      = branch
    grade["duration_min"] = duration_min

    return grade
