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
        out.append(f'''<tr>
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
    return f'''<div class="rep-section" id="{anchor(rep)}">
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

html_out = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="robots" content="noindex, nofollow, noarchive">
<title>CET Call Grading — {WEEK_START} to {WEEK_END} — Jeff Call Map (v2)</title>
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
</style>
</head>
<body>
  <div class="header">
    <h1>CET Call Grading — Jeff Johnson Call Map (v2)</h1>
    <div class="sub">Week of {WEEK_START} to {WEEK_END} &nbsp;·&nbsp; Fresh rubric, no baseline carried forward &nbsp;·&nbsp; Passing bar: 80/100</div>
  </div>
  <div class="stats-bar">
    <div class="stat"><div class="num">{n_total}</div><div class="lbl">calls pulled</div></div>
    <div class="stat"><div class="num">{n_graded}</div><div class="lbl">graded</div></div>
    <div class="stat"><div class="num">{n_skipped}</div><div class="lbl">skipped</div></div>
    <div class="stat"><div class="num" style="color:{score_color(avg_score)}">{avg_score}</div><div class="lbl">company avg / 100</div></div>
    <div class="stat"><div class="num" style="color:{GREEN if pass_count else RED}">{pass_count}</div><div class="lbl">calls passing (80+)</div></div>
  </div>

  <div class="section">
    <h2>Leaderboard</h2>
    <table>
      <tr><th>#</th><th>Rep</th><th>Calls</th><th>Avg</th><th>Passes</th></tr>
      {leaderboard_rows()}
    </table>
  </div>

  <div class="section">
    <h2>Where the score is going (company-wide, % of max)</h2>
    {comp_gap_rows()}
  </div>

  {rep_sections_html}

  <div class="section" style="color:#999;font-size:11px;padding:12px 0 40px;">
    This page is public but marked no-index — it isn't listed anywhere or access-gated. Anyone with this exact link can view it, including the transcripts below.
  </div>

</body>
</html>'''

OUT_PATH.write_text(html_out)
print(f"Written: {OUT_PATH}  ({len(html_out)/1024:.0f} KB)")
