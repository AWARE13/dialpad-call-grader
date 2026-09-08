#!/usr/bin/env python3
"""
grade_call_auto_v2.py — Automated grading via Anthropic API against rubric_v2.md
(Jeff Johnson / Northwood Call Map). Grades one call and returns structured JSON
with the final 100-pt score computed in Python (not trusted to the model), so the
scoring math stays centralized and auditable.

Used by grade_week_range.py. Not intended for direct use.
"""

import os, json, subprocess
from pathlib import Path

RUBRIC_PATH    = Path(__file__).parent.parent / "config" / "rubric_v2.md"
TRANSCRIPT_DIR = Path(__file__).parent.parent / "output" / "transcripts"

SYSTEM_PROMPT = """You are an expert sales call evaluator for Einstein Moving Company.
You grade sales calls against the Jeff Johnson / Northwood Call Map rubric and return structured JSON.
Be fair but rigorous. Base every judgment strictly on what is said in the transcript — do not assume
something was covered if it is absent. Report facts (was X said, where did it land), not point totals —
point totals are computed separately."""

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

QUID_PRO_QUO_PTS   = {"full": 5, "partial": 2, "none": 0}
THEIR_AGENDA_PTS   = {"asked_before_probing": 10, "asked_after_probing": 4, "not_asked": 0}
TWO_LAYERS_PTS     = {"full": 15, "shallow": 8, "none": 0}
ESTIMATE_ANCHOR_PTS = {"full": 10, "partial": 5, "none": 0}

def compute_scores(g):
    """g = the raw judgment JSON from the model. Returns the final scored dict."""
    s1 = g["stage1"]
    s2 = g["stage2"]
    s3 = g["stage3"]

    quid_pro_quo = QUID_PRO_QUO_PTS[s1["quid_pro_quo"]]
    their_agenda = THEIR_AGENDA_PTS[s1["their_agenda"]]
    two_layers   = TWO_LAYERS_PTS[s1["two_layers_deep"]]

    sheet1 = 5 if s1.get("sheet1_careful_with_answered_anywhere") else 0
    sheet2 = 5 if s1.get("sheet2_whos_coming_answered_anywhere") else 0

    takeaway = (7.5 if s2.get("on_time_guarantee_covered_anywhere") else 0) + \
               (7.5 if s2.get("communication_covered_anywhere") else 0)

    estimate = ESTIMATE_ANCHOR_PTS[s3["estimate_anchor"]]

    sya_lines = s3.get("save_your_ass_lines_hit", {})
    save_your_ass = sum(3 for v in sya_lines.values() if v)

    close = (2.5 if s3.get("close_rate_lock_mentioned") else 0) + \
            (2.5 if s3.get("close_explicit_ask") else 0)

    rapport = max(0, min(5, int(g.get("rapport_warmth_1to5") or 0))) * 2

    violations = int(g.get("process_discipline_violations") or 0)
    process_discipline = max(0, 5 - violations)

    total = round(quid_pro_quo + their_agenda + two_layers + sheet1 + sheet2 +
                  takeaway + estimate + save_your_ass + close + rapport + process_discipline, 1)

    return {
        "rubric_version": "v2-jeff-call-map",
        "stage1_quid_pro_quo": quid_pro_quo,
        "stage1_their_agenda": their_agenda,
        "stage1_two_layers_deep": two_layers,
        "stage1_careful_with_sheet1": sheet1,
        "stage1_whos_coming_sheet2": sheet2,
        "stage2_takeaway_sheets3_4": takeaway,
        "stage3_estimate": estimate,
        "stage3_save_your_ass_sheet5": save_your_ass,
        "stage3_close": close,
        "rapport_warmth": rapport,
        "process_discipline": process_discipline,
        "total_score": total,
        "pass": total >= 80,
    }

def grade_call_auto_v2(call_id, rep_name, branch, duration_min, datetime_ct=None, external_number=None):
    import anthropic

    anthropic_key = get_anthropic_key()
    client = anthropic.Anthropic(api_key=anthropic_key)

    with open(RUBRIC_PATH) as f:
        rubric = f.read()

    raw = fetch_transcript(call_id)
    formatted = format_transcript(raw)

    if formatted["line_count"] < 5:
        return {
            "call_id": call_id, "rep_name": rep_name, "branch": branch,
            "duration_min": duration_min, "datetime_ct": datetime_ct,
            "external_number": external_number,
            "call_type": "skip", "skip_reason": "Transcript unavailable or too short",
            "total_score": None, "pass": None,
        }

    prompt = f"""Grade this Einstein Moving Company sales call against the Jeff Johnson / Northwood Call Map rubric below.

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

If "skip": return call_type="skip", skip_reason explaining why, everything else null.

Report FACTS, not point totals — the point math is computed separately from your judgments.

Return ONLY valid JSON in this exact structure:
{{
  "call_type": "full_sales_call" | "walkthrough_scheduler" | "skip",
  "skip_reason": null or string,
  "stage1": {{
    "quid_pro_quo": "full" | "partial" | "none",
    "their_agenda": "asked_before_probing" | "asked_after_probing" | "not_asked",
    "two_layers_deep": "full" | "shallow" | "none",
    "sheet1_careful_with_answered_anywhere": true/false,
    "sheet2_whos_coming_answered_anywhere": true/false
  }},
  "stage2": {{
    "on_time_guarantee_covered_anywhere": true/false,
    "communication_covered_anywhere": true/false,
    "repeated_a_stage1_item_in_stage2": true/false
  }},
  "stage3": {{
    "estimate_anchor": "full" | "partial" | "none",
    "save_your_ass_lines_hit": {{
      "commit_to_rate": true/false,
      "estimate_is_a_window": true/false,
      "beats_it_pay_less": true/false,
      "self_prep_tip": true/false,
      "does_that_feel_fair_then_silence": true/false
    }},
    "close_rate_lock_mentioned": true/false,
    "close_explicit_ask": true/false
  }},
  "rapport_warmth_1to5": int,
  "rapport_notes": "one sentence",
  "process_discipline_violations": int,
  "process_discipline_notes": "one sentence or empty string",
  "evidence_quotes": {{"agenda": "...", "two_layers_deep": "...", "save_your_ass": "..."}},
  "top_strength": "one sentence — the best thing the rep did on this call",
  "coaching_note": "one sentence — the single most important thing to improve"
}}"""

    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1536,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_response = message.content[0].text.strip()
    if raw_response.startswith("```"):
        raw_response = raw_response.split("```")[1]
        if raw_response.startswith("json"):
            raw_response = raw_response[4:]
    raw_response = raw_response.strip()

    g = json.loads(raw_response)

    result = {
        "call_id": call_id, "rep_name": rep_name, "branch": branch,
        "duration_min": duration_min, "datetime_ct": datetime_ct,
        "external_number": external_number,
        "call_type": g.get("call_type"), "skip_reason": g.get("skip_reason"),
    }

    if g.get("call_type") == "skip":
        result["total_score"] = None
        result["pass"] = None
        return result

    scores = compute_scores(g)
    result.update(scores)
    result["rapport_notes"] = g.get("rapport_notes")
    result["process_discipline_notes"] = g.get("process_discipline_notes")
    result["evidence_quotes"] = g.get("evidence_quotes")
    result["top_strength"] = g.get("top_strength")
    result["coaching_note"] = g.get("coaching_note")

    return result
