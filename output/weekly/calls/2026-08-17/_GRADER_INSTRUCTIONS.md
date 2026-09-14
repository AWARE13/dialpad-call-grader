# Grader instructions — Einstein weekly sales call grading (run 2026-08-17)

You are grading real Einstein Moving Company sales calls against the company scorecard.

## Inputs
- Rubric: `/Users/amandaware/Documents/GitHub/dialpad-call-grader/config/rubric.md` — READ THIS FIRST, in full.
- Call files: `/Users/amandaware/Documents/GitHub/dialpad-call-grader/output/weekly/calls/2026-08-17/<FILENAME>.json`
  Each contains: rep_name, rep_id, call_id, branch, duration_min, datetime_ct, speakers, transcript, line_count.

## Task
For each call file assigned to you:

1. Read the call JSON. Read the full transcript.
2. Classify the call:
   - `full_sales_call` — a real moving-quote/sales conversation (intake + pricing/estimate discussion, or a booking conversation).
   - `walkthrough_scheduler` — intake call for a large home (typically >=1800 sqft) that routes to a virtual walkthrough; pricing/clock/estimate/Save Your Ass sections do not apply.
   - `skip` — not a gradeable sales call (voicemail, wrong number, internal/rep-to-rep call, pure customer-service or claims call, existing-move logistics with no sales content, transcript too garbled/short to grade, customer hung up immediately).
3. If `skip`: set `skip_reason` and leave scores null. Do not invent a score.
4. Otherwise grade ALL 9 rubric sections. Scoring rule: start from full points, deduct for each bullet the rep failed to cover. **If a bullet genuinely does not apply to this call, the point is automatically granted (N/A = automatic point).** Be honest and evidence-based — only credit something you can actually point to in the transcript. Do not inflate.
5. Also do the Phone Presence Assessment (1-5, transcript-language based, separate from the 85).

## Differentiator flags (must be strictly evidence-based)
- `save_your_ass_hit` — true only if the rep gave the prep speech (prep before move day shortens the move / lowers the bill, consolidation tips, carload tip). Partial gestures do not count.
- `meet_your_mover_hit` — true only if the rep explicitly described the pre-move email with the mover's photo/info.
- `on_time_guarantee_hit` — true only if the rep explicitly said Einstein discounts if it misses the arrival window.
- `email_handoff_hit` — true if the rep explained they'll send a confirmation email.
- `agenda_opener_hit` — true only if the rep gave an actual agenda statement (what the call will cover + rough time) AND asked for confirmation ("sound good?" or equivalent).

## Output — write ONE file per call
Write to: `/Users/amandaware/Documents/GitHub/dialpad-call-grader/output/weekly/grades/2026-08-17/<SAME_FILENAME>.json`

Exact schema (match key names and types exactly):

```json
{
  "call_id": "string",
  "rep_name": "string",
  "branch": "string",
  "duration_min": 0.0,
  "call_type": "full_sales_call | walkthrough_scheduler | skip",
  "skip_reason": null,
  "total_score": 0,
  "mastery": false,
  "save_your_ass_hit": false,
  "meet_your_mover_hit": false,
  "on_time_guarantee_hit": false,
  "email_handoff_hit": false,
  "agenda_opener_hit": false,
  "section_scores": {
    "1_set_agenda": "0/7",
    "2_probe": "0/9",
    "3_pricing": "0/20",
    "4_clock": "0/4",
    "5_estimate": "0/13",
    "6_save_your_ass": "0/10",
    "7_quote_booking": "0/11",
    "8_politeness": "0/3",
    "9_bonus": "0/8"
  },
  "items_missed": ["specific, concrete misses — quote or paraphrase what was skipped"],
  "top_strength": "1-2 sentences, specific to THIS call",
  "coaching_note": "1-3 sentences — the single most useful thing this rep should change next call",
  "phone_presence_score": 3,
  "phone_presence_label": "Outstanding|Engaging|Adequate|Flat|Disengaging",
  "phone_presence_notes": "one sentence",
  "audio_review_flag": false,
  "audio_review_reason": null
}
```

Rules:
- `total_score` must equal the sum of the 9 section numerators. Verify the arithmetic before writing.
- `mastery` = total_score >= 77.
- For `skip`: total_score = null, mastery = false, all *_hit = false, section_scores = null.
- For `walkthrough_scheduler`: score sections 1, 2, 7, 8, 9 normally; set sections 3, 4, 5, 6 to full N/A credit ONLY if the transcript confirms the call legitimately routed to a walkthrough before pricing. Note this in coaching_note.
- Write valid JSON only — no markdown fences inside the file.

## Your reply
Return ONE line per call, nothing else: `FILENAME | rep | call_type | total_score/85 | presence N/5`
