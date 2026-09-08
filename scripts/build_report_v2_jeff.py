#!/usr/bin/env python3
"""
build_report_v2_jeff.py — Builds the viewable HTML report for a rubric_v2 (Jeff Call Map)
grading run: per-rep leaderboard, per-call cards with score breakdown, recording link,
and an expandable transcript. Matches the Einstein-branded style of report_2026-06-11.html.

Usage:
    python3 scripts/build_report_v2_jeff.py 2026-08-30 2026-09-05
"""
import json, sys, html, os
from pathlib import Path
from collections import defaultdict

WEEK_START = sys.argv[1] if len(sys.argv) > 1 else "2026-08-30"
WEEK_END   = sys.argv[2] if len(sys.argv) > 2 else "2026-09-05"

BASE = Path(__file__).parent.parent
GRADES_DIR = BASE / "output" / "weekly" / "grades" / f"v2_cet_week_{WEEK_START}_{WEEK_END}"
TRANSCRIPT_DIR = BASE / "output" / "transcripts"
OUT_PATH = BASE / "output" / "weekly" / f"v2_cet_week_{WEEK_START}_{WEEK_END}_report.html"

GREEN, BLUE, ORANGE, RED = "#639922", "#185fa5", "#E8630A", "#a32d2d"
NAVY = "#1a2744"

# Training-group rosters (Jeff/Northwood CET split — Tue group / Wed group).
# Names below match the grading data's rep_name (roster "name"), not always the Dialpad
# display name Amanda gave (e.g. "Chauny Shivers" -> "Chauntelle Shivers" here).
# Not assigned to either group: Therese Ablang, Nhel Banayad (not mentioned in either
# list) and Jevic Lazanas (Wednesday list, but has no matching Dialpad account at all --
# a known unresolved gap, so no grading data exists for him either way).
GROUP_ASSIGNMENTS = {
    "Amy Arbasa": "tuesday",
    "Chauntelle Shivers": "tuesday",
    "Jeline 2Lavarias": "tuesday",
    "Jules Nicolas": "tuesday",
    "Zhang Pammit": "tuesday",
    "Arden 2Asilo": "wednesday",
    "Brianne Newbro": "wednesday",
    "Joanna Ballon": "wednesday",
    "Danah 2Celestial": "wednesday",
    "Nicole Tolete": "wednesday",
}

COMPONENTS = [
    ("stage1_quid_pro_quo", "Quid pro quo", 5),
    ("stage1_their_agenda", "Their agenda", 10),
    ("stage1_two_layers_deep", "Two layers deep", 15),
    ("stage1_careful_with_sheet1", "Careful with (Sheet 1)", 5),
    ("stage1_whos_coming_sheet2", "Who's coming (Sheet 2)", 5),
    ("stage2_takeaway_sheets3_4", "Takeaway (Sheets 3-4)", 15),
    ("stage3_estimate", "Estimate anchor", 10),
    ("stage3_save_your_ass_sheet5", "Save Your Ass (Sheet 5)", 15),
    ("stage3_close", "Close", 5),
    ("rapport_warmth", "Rapport/warmth", 10),
    ("process_discipline", "Process discipline", 5),
]

def esc(x):
    return html.escape(str(x)) if x is not None else ""

def score_color(s):
    if s is None: return "#888"
    if s >= 80: return GREEN
    if s >= 60: return BLUE
    if s >= 40: return ORANGE
    return RED

def comp_color(v, mx):
    pct = (v or 0) / mx if mx else 0
    if pct >= 0.9: return GREEN
    if pct >= 0.5: return BLUE
    if pct >= 0.2: return ORANGE
    return RED

def anchor(name):
    return name.replace(" ", "_").replace("'", "")

def load_transcript_text(call_id):
    p = TRANSCRIPT_DIR / f"{call_id}.json"
    if not p.exists():
        return None
    try:
        data = json.load(open(p))
    except Exception:
        return None
    lines = data.get("lines", [])
    out = []
    for l in lines:
        if l.get("type") == "transcript":
            out.append(f'{l.get("name","?")}: {l.get("content","")}')
    return "\n".join(out) if out else None

files = sorted(GRADES_DIR.glob("*.json"))
calls = [json.load(open(f)) for f in files]

graded = [c for c in calls if c.get("total_score") is not None]
skipped = [c for c in calls if c.get("total_score") is None]

n_total, n_graded, n_skipped = len(calls), len(graded), len(skipped)
avg_score = round(sum(c["total_score"] for c in graded) / n_graded, 1) if graded else 0
pass_count = sum(1 for c in graded if c["total_score"] >= 80)

by_rep = defaultdict(list)
for c in calls:
    by_rep[c["rep_name"]].append(c)

rep_rows = []
for rep, entries in by_rep.items():
    scored = [e["total_score"] for e in entries if e.get("total_score") is not None]
    avg = round(sum(scored) / len(scored), 1) if scored else None
    passes = sum(1 for s in scored if s >= 80)
    rep_rows.append({"rep": rep, "n": len(entries), "n_scored": len(scored), "avg": avg, "passes": passes})

rep_rows_ranked = sorted([r for r in rep_rows if r["avg"] is not None], key=lambda r: -r["avg"])

# component company-wide averages (for the gap chart)
comp_avgs = {}
for key, label, mx in COMPONENTS:
    vals = [c.get(key, 0) or 0 for c in graded]
    avg = sum(vals) / len(vals) if vals else 0
    comp_avgs[key] = {"label": label, "avg": round(avg, 1), "max": mx, "pct": round(100 * avg / mx) if mx else 0}

def leaderboard_rows():
    out = []
    for i, r in enumerate(rep_rows_ranked, 1):
        excl = f' <span style="color:{ORANGE};font-size:11px">({r["n"]-r["n_scored"]} excl.)</span>' if r["n_scored"] != r["n"] else ""
        group = GROUP_ASSIGNMENTS.get(r["rep"], "unassigned")
        out.append(f'''<tr data-group="{group}">
      <td style="color:#aaa">{i}</td>
      <td><a href="#{anchor(r["rep"])}" style="font-weight:700;color:{NAVY};text-decoration:none">{esc(r["rep"])}</a></td>
      <td>{r["n_scored"]}{excl}</td>
      <td><strong style="color:{score_color(r["avg"])}">{r["avg"]}</strong></td>
      <td>{r["passes"]}</td>
    </tr>''')
    return "\n".join(out)

def comp_gap_rows():
    rows = sorted(comp_avgs.items(), key=lambda x: x[1]["pct"])
    out = []
    for key, d in rows:
        out.append(f'''<div class="gap-row">
      <div class="gap-label">{esc(d["label"])}</div>
      <div class="gap-bar-track"><div class="gap-bar-fill" style="width:{d["pct"]}%;background:{comp_color(d["avg"], d["max"])}"></div></div>
      <div class="gap-pct">{d["pct"]}%</div>
    </div>''')
    return "\n".join(out)

def call_card(c, idx):
    score = c.get("total_score")
    color = score_color(score)
    call_id = c["call_id"]
    rec_url = f"https://dialpad.com/blob/adminrecording/{call_id}.mp3"
    transcript = load_transcript_text(call_id)
    transcript_html = f'<pre class="transcript">{esc(transcript)}</pre>' if transcript else '<div style="color:#999;font-size:12px">Transcript not cached.</div>'

    comps_html = ""
    for key, label, mx in COMPONENTS:
        v = c.get(key)
        cc = comp_color(v, mx) if v is not None else "#bbb"
        comps_html += f'''<div class="comp-item">
          <div class="comp-name">{esc(label)}</div>
          <div class="comp-score" style="color:{cc}">{v if v is not None else "—"}/{mx}</div>
        </div>'''

    quotes = c.get("evidence_quotes") or {}
    quotes_html = "".join(f'<div class="quote-item"><strong>{esc(k)}:</strong> "{esc(v)}"</div>' for k, v in quotes.items() if v)

    return f'''<div class="call-card">
      <div class="call-header">
        <div class="call-score" style="color:{color}">{score if score is not None else "—"}/100</div>
        <div>
          <div style="font-weight:600;font-size:13px">Call {idx} &nbsp;·&nbsp; {esc(c.get("call_type","")).replace("_"," ")}</div>
          <div class="call-meta">
            <span>⏱ {c.get("duration_min","?")} min</span>
            <span>{esc(c.get("datetime_ct",""))}</span>
            <span>{esc(c.get("branch","")).replace(" Einstein Moving Company","")}</span>
            <span>ID: {call_id}</span>
          </div>
        </div>
        <a href="{rec_url}" class="listen-btn" target="_blank">▶ Listen</a>
      </div>
      <div class="comps-grid">{comps_html}</div>
      <div class="call-notes">
        <div class="note-box">
          <div class="note-label">💪 Top strength</div>
          {esc(c.get("top_strength") or "—")}
        </div>
        <div class="note-box">
          <div class="note-label">🎯 Coaching note</div>
          {esc(c.get("coaching_note") or "—")}
        </div>
      </div>
      {f'<details style="margin-top:8px;font-size:12px;"><summary style="cursor:pointer;color:{BLUE};font-weight:600">Evidence quotes</summary><div style="margin-top:8px">{quotes_html}</div></details>' if quotes_html else ""}
      <details style="margin-top:8px;font-size:12px;">
        <summary style="cursor:pointer;color:{BLUE};font-weight:600">Transcript</summary>
        {transcript_html}
      </details>
    </div>'''

def skip_card(c):
    call_id = c["call_id"]
    rec_url = f"https://dialpad.com/blob/adminrecording/{call_id}.mp3"
    return f'''<div class="skip-card">
      <strong>Not scored</strong> — {c.get("duration_min","?")} min, {esc(c.get("datetime_ct",""))}, ID {call_id}
      &nbsp;<a href="{rec_url}" target="_blank" style="color:{BLUE}">▶ Listen</a><br>
      {esc(c.get("skip_reason") or "—")}
    </div>'''

def rep_section(rep, entries):
    scored = [e["total_score"] for e in entries if e.get("total_score") is not None]
    avg = round(sum(scored) / len(scored), 1) if scored else None
    cards = []
    idx = 1
    for e in sorted(entries, key=lambda x: x.get("datetime_ct") or ""):
        if e.get("total_score") is not None:
            cards.append(call_card(e, idx))
            idx += 1
        else:
            cards.append(skip_card(e))
    avg_html = f'<div class="rep-avg">{avg}/100</div><div style="font-size:11px;color:rgba(255,255,255,0.6)">avg score</div>' if avg is not None else '<div class="rep-avg" style="font-size:13px">not scored</div>'
    group = GROUP_ASSIGNMENTS.get(rep, "unassigned")
    return f'''<div class="rep-section" id="{anchor(rep)}" data-group="{group}">
  <div class="rep-header">
    <div>
      <h3>{esc(rep)}</h3>
      <span style="font-size:12px;color:rgba(255,255,255,0.6)">{len(entries)} call(s)</span>
    </div>
    <div style="text-align:right">{avg_html}</div>
  </div>
  <div class="rep-calls">{"".join(cards)}</div>
</div>'''

rep_sections_html = "".join(rep_section(rep, entries) for rep, entries in sorted(by_rep.items(), key=lambda x: -next((r["avg"] for r in rep_rows if r["rep"]==x[0] and r["avg"] is not None), 0)))

tuesday_n = sum(1 for g in GROUP_ASSIGNMENTS.values() if g == "tuesday")
wednesday_n = sum(1 for g in GROUP_ASSIGNMENTS.values() if g == "wednesday")

# Slim per-call dataset embedded client-side so every part of the page (stats bar,
# gap chart, leaderboard) can recompute for the active view, not just show/hide DOM.
calls_min = []
for c in calls:
    row = {
        "rep": c["rep_name"],
        "group": GROUP_ASSIGNMENTS.get(c["rep_name"], "unassigned"),
        "score": c.get("total_score"),
    }
    for key, _, _ in COMPONENTS:
        row[key] = c.get(key)
    calls_min.append(row)
calls_json = json.dumps(calls_min)
components_json = json.dumps([[k, l, m] for k, l, m in COMPONENTS])

def empty_notice(view_key, view_label):
    return (f'<div class="view-empty" data-view-only="{view_key}">'
            f'{view_label} training group roster has not been set yet — check back once it is assigned.</div>')

tuesday_empty_html = empty_notice("tuesday", "Tuesday") if tuesday_n == 0 else ""
wednesday_empty_html = empty_notice("wednesday", "Wednesday") if wednesday_n == 0 else ""

html_out = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="robots" content="noindex, nofollow, noarchive">
<title>CET Call Grading — {WEEK_START} to {WEEK_END}</title>
<style>
  body {{ font-family: -apple-system, Roboto, Arial, sans-serif; background:#f4f2ee; color:#222; margin:0; }}
  .header {{ background:{NAVY}; color:#fff; padding:32px 40px; }}
  .header h1 {{ margin:0 0 4px; font-size:24px; }}
  .header .sub {{ color:rgba(255,255,255,0.7); font-size:13px; }}
  .stats-bar {{ display:flex; gap:24px; padding:20px 40px; background:#fff; border-bottom:1px solid #e5e0d8; flex-wrap:wrap; }}
  .stat {{ min-width:120px; }}
  .stat .num {{ font-size:28px; font-weight:700; }}
  .stat .lbl {{ font-size:12px; color:#888; }}
  .section {{ max-width:1000px; margin:24px auto; padding:0 20px; }}
  table {{ width:100%; border-collapse:collapse; background:#fff; border-radius:8px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,0.08); }}
  th {{ text-align:left; padding:10px 14px; background:#eee7db; font-size:12px; color:#666; }}
  td {{ padding:10px 14px; border-top:1px solid #eee; font-size:14px; }}
  .gap-row {{ display:flex; align-items:center; gap:12px; padding:6px 0; }}
  .gap-label {{ width:220px; font-size:13px; color:#444; }}
  .gap-bar-track {{ flex:1; background:#eee; height:14px; border-radius:7px; overflow:hidden; }}
  .gap-bar-fill {{ height:100%; }}
  .gap-pct {{ width:40px; text-align:right; font-size:12px; color:#666; }}
  .rep-section {{ max-width:1000px; margin:24px auto; padding:0 20px; }}
  .rep-header {{ background:{NAVY}; color:#fff; padding:14px 20px; border-radius:8px 8px 0 0; display:flex; justify-content:space-between; align-items:center; }}
  .rep-header h3 {{ margin:0; font-size:16px; }}
  .rep-avg {{ font-size:22px; font-weight:700; }}
  .rep-calls {{ background:#fff; padding:16px; border-radius:0 0 8px 8px; }}
  .call-card {{ border:1px solid #eee; border-radius:8px; padding:14px; margin-bottom:12px; }}
  .call-header {{ display:flex; align-items:center; gap:14px; margin-bottom:10px; }}
  .call-score {{ font-size:22px; font-weight:700; min-width:64px; }}
  .call-meta {{ display:flex; gap:12px; font-size:11px; color:#888; }}
  .listen-btn {{ margin-left:auto; background:{ORANGE}; color:#fff; padding:6px 12px; border-radius:6px; text-decoration:none; font-size:12px; font-weight:600; }}
  .comps-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(150px,1fr)); gap:6px; margin-bottom:10px; }}
  .comp-item {{ background:#faf9f6; border-radius:6px; padding:6px 8px; }}
  .comp-name {{ font-size:10px; color:#888; }}
  .comp-score {{ font-size:14px; font-weight:700; }}
  .call-notes {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }}
  .note-box {{ background:#faf9f6; border-radius:6px; padding:8px 10px; font-size:12px; }}
  .note-label {{ font-size:11px; font-weight:700; color:{ORANGE}; margin-bottom:2px; }}
  .quote-item {{ font-size:12px; color:#555; margin-bottom:4px; }}
  .transcript {{ white-space:pre-wrap; font-size:11px; color:#444; background:#faf9f6; padding:10px; border-radius:6px; max-height:400px; overflow-y:auto; }}
  .skip-card {{ border:1px dashed #ddd; border-radius:8px; padding:10px 14px; margin-bottom:8px; font-size:12px; color:#888; }}
  .rubric-section h2 {{ margin-bottom:8px; }}
  .rubric-score-badges {{ display:flex; align-items:center; gap:16px; margin-bottom:16px; flex-wrap:wrap; }}
  .rubric-badge {{ flex:0 0 auto; text-align:center; background:#fff; border:2px solid {NAVY}; border-radius:10px; padding:8px 18px; min-width:90px; }}
  .rubric-badge-pass {{ border-color:{GREEN}; }}
  .rb-num {{ font-size:24px; font-weight:800; color:{NAVY}; line-height:1.1; }}
  .rubric-badge-pass .rb-num {{ color:{GREEN}; }}
  .rb-lbl {{ font-size:10px; color:#888; text-transform:uppercase; letter-spacing:.4px; margin-top:2px; }}
  .rubric-intro {{ font-size:12.5px; color:#555; line-height:1.55; margin:0; flex:1 1 320px; min-width:280px; }}
  .rubric-stage-bar {{ display:flex; justify-content:space-between; align-items:center; background:{NAVY}; color:#fff; padding:6px 14px; border-radius:6px; font-size:12px; font-weight:700; letter-spacing:.2px; margin:14px 0 8px; }}
  .rubric-stage-total {{ font-weight:400; color:rgba(255,255,255,0.75); }}
  .rubric-cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:8px; }}
  .rubric-card {{ display:flex; gap:10px; background:#fff; border:1px solid #eee; border-radius:8px; padding:10px 12px; }}
  .rc-pts {{ flex:0 0 auto; width:34px; height:34px; border-radius:50%; background:{ORANGE}; color:#fff; font-weight:700; font-size:13px; display:flex; align-items:center; justify-content:center; }}
  .rc-name {{ font-size:12.5px; font-weight:700; color:#222; margin-bottom:2px; }}
  .rc-sheet {{ font-weight:400; color:#999; font-size:10.5px; display:block; }}
  .rc-desc {{ font-size:11px; color:#666; line-height:1.4; }}
  .rubric-footnote {{ font-size:11.5px; color:#888; margin-top:14px; max-width:900px; }}
  .lb-header {{ display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px; margin-bottom:10px; }}
  .lb-header h2 {{ margin:0; }}
  .view-tabs {{ display:flex; gap:6px; }}
  .view-tab {{ font-family:inherit; font-size:12px; font-weight:600; color:{NAVY}; background:#fff; border:1px solid #ddd; border-radius:999px; padding:6px 14px; cursor:pointer; }}
  .view-tab.active {{ background:{NAVY}; color:#fff; border-color:{NAVY}; }}
  .view-empty {{ display:none; background:#fff8ef; border:1px dashed {ORANGE}; border-radius:8px; padding:10px 14px; font-size:12px; color:#8a5a20; margin-bottom:10px; }}
  body[data-view="tuesday"] .view-empty[data-view-only="tuesday"] {{ display:block; }}
  body[data-view="wednesday"] .view-empty[data-view-only="wednesday"] {{ display:block; }}
  body[data-view="tuesday"] tr[data-group]:not([data-group="tuesday"]) {{ display:none; }}
  body[data-view="tuesday"] .rep-section[data-group]:not([data-group="tuesday"]) {{ display:none; }}
  body[data-view="wednesday"] tr[data-group]:not([data-group="wednesday"]) {{ display:none; }}
  body[data-view="wednesday"] .rep-section[data-group]:not([data-group="wednesday"]) {{ display:none; }}
</style>
</head>
<body>
  <div class="header">
    <h1>CET Call Grading</h1>
    <div class="sub">Week of {WEEK_START} to {WEEK_END} &nbsp;·&nbsp; Fresh rubric, no baseline carried forward &nbsp;·&nbsp; Passing bar: 80/100</div>
  </div>
  <div class="stats-bar">
    <div class="stat"><div class="num" id="stat-total">{n_total}</div><div class="lbl">calls pulled</div></div>
    <div class="stat"><div class="num" id="stat-graded">{n_graded}</div><div class="lbl">graded</div></div>
    <div class="stat"><div class="num" id="stat-skipped">{n_skipped}</div><div class="lbl">skipped</div></div>
    <div class="stat"><div class="num" id="stat-avg" style="color:{score_color(avg_score)}">{avg_score}</div><div class="lbl">avg / 100</div></div>
    <div class="stat"><div class="num" id="stat-pass" style="color:{GREEN if pass_count else RED}">{pass_count}</div><div class="lbl">calls passing (80+)</div></div>
  </div>

  <div class="section rubric-section">
    <h2>How this is scored</h2>
    <div class="rubric-score-badges">
      <div class="rubric-badge"><div class="rb-num">100</div><div class="rb-lbl">points possible</div></div>
      <div class="rubric-badge rubric-badge-pass"><div class="rb-num">80+</div><div class="rb-lbl">to pass</div></div>
      <p class="rubric-intro">
        Based on Jeff Johnson's (Northwood Group) Call Map — 3 stages, 11 scored items.
        One rule covers 4 items below: the differentiators (damage coverage, Meet Your Mover, On-Time Guarantee, Communication)
        only need to land <strong>once</strong> — as a direct answer in Stage 1, or as the Stage 2 "takeaway" ask if it wasn't raised. Never both required, never penalized twice for the same gap.
      </p>
    </div>

    <div class="rubric-stage-bar"><span>Stage 1 — Discovery</span><span class="rubric-stage-total">40 pts</span></div>
    <div class="rubric-cards">
      <div class="rubric-card"><div class="rc-pts">5</div><div class="rc-body"><div class="rc-name">Quid pro quo</div><div class="rc-desc">Trades "let's get you a quote" for the customer's patience before probing. Full credit if the framing was there, partial if skipped, zero if straight into probing.</div></div></div>
      <div class="rubric-card"><div class="rc-pts">10</div><div class="rc-body"><div class="rc-name">Their agenda</div><div class="rc-desc">"Other than price, what are your biggest concerns... what do you want answered today?" Full if asked before probing, partial if late, zero if never. Biggest adoption gap company-wide.</div></div></div>
      <div class="rubric-card"><div class="rc-pts">15</div><div class="rc-body"><div class="rc-name">Two layers deep</div><div class="rc-desc">Real follow-up on a raised concern — "tell me more" — not one question and a pivot. Heaviest item in Stage 1. Full credit if the customer never raised a concern at all (nothing to follow up on).</div></div></div>
      <div class="rubric-card"><div class="rc-pts">5</div><div class="rc-body"><div class="rc-name">Careful with <span class="rc-sheet">Sheet 1 · damage coverage</span></div><div class="rc-desc">Binary — covered anywhere in the call (Stage 1 or Stage 2), or not covered at all.</div></div></div>
      <div class="rubric-card"><div class="rc-pts">5</div><div class="rc-body"><div class="rc-name">Who's coming <span class="rc-sheet">Sheet 2 · Meet Your Mover</span></div><div class="rc-desc">Same binary logic as Sheet 1.</div></div></div>
    </div>

    <div class="rubric-stage-bar"><span>Stage 2 — Ramp up, take away</span><span class="rubric-stage-total">15 pts</span></div>
    <div class="rubric-cards">
      <div class="rubric-card"><div class="rc-pts">15</div><div class="rc-body"><div class="rc-name">The takeaway <span class="rc-sheet">Sheets 3–4 · On-Time + Communication</span></div><div class="rc-desc">Splits 7.5 / 7.5 — each half scores independently on whether On-Time Guarantee and Communication (day-before call, named crew lead) are covered anywhere in the call.</div></div></div>
    </div>

    <div class="rubric-stage-bar"><span>Stage 3 — After the estimate</span><span class="rubric-stage-total">35 pts</span></div>
    <div class="rubric-cards">
      <div class="rubric-card"><div class="rc-pts">10</div><div class="rc-body"><div class="rc-name">Estimate anchor</div><div class="rc-desc">A typical range AND personalized to this move = full credit. Range only = partial. No framing = zero.</div></div></div>
      <div class="rubric-card"><div class="rc-pts">15</div><div class="rc-body"><div class="rc-name">Save Your Ass <span class="rc-sheet">Sheet 5</span></div><div class="rc-desc">5 lines, 3 pts each: rate commitment, "the estimate is a window," beats-it-pay-less, self-prep tip, "does that feel fair?" + real silence.</div></div></div>
      <div class="rubric-card"><div class="rc-pts">5</div><div class="rc-body"><div class="rc-name">Close</div><div class="rc-desc">2 items, 2.5 pts each: the rate-lock line, and an explicit ask ("would you like our help with your move?").</div></div></div>
    </div>

    <div class="rubric-stage-bar"><span>Cross-call</span><span class="rubric-stage-total">15 pts</span></div>
    <div class="rubric-cards">
      <div class="rubric-card"><div class="rc-pts">10</div><div class="rc-body"><div class="rc-name">Rapport / warmth</div><div class="rc-desc">Same 1–5 transcript-based warmth scale as the old phone-presence rubric, rescaled ×2.</div></div></div>
      <div class="rubric-card"><div class="rc-pts">5</div><div class="rc-body"><div class="rc-name">Process discipline</div><div class="rc-desc">Starts at 5, −1 per violation (a differentiator repeated, or no silence after an open question). Floors at 0.</div></div></div>
    </div>

    <p class="rubric-footnote">
      <strong>One more exception:</strong> calls cleanly routed to a virtual walkthrough before pricing (large moves) get the 3 Stage 3 items scored as full credit rather than zeroed — the call wasn't supposed to reach pricing. Only for a clean, by-design handoff, not a call that just trails off.
    </p>
  </div>

  <div class="section">
    <div class="lb-header">
      <h2>Leaderboard</h2>
      <div class="view-tabs">
        <button class="view-tab active" data-view="all" type="button">All CET</button>
        <button class="view-tab" data-view="tuesday" type="button">Tuesday Group</button>
        <button class="view-tab" data-view="wednesday" type="button">Wednesday Group</button>
      </div>
    </div>
    {tuesday_empty_html}
    {wednesday_empty_html}
    <table>
      <tr><th>#</th><th>Rep</th><th>Calls</th><th>Avg</th><th>Passes</th></tr>
      <tbody id="leaderboard-body">
      {leaderboard_rows()}
      </tbody>
    </table>
  </div>

  <div class="section">
    <h2>Where the score is going <span id="gap-chart-scope" style="font-weight:400;color:#888;font-size:13px">(company-wide, % of max)</span></h2>
    <div id="gap-chart">
    {comp_gap_rows()}
    </div>
  </div>

  {rep_sections_html}

  <div class="section" style="color:#999;font-size:11px;padding:12px 0 40px;">
    This page is public but marked no-index — it isn't listed anywhere or access-gated. Anyone with this exact link can view it, including the transcripts below.
  </div>

<script>
  var CALLS = {calls_json};
  var COMPONENTS = {components_json};
  var VIEW_LABELS = {{all: "company-wide", tuesday: "Tuesday group", wednesday: "Wednesday group"}};

  function scoreColor(s) {{
    if (s == null) return '#888';
    if (s >= 80) return '{GREEN}';
    if (s >= 60) return '{BLUE}';
    if (s >= 40) return '{ORANGE}';
    return '{RED}';
  }}
  function compColor(pct) {{
    if (pct >= 90) return '{GREEN}';
    if (pct >= 50) return '{BLUE}';
    if (pct >= 20) return '{ORANGE}';
    return '{RED}';
  }}
  function anchorName(name) {{
    return name.split(' ').join('_').split("'").join('');
  }}

  function renderView(view) {{
    var filtered = view === 'all' ? CALLS : CALLS.filter(function(c) {{ return c.group === view; }});
    var graded = filtered.filter(function(c) {{ return c.score != null; }});
    var skipped = filtered.filter(function(c) {{ return c.score == null; }});
    var avg = graded.length ? (graded.reduce(function(a, c) {{ return a + c.score; }}, 0) / graded.length) : 0;
    var passCount = graded.filter(function(c) {{ return c.score >= 80; }}).length;

    document.getElementById('stat-total').textContent = filtered.length;
    document.getElementById('stat-graded').textContent = graded.length;
    document.getElementById('stat-skipped').textContent = skipped.length;
    var avgEl = document.getElementById('stat-avg');
    avgEl.textContent = avg.toFixed(1);
    avgEl.style.color = scoreColor(avg);
    var passEl = document.getElementById('stat-pass');
    passEl.textContent = passCount;
    passEl.style.color = passCount > 0 ? '{GREEN}' : '{RED}';
    document.getElementById('gap-chart-scope').textContent = '(' + VIEW_LABELS[view] + ', % of max)';

    // leaderboard, re-ranked for this view
    var byRep = {{}};
    filtered.forEach(function(c) {{ (byRep[c.rep] = byRep[c.rep] || []).push(c); }});
    var rows = Object.keys(byRep).map(function(rep) {{
      var entries = byRep[rep];
      var scored = entries.filter(function(e) {{ return e.score != null; }}).map(function(e) {{ return e.score; }});
      var avgR = scored.length ? scored.reduce(function(a, b) {{ return a + b; }}, 0) / scored.length : null;
      var passes = scored.filter(function(s) {{ return s >= 80; }}).length;
      return {{rep: rep, n: entries.length, nScored: scored.length, avg: avgR, passes: passes}};
    }}).filter(function(r) {{ return r.avg != null; }}).sort(function(a, b) {{ return b.avg - a.avg; }});

    document.getElementById('leaderboard-body').innerHTML = rows.map(function(r, i) {{
      var excl = r.nScored !== r.n ? (' <span style="color:{ORANGE};font-size:11px">(' + (r.n - r.nScored) + ' excl.)</span>') : '';
      return '<tr><td style="color:#aaa">' + (i + 1) + '</td>' +
        '<td><a href="#' + anchorName(r.rep) + '" style="font-weight:700;color:{NAVY};text-decoration:none">' + r.rep + '</a></td>' +
        '<td>' + r.nScored + excl + '</td>' +
        '<td><strong style="color:' + scoreColor(r.avg) + '">' + r.avg.toFixed(1) + '</strong></td>' +
        '<td>' + r.passes + '</td></tr>';
    }}).join('');

    // gap chart, recomputed and re-sorted for this view
    var compStats = COMPONENTS.map(function(comp) {{
      var key = comp[0], label = comp[1], mx = comp[2];
      var vals = graded.map(function(c) {{ return c[key] || 0; }});
      var avgV = vals.length ? vals.reduce(function(a, b) {{ return a + b; }}, 0) / vals.length : 0;
      var pct = mx ? Math.round(100 * avgV / mx) : 0;
      return {{label: label, pct: pct}};
    }}).sort(function(a, b) {{ return a.pct - b.pct; }});

    document.getElementById('gap-chart').innerHTML = compStats.map(function(d) {{
      return '<div class="gap-row"><div class="gap-label">' + d.label + '</div>' +
        '<div class="gap-bar-track"><div class="gap-bar-fill" style="width:' + d.pct + '%;background:' + compColor(d.pct) + '"></div></div>' +
        '<div class="gap-pct">' + d.pct + '%</div></div>';
    }}).join('');
  }}

  document.querySelectorAll('.view-tab').forEach(function(btn) {{
    btn.addEventListener('click', function() {{
      document.querySelectorAll('.view-tab').forEach(function(b) {{ b.classList.remove('active'); }});
      btn.classList.add('active');
      document.body.setAttribute('data-view', btn.dataset.view);
      renderView(btn.dataset.view);
    }});
  }});
</script>
</body>
</html>'''

OUT_PATH.write_text(html_out)
print(f"Written: {OUT_PATH}  ({len(html_out)/1024:.0f} KB)")
