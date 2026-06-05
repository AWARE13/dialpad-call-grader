# Dialpad Sales Call Grader — Einstein Moving Company

AI-powered sales call auditing tool. Pulls calls from Dialpad, filters to legitimate sales calls, grades against Einstein's 85-pt Sales Call Scorecard, and produces coaching reports.

**Owner:** Amanda Ware (Director of CX)
**AI operator:** Gary (Amanda's AI Chief of Staff)
**Status:** Active — Week 1 build

---

## Quick Start

```bash
# Verify API connection
source ~/.zshrc
curl -s -H "Authorization: Bearer $DIALPAD_API_KEY" https://dialpad.com/api/v2/company

# Run a full audit (pull + filter + grade)
python3 scripts/run_audit.py

# Pull candidates only (no grading)
python3 scripts/pull_candidates.py
```

---

## What This Does

1. **Pull** — Hits all 10 Dialpad call centers, pulls last 50 calls each
2. **Filter** — Keeps inbound, >5 min, state=hangup, deduped by leg
3. **Grade** — AI reads each transcript against the 85-pt rubric in `config/rubric.md`
4. **Report** — Outputs per-call scorecards + cross-call pattern findings

---

## Project Structure

```
dialpad-call-grader/
├── CLAUDE.md                  ← You are here
├── config/
│   ├── rubric.md              ← 85-pt Sales Call Scorecard (source of truth)
│   ├── call_centers.json      ← All branch call center IDs (cached)
│   └── filter_config.json     ← Pre-filter rules
├── scripts/
│   ├── pull_candidates.py     ← Pull + filter calls from all branches
│   ├── run_audit.py           ← Full pipeline: pull → grade → report
│   └── grade_call.py          ← Grade a single call by call_id
├── output/
│   ├── grades/                ← Per-call scorecards (JSON + markdown)
│   └── transcripts/           ← Cached raw transcripts (avoid re-pulling)
└── README.md
```

---

## API Setup

- **Env var:** `DIALPAD_API_KEY` (already in `~/.zshrc`)
- **Base URL:** `https://dialpad.com/api/v2/`
- **Auth header:** `Authorization: Bearer $DIALPAD_API_KEY`
- **Key endpoints:**
  - `GET /call?target_type=callcenter&target_id={id}&limit=50` — call list
  - `GET /transcripts/{call_id}` — full transcript with AI moments

**Note:** Office lines (`target_type=office`) are pass-throughs only — all real sales calls go through call centers. Verified 6/5/2026.

---

## Rubric Summary (85 pts)

| Section | Pts | Mastery threshold |
|---------|-----|-------------------|
| Set The Agenda | 7 | |
| Probe for Info | 9 | |
| Pricing / Differentiators | 20 | |
| Clock | 4 | |
| Estimate | 13 | |
| Save Your Ass | 10 | |
| Quote / Booking | 11 | |
| Politeness | 3 | |
| Bonus | 8 | |
| **Total** | **85** | **77+ = mastery** |

N/A rule: automatic point if a bullet doesn't apply to the call.
Full rubric: `config/rubric.md`

---

## Call Centers (cached — don't re-pull)

| Branch | Call Center ID |
|--------|---------------|
| North Austin | 6059781097930752 |
| South Austin | 5415116541640704 |
| South Austin CC (alt) | 4518275526574080 |
| Leander | 5228981035089920 |
| San Antonio | 6627360982056960 |
| Houston | 5991438108213248 |
| Dallas | 4645958333906944 |
| Fort Worth | 5221847950049280 |
| McKinney | 5221559331602432 |
| Garland | 6654487771103232 |
| Tampa | 5107631565979648 |

---

## Known Patterns (updated after each audit)

| Gap | Calls audited | Hit rate |
|-----|--------------|----------|
| Save Your Ass | 5/5 | 0% — never used |
| Meet Your Mover | 5/5 | 20% (Nicole Cruz only) |
| On-Time Guarantee | 5/5 | 20% (Nicole Cruz only) |
| Email handoff "reply with corrections" | 5/5 | 0% |
| Agenda-setting opener | 5/5 | 20% |

---

## Open Decisions (need Amanda + Cameron)

1. Per-bullet rubric weights — needs 60-min working session with Nhel + Tetet
2. Walkthrough-scheduler mini-rubric scope
3. Comp tie / Goodhart risk — feed performance pay?
4. Privacy + retention policy for transcripts

---

## Monday Tracking

- **Sky Board pulse:** https://einsteinmoving.monday.com/boards/1146915251/pulses/12206626312
- **SCB handover pulse:** https://einsteinmoving.monday.com/boards/18407411332/pulses/12205284990
- Post audit findings as updates on the Sky Board pulse. Tag Cameron (Monday ID: 13851452) on anything that needs his input.

---

## Audit Log

| Date | Calls pulled | Candidates | Graded | Key finding |
|------|-------------|------------|--------|-------------|
| 2026-06-05 | ~500 (10 branches) | 64 | 2 | Save Your Ass 0/5 company-wide; Nicole Cruz hit all 3 differentiators |
