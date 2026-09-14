# CET Agenda-Opener Mini-Rubric (new script piece, live 2026-08-19)

**Scope:** CET reps only. Narrow check on ONE new script addition — not the full 85-pt scorecard.
**Source script (Part 1 — Bonding & Rapport):**

> "Let's talk about your move — what are your biggest concerns, and what are the most important things you want answers to on this call today?"

Followed by: actively listen, then a feeling-probe follow-up ("So your concern is X, tell me more about that / did this happen before / what happened to make you feel that way?"), aiming for a 70/30 talk ratio (customer doing most of the talking) before moving into the standard move-probing section (address, home size, stairs, etc.).

## What to grade per call

1. **Agenda opener asked** — did the rep ask a recognizable version of the "what are your biggest concerns / what do you want answered today" question? (paraphrase counts, doesn't need to be verbatim)
2. **Asked before probing** — did it happen *before* the rep moved into logistics/probing questions (address, sq ft, stairs, etc.), not after or skipped entirely?
3. **Emotion follow-up** — after the customer names a concern, did the rep ask a follow-up to get at the feeling/story behind it ("tell me more," "what happened," "did this happen before"), rather than immediately pivoting to pricing or probing?
4. **Talk ratio in that exchange** — customer should be doing ~70% of the talking during the agenda-opener exchange (from the opener question through the emotion follow-up, before probing starts). This is computed programmatically from transcript timestamps (see `pull_agenda_opener_candidates.py`), not judged by feel — treat the computed number as ground truth, don't override it.

## Output per call

```json
{
  "call_id": "...",
  "rep": "...",
  "agenda_opener_asked": true/false,
  "asked_before_probing": true/false,
  "emotion_followup": true/false,
  "pass": true/false,           // true only if all three above are true
  "talk_ratio_customer_pct": 0-100,   // from the pull script, pre-computed
  "talk_ratio_meets_70": true/false,
  "evidence_quote": "the actual line(s) from the transcript",
  "coaching_note": "one sentence, specific"
}
```

`pass` is about whether the script piece was executed at all (steps 1-3). `talk_ratio_meets_70` is tracked as a separate signal — a rep can ask the right question and still dominate the follow-up, or vice versa. Don't collapse the two into one score; report both.

## Per-call score (added 2026-08-21, Amanda's request)

100-point score per applicable call, weighted:
- **30 pts** — agenda_opener_asked (did they ask it at all, anywhere in the call)
- **30 pts** — asked_before_probing (did it land in the right spot in the call)
- **40 pts** — emotion_followup (the heaviest weight — this is the actual coaching target; asking the line without doing anything with the answer is the dominant failure mode seen in week 1)

Judgment call, naming it explicitly: emotion_followup carries the most points because "asked the line" without a real follow-up is worse than it looks — it trains reps to treat this as a box to check rather than a rapport move, which is the opposite of the intent. Timing (before vs. after probing) and simply asking at all split the remaining 60 evenly since both are prerequisite behaviors, not the differentiator.

`not_applicable` calls (not a real move-consultation — e.g. a job-applicant call) are excluded from scoring entirely, not given automatic credit. That's a deliberate deviation from the main 85-pt rubric's N/A convention, where N/A items *do* get automatic credit — that convention exists for individual checklist bullets inside an applicable sales call (e.g. packing pricing when no packing was discussed). It doesn't fit here because the whole call is a different category of thing, not a call where one bullet doesn't apply.

## Not in scope

Don't grade anything else on the call (pricing, probing depth, close, etc.) — this rubric exists to check adoption of one new script piece, not to duplicate the weekly 85-pt scorecard.
