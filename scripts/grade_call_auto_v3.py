#!/usr/bin/env python3
"""
grade_call_auto_v3.py — Automated grading via Anthropic API against rubric_v3.md
(Section Map, graded directly against the seven-section call script). Grades one
call and returns structured JSON with the final 100-pt score computed in Python
(not trusted to the model), so the scoring math stays centralized and auditable.

Supersedes grade_call_auto_v2.py (Jeff Johnson / Northwood Call Map) as of the
2026-09-24 script rewrite. v2 stays in the repo unchanged for reproducibility of
prior weeks' scores — see config/rubric_v3.md "Baseline handling."

Used by grade_week_range.py. Not intended for direct use.
"""

import os, json, subprocess
from pathlib import Path

RUBRIC_PATH    = Path(__file__).parent.parent / "config" / "rubric_v3.md"
TRANSCRIPT_DIR = Path(__file__).parent.parent / "output" / "transcripts"

SYSTEM_PROMPT = """You are an expert sales call evaluator for Einstein Moving Company.
You grade sales calls against the Einstein 15-Minute Quote Call section rubric (v3) and
return structured JSON. Be fair but rigorous. Base every judgment strictly on what is said
in the transcript — do not assume something was covered if it is absent. Report facts (was
X said, where did it land), not point totals — point totals are computed separately."""

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

# --- Section 1 — OPEN (10 pts) ---
QUID_PRO_QUO_PTS       = {"full": 5, "partial": 2, "none": 0}
DISCOVERY_BASICS_PTS   = {"all_four": 3, "some": 1, "few": 0}
WALKTHROUGH_BRANCH_PTS = {"correct_or_na": 2, "missed": 0}

# --- Section 2 — THEIR CONCERNS (30 pts) ---
THEIR_AGENDA_PTS   = {"asked_before_probing": 8, "asked_after_probing": 3, "not_asked": 0}
TWO_LAYERS_PTS     = {"full": 15, "shallow": 8, "none": 0}
ACTIVE_LISTEN_PTS  = {"full": 7, "partial": 3, "none": 0}

# --- Section 3 — PROBING FOR DETAILS (20 pts) ---
LOGISTICS_PTS = {"full": 12, "partial": 6, "minimal": 0}
# packing_offered / box_count_asked are plain booleans -> 4 pts each

# --- Section 4 — THE ESTIMATE (10 pts) ---
ESTIMATE_ANCHOR_PTS = {"full": 4, "partial": 2, "none": 0}
PRICING_FRAMING_PTS = {"full": 3, "partial": 1, "none": 0}
# feels_fair_then_silence: full=3, talked_over=1, not_asked=0
FEELS_FAIR_PTS = {"full": 3, "talked_over": 1, "not_asked": 0}

# --- Section 5 — TWO PROMISES (10 pts) ---
ON_TIME_PTS = {"full": 4, "partial": 2, "none": 0}
DAMAGE_PTS  = {"full": 4, "partial": 2, "none": 0}
# closes_the_loop: boolean -> 2 pts

# --- Section 6 — CONCERNS AGAIN (10 pts) ---
FINAL_CONCERNS_PTS = {"full": 5, "throwaway": 2, "not_asked": 0}
FOLLOWUP_PTS        = {"full": 3, "none": 0}
# catch_all_asked: boolean -> 2 pts

# --- Section 7 — ASK FOR THE BUSINESS (10 pts) ---
EXPLICIT_ASK_PTS = {"full": 5, "with_out": 2, "never": 0}
# rate_lock_mentioned: boolean -> 2 pts
BOOKING_CONFIRMED_PTS = {"full": 3, "partial": 1, "none": 0}

_NA_STRINGS = {"n/a", "na", "not applicable", "none applicable", "not_applicable", ""}

def _lookup(pts_map, key, field_name, na_fallback_key=None):
    """Look up an enum score, tolerating an out-of-schema 'n/a'-shaped value instead of
    crashing (mirrors the same fix applied to grade_call_auto_v2.py on 2026-09-21, after
    the model returned out-of-schema 'n/a' values on ~1/3 of a QA sample against a schema
    with no n/a option). Returns (points, used_fallback: bool).

    na_fallback_key: which tier to award if the model returns an n/a-shaped value for a
    field that DOES have an explicit N/A/full-credit carve-out in rubric_v3.md (Two Layers
    Deep, Active Listening Reflection, Follow-up on remaining concern). Fields with no
    N/A carve-out in the rubric get the zero-credit tier instead — an out-of-schema value
    there is a real grading gap, not a legitimate N/A.
    """
    if key in pts_map:
        return pts_map[key], False
    normalized = str(key).strip().lower()
    if normalized not in _NA_STRINGS:
        raise KeyError(f"Unrecognized value {key!r} for {field_name} (not in {list(pts_map)} and not an n/a-shaped string)")
    if na_fallback_key is not None:
        return pts_map[na_fallback_key], True
    zero_key = next(k for k, v in pts_map.items() if v == 0)
    return pts_map[zero_key], True

def compute_scores(g):
    """g = the raw judgment JSON from the model. Returns the final scored dict."""
    s1 = g["section1"]
    s2 = g["section2"]
    s3 = g["section3"]
    s4 = g["section4"]
    s5 = g["section5"]
    s6 = g["section6"]
    s7 = g["section7"]

    na_fallbacks_used = []

    # --- Section 1 (10 pts) ---
    quid_pro_quo, fb = _lookup(QUID_PRO_QUO_PTS, s1["quid_pro_quo"], "quid_pro_quo")
    if fb: na_fallbacks_used.append("quid_pro_quo")
    discovery_basics, fb = _lookup(DISCOVERY_BASICS_PTS, s1["discovery_basics"], "discovery_basics")
    if fb: na_fallbacks_used.append("discovery_basics")
    walkthrough_branch, fb = _lookup(WALKTHROUGH_BRANCH_PTS, s1["walkthrough_branch"], "walkthrough_branch",
                                      na_fallback_key="correct_or_na")
    if fb: na_fallbacks_used.append("walkthrough_branch")
    section1_total = quid_pro_quo + discovery_basics + walkthrough_branch

    # --- Section 2 (30 pts) ---
    their_agenda, fb = _lookup(THEIR_AGENDA_PTS, s2["their_agenda"], "their_agenda")
    if fb: na_fallbacks_used.append("their_agenda")
    two_layers, fb = _lookup(TWO_LAYERS_PTS, s2["two_layers_deep"], "two_layers_deep", na_fallback_key="full")
    if fb: na_fallbacks_used.append("two_layers_deep")
    active_listen, fb = _lookup(ACTIVE_LISTEN_PTS, s2["active_listening_reflection"], "active_listening_reflection",
                                 na_fallback_key="full")
    if fb: na_fallbacks_used.append("active_listening_reflection")
    section2_total = their_agenda + two_layers + active_listen

    # --- Section 3 (20 pts) ---
    logistics, fb = _lookup(LOGISTICS_PTS, s3["logistics_details_gathered"], "logistics_details_gathered")
    if fb: na_fallbacks_used.append("logistics_details_gathered")
    packing_offered = 4 if s3.get("packing_services_offered") else 0
    box_count_asked = 4 if s3.get("box_count_asked") else 0
    section3_total = logistics + packing_offered + box_count_asked

    # --- Sections 4-7: walkthrough_scheduler calls get all four as N/A/full credit ---
    # Per config/rubric_v3.md "Walkthrough-scheduler calls": a clean, by-design handoff to a
    # virtual walkthrough (decided in Section 1) means Sections 4-7 were never supposed to
    # happen on this call. Enforced here in Python, not left to the grading judgment to
    # self-report, matching the same guardrail added to v2 on 2026-09-21.
    if g.get("call_type") == "walkthrough_scheduler":
        section4_total, section5_total, section6_total, section7_total = 10, 10, 10, 10
    else:
        # --- Section 4 (10 pts) ---
        estimate_anchor, fb = _lookup(ESTIMATE_ANCHOR_PTS, s4["estimate_anchor"], "estimate_anchor")
        if fb: na_fallbacks_used.append("estimate_anchor")
        pricing_framing, fb = _lookup(PRICING_FRAMING_PTS, s4["pricing_framing"], "pricing_framing")
        if fb: na_fallbacks_used.append("pricing_framing")
        feels_fair, fb = _lookup(FEELS_FAIR_PTS, s4["feels_fair_then_silence"], "feels_fair_then_silence")
        if fb: na_fallbacks_used.append("feels_fair_then_silence")
        section4_total = estimate_anchor + pricing_framing + feels_fair

        # --- Section 5 (10 pts) ---
        on_time, fb = _lookup(ON_TIME_PTS, s5["on_time_guarantee_delivered"], "on_time_guarantee_delivered")
        if fb: na_fallbacks_used.append("on_time_guarantee_delivered")
        damage, fb = _lookup(DAMAGE_PTS, s5["damage_coverage_delivered"], "damage_coverage_delivered")
        if fb: na_fallbacks_used.append("damage_coverage_delivered")
        closes_loop = 2 if s5.get("closes_the_loop") else 0
        section5_total = on_time + damage + closes_loop

        # --- Section 6 (10 pts) ---
        final_concerns, fb = _lookup(FINAL_CONCERNS_PTS, s6["final_concerns_check"], "final_concerns_check")
        if fb: na_fallbacks_used.append("final_concerns_check")
        followup, fb = _lookup(FOLLOWUP_PTS, s6["followup_on_remaining_concern"], "followup_on_remaining_concern",
                                na_fallback_key="full")
        if fb: na_fallbacks_used.append("followup_on_remaining_concern")
        catch_all = 2 if s6.get("catch_all_asked") else 0
        section6_total = final_concerns + followup + catch_all

        # --- Section 7 (10 pts) ---
        explicit_ask, fb = _lookup(EXPLICIT_ASK_PTS, s7["explicit_ask"], "explicit_ask")
        if fb: na_fallbacks_used.append("explicit_ask")
        rate_lock = 2 if s7.get("rate_lock_mentioned") else 0
        booking_confirmed, fb = _lookup(BOOKING_CONFIRMED_PTS, s7["booking_confirmed"], "booking_confirmed")
        if fb: na_fallbacks_used.append("booking_confirmed")
        section7_total = explicit_ask + rate_lock + booking_confirmed

    total = round(section1_total + section2_total + section3_total + section4_total +
                  section5_total + section6_total + section7_total, 1)

    return {
        "rubric_version": "v3-section-map",
        "section1_open": section1_total,
        "section2_their_concerns": section2_total,
        "section3_probing_for_details": section3_total,
        "section4_the_estimate": section4_total,
        "section5_two_promises": section5_total,
        "section6_concerns_again": section6_total,
        "section7_ask_for_the_business": section7_total,
        "total_score": total,
        "pass": total >= 80,
        "na_fallbacks_used": na_fallbacks_used,
    }

def grade_call_auto_v3(call_id, rep_name, branch, duration_min, datetime_ct=None, external_number=None):
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

    prompt = f"""Grade this Einstein Moving Company sales call against the section rubric below.

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
- "walkthrough_scheduler" — intake call routing to a virtual walkthrough (>=1800 sqft moves), per Section 1's walkthrough branch
- "skip" — not gradeable (complaint, voicemail, availability-only, vendor call, incomplete inquiry)

If "skip": return call_type="skip", skip_reason explaining why, everything else null.

Report FACTS, not point totals — the point math is computed separately from your judgments.

Return ONLY valid JSON in this exact structure:
{{
  "call_type": "full_sales_call" | "walkthrough_scheduler" | "skip",
  "skip_reason": null or string,
  "section1": {{
    "quid_pro_quo": "full" | "partial" | "none",
    "discovery_basics": "all_four" | "some" | "few",
    "walkthrough_branch": "correct_or_na" | "missed"
  }},
  "section2": {{
    "their_agenda": "asked_before_probing" | "asked_after_probing" | "not_asked",
    "two_layers_deep": "full" | "shallow" | "none" | "n/a",
    "active_listening_reflection": "full" | "partial" | "none" | "n/a"
  }},
  "section3": {{
    "logistics_details_gathered": "full" | "partial" | "minimal",
    "packing_services_offered": true/false,
    "box_count_asked": true/false
  }},
  "section4": {{
    "estimate_anchor": "full" | "partial" | "none",
    "pricing_framing": "full" | "partial" | "none",
    "feels_fair_then_silence": "full" | "talked_over" | "not_asked"
  }},
  "section5": {{
    "on_time_guarantee_delivered": "full" | "partial" | "none",
    "damage_coverage_delivered": "full" | "partial" | "none",
    "closes_the_loop": true/false
  }},
  "section6": {{
    "final_concerns_check": "full" | "throwaway" | "not_asked",
    "followup_on_remaining_concern": "full" | "none" | "n/a",
    "catch_all_asked": true/false
  }},
  "section7": {{
    "explicit_ask": "full" | "with_out" | "never",
    "rate_lock_mentioned": true/false,
    "booking_confirmed": "full" | "partial" | "none"
  }},
  "evidence_quotes": {{"their_agenda": "...", "two_layers_deep": "...", "estimate_anchor": "...", "explicit_ask": "..."}},
  "top_strength": "one sentence — the best thing the rep did on this call",
  "coaching_note": "one sentence — the single most important thing to improve"
}}

Note: sections 4-7 are only scored for "full_sales_call" calls. For a "walkthrough_scheduler" call,
still fill in section1/section2/section3 normally, but you may return empty objects {{}} for
section4/section5/section6/section7 — they will be scored as full credit automatically."""

    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=3072,
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

    if g.get("call_type") == "walkthrough_scheduler":
        for k in ("section4", "section5", "section6", "section7"):
            g.setdefault(k, {})

    scores = compute_scores(g)
    result.update(scores)
    result["evidence_quotes"] = g.get("evidence_quotes")
    result["top_strength"] = g.get("top_strength")
    result["coaching_note"] = g.get("coaching_note")

    return result
