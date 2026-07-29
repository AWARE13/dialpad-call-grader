#!/usr/bin/env python3
"""
build_weekly_report_v2.py — Rebuilds the weekly report in the established
rep-grouped / call-card format (matching report_2026-06-11.html / report_2026-07-03.html):
recording listen links, per-call section breakdowns, diff-flag badges, phone presence.

Usage:
    python3 scripts/build_weekly_report_v2.py 2026-07-27
"""
import json, glob, sys, html
from pathlib import Path
from collections import defaultdict

RUN_DATE = sys.argv[1] if len(sys.argv) > 1 else "2026-07-27"
GRADES_DIR = Path(__file__).parent.parent / "output" / "weekly" / "grades" / RUN_DATE
OUT_PATH = Path(__file__).parent.parent / "output" / "weekly" / f"{RUN_DATE}_weekly_report.html"

SECTION_KEYS = ["1_set_agenda", "2_probe", "3_pricing", "4_clock", "5_estimate",
                "6_save_your_ass", "7_quote_booking", "8_politeness", "9_bonus"]
SECTION_LABELS = {
    "1_set_agenda": "Set the agenda", "2_probe": "Probe for info",
    "3_pricing": "Pricing & differentiators", "4_clock": "Clock",
    "5_estimate": "Estimate", "6_save_your_ass": "Save Your Ass",
    "7_quote_booking": "Quote / booking", "8_politeness": "Politeness", "9_bonus": "Bonus",
}
SECTION_MAX = {"1_set_agenda": 7, "2_probe": 9, "3_pricing": 20, "4_clock": 4, "5_estimate": 13,
               "6_save_your_ass": 10, "7_quote_booking": 11, "8_politeness": 3, "9_bonus": 8}

GREEN, BLUE, ORANGE, RED = "#639922", "#185fa5", "#E8630A", "#a32d2d"

def parse_frac(s):
    if not s or "/" not in str(s):
        return None
    n, d = str(s).split("/")
    return float(n)

def sec_color(v, mx):
    pct = v / mx if mx else 0
    if pct >= 0.9: return GREEN
    if pct >= 0.6: return BLUE
    if pct >= 0.35: return ORANGE
    return RED

def score_color(s):
    if s is None: return "#888"
    if s >= 77: return GREEN
    if s >= 60: return BLUE
    if s >= 45: return ORANGE
    return RED

def esc(x):
    return html.escape(str(x)) if x is not None else ""

files = sorted(glob.glob(str(GRADES_DIR / "*.json")))
calls = [json.load(open(f)) for f in files]

graded = [c for c in calls if c["call_type"] == "full_sales_call" and c.get("total_score") is not None]
skipped = [c for c in calls if c["call_type"] != "full_sales_call" or c.get("total_score") is None]

total_calls = len(calls)
n_graded = len(graded)
avg_score = round(sum(c["total_score"] for c in graded) / n_graded, 1) if graded else 0
mastery_count = sum(1 for c in graded if c.get("mastery"))
unique_reps = sorted(set(c["rep_name"] for c in calls))

diff_fields = ["save_your_ass_hit", "meet_your_mover_hit", "on_time_guarantee_hit", "email_handoff_hit", "agenda_opener_hit"]
diff_pct = {f: round(100 * sum(1 for c in graded if c.get(f)) / n_graded) for f in diff_fields}

# section performance (avg + rate) across graded calls
sec_stats = {}
for k in SECTION_KEYS:
    vals = [parse_frac(c["section_scores"].get(k)) for c in graded if c.get("section_scores")]
    vals = [v for v in vals if v is not None]
    avg = sum(vals) / len(vals) if vals else 0
    sec_stats[k] = {"avg": round(avg, 1), "max": SECTION_MAX[k], "pct": round(100 * avg / SECTION_MAX[k]) if SECTION_MAX[k] else 0}

# phone presence distribution
presence_labels = ["Outstanding", "Engaging", "Adequate", "Flat", "Disengaging"]
presence_colors = {"Outstanding": GREEN, "Engaging": BLUE, "Adequate": ORANGE, "Flat": RED, "Disengaging": "#711f1f"}
presence_counts = {lbl: 0 for lbl in presence_labels}
for c in graded:
    lbl = c.get("phone_presence_label")
    if lbl in presence_counts:
        presence_counts[lbl] += 1
audio_flag_count = sum(1 for c in graded if c.get("audio_review_flag"))

# rep grouping
by_rep = defaultdict(list)
for c in calls:
    by_rep[c["rep_name"]].append(c)

rep_rows = []
for rep, entries in by_rep.items():
    branch = entries[0]["branch"].replace(" Einstein Moving Company", "")
    scored = [e["total_score"] for e in entries if e.get("total_score") is not None]
    presence_scores = [e["phone_presence_score"] for e in entries if e.get("phone_presence_score") is not None]
    presence_labels_this = [e["phone_presence_label"] for e in entries if e.get("phone_presence_label")]
    sya_hits = sum(1 for e in entries if e.get("save_your_ass_hit"))
    sya_total = sum(1 for e in entries if e["call_type"] == "full_sales_call" and e.get("total_score") is not None)
    avg = round(sum(scored) / len(scored), 1) if scored else None
    avg_presence = round(sum(presence_scores) / len(presence_scores), 1) if presence_scores else None
    top_presence_label = presence_labels_this[0] if presence_labels_this else None
    rep_rows.append({
        "rep": rep, "branch": branch, "n_calls": len(entries), "n_scored": len(scored),
        "avg": avg, "avg_presence": avg_presence, "presence_label": top_presence_label,
        "sya_hits": sya_hits, "sya_total": sya_total, "audio_flag": any(e.get("audio_review_flag") for e in entries),
    })

rep_rows_ranked = sorted([r for r in rep_rows if r["avg"] is not None], key=lambda r: -r["avg"])
rep_rows_unranked = [r for r in rep_rows if r["avg"] is None]

def anchor(name):
    return name.replace(" ", "_").replace("'", "")

# ---------- HTML building blocks ----------

def leaderboard_rows():
    out = []
    for i, r in enumerate(rep_rows_ranked, 1):
        presence_str = f'{r["avg_presence"]} {r["presence_label"]}' if r["avg_presence"] is not None else "—"
        presence_color = presence_colors.get(r["presence_label"], "#888")
        sya_badge_cls = "bg" if r["sya_hits"] > 0 else "br"
        audio_icon = " 🎧" if r["audio_flag"] else ""
        calls_str = f'{r["n_scored"]}' if r["n_scored"] == r["n_calls"] else f'{r["n_scored"]} <span style="color:{ORANGE};font-size:11px">({r["n_calls"]-r["n_scored"]} excl.)</span>'
        out.append(f'''<tr>
      <td style="color:#aaa">{i}</td>
      <td><a href="#{anchor(r["rep"])}" style="font-weight:700">{esc(r["rep"])}</a>{audio_icon}</td>
      <td style="color:#888;font-size:12px">{esc(r["branch"])}</td>
      <td>{calls_str}</td>
      <td><strong style="color:{score_color(r["avg"])}">{r["avg"]}</strong></td>
      <td><span style="color:{presence_color}">{presence_str}</span></td>
      <td><span class="bdg {sya_badge_cls}">{r["sya_hits"]}/{r["sya_total"]}</span></td>
    </tr>''')
    return "\n".join(out)

def call_card(c, idx):
    score = c.get("total_score")
    color = score_color(score)
    rec_url = c.get("recording_url")
    listen_btn = f'<a href="{rec_url}" class="listen-btn" target="_blank">▶ Listen</a>' if rec_url else '<span style="font-size:11px;color:#bbb">no recording</span>'

    sections_html = ""
    if c.get("section_scores"):
        for k in SECTION_KEYS:
            frac = c["section_scores"].get(k)
            v = parse_frac(frac)
            mx = SECTION_MAX[k]
            cc = sec_color(v, mx) if v is not None else "#bbb"
            sections_html += f'''<div class="sec-item">
          <div class="sec-name">{SECTION_LABELS[k]}</div>
          <div class="sec-score" style="color:{cc}">{frac or "—"}</div>
        </div>'''

    diff_labels = [("save_your_ass_hit", "Save Your Ass"), ("meet_your_mover_hit", "Meet Your Mover"),
                   ("on_time_guarantee_hit", "On-Time Guarantee"), ("agenda_opener_hit", "Agenda opener"),
                   ("email_handoff_hit", "Email Handoff")]
    flags_html = "".join(
        f'<span class="bdg {"bg" if c.get(f) else "br"}">{"✓" if c.get(f) else "✗"} {lbl}</span>'
        for f, lbl in diff_labels
    )

    presence_score = c.get("phone_presence_score")
    presence_label = c.get("phone_presence_label")
    presence_color = presence_colors.get(presence_label, "#888")
    customer = c.get("customer_name") or "Unknown"
    audio_flag_html = ""
    if c.get("audio_review_flag"):
        audio_flag_html = f'<div class="note-box" style="grid-column:1/-1"><div class="note-label">\U0001f3a7 Audio review flagged</div>{esc(c.get("audio_review_reason"))}</div>'

    items_missed_html = ""
    if c.get("items_missed"):
        lis = "".join(f"<li>{esc(item)}</li>" for item in c["items_missed"])
        items_missed_html = f'''<details style="margin-top:8px;font-size:12px;">
          <summary style="cursor:pointer;color:#185fa5;font-weight:600">Items missed ({len(c["items_missed"])})</summary>
          <ul style="margin:8px 0 0 18px;color:#555;line-height:1.6">{lis}</ul>
        </details>'''

    return f'''<div class="call-card">
      <div class="call-header">
        <div class="call-score" style="color:{color}">{score if score is not None else "—"}/85</div>
        <div>
          <div style="font-weight:600;font-size:13px">Call {idx} — {esc(customer)}</div>
          <div class="call-meta">
            <span>⏱ {c.get("duration_min","?")} min</span>
            <span>ID: {c["call_id"]}</span>
          </div>
        </div>
        {listen_btn}
      </div>
      <div class="sections-grid">{sections_html}</div>
      <div class="diff-flags">{flags_html}</div>
      <div class="presence-row">
        <span style="color:#888">Customer:</span> <strong>{esc(customer)}</strong>
        &nbsp;·&nbsp;
        <span style="color:#888">Phone presence:</span> <strong style="color:{presence_color}">{presence_score} — {presence_label}</strong>
      </div>
      <div class="call-notes">
        <div class="note-box">
          <div class="note-label">\U0001f4aa Top strength</div>
          {esc(c.get("top_strength") or "—")}
        </div>
        <div class="note-box">
          <div class="note-label">\U0001f3af Coaching note</div>
          {esc(c.get("coaching_note") or "—")}
        </div>
        <div class="note-box" style="grid-column:1/-1">
          <div class="note-label">\U0001f4de Phone presence</div>
          {esc(c.get("phone_presence_notes") or "—")}
        </div>
        {audio_flag_html}
      </div>
      {items_missed_html}
    </div>'''

def skip_card(c):
    reason = c.get("skip_reason") or "Not scored."
    rec_url = c.get("recording_url")
    listen = f' — <a href="{rec_url}" target="_blank" style="color:#185fa5">▶ Listen</a>' if rec_url else ""
    kind = "Walkthrough-scheduler intake (pending mini-rubric)" if c["call_type"] == "walkthrough_scheduler" else "Not a scoreable sales call"
    return f'''<div class="skip-card">
      <strong>{esc(kind)}</strong> — {c.get("duration_min","?")} min, ID {c["call_id"]}{listen}<br>
      {esc(reason)}
      {f'<br><span style="color:#888">Coaching note: {esc(c.get("coaching_note"))}</span>' if c.get("coaching_note") else ""}
    </div>'''

def rep_section(rep, entries):
    branch = entries[0]["branch"].replace(" Einstein Moving Company", "")
    scored = [e["total_score"] for e in entries if e.get("total_score") is not None]
    avg = round(sum(scored) / len(scored), 1) if scored else None
    presence_scores = [e["phone_presence_score"] for e in entries if e.get("phone_presence_score") is not None]
    avg_presence = round(sum(presence_scores) / len(presence_scores), 1) if presence_scores else None

    cards = []
    call_idx = 1
    for e in entries:
        if e["call_type"] == "full_sales_call" and e.get("total_score") is not None:
            cards.append(call_card(e, call_idx))
            call_idx += 1
        else:
            cards.append(skip_card(e))

    avg_html = f'<div class="rep-avg">{avg}/85</div><div style="font-size:11px;color:rgba(255,255,255,0.6)">avg score</div>' if avg is not None else '<div class="rep-avg" style="font-size:13px">not scored</div>'
    presence_str = f"presence avg {avg_presence}" if avg_presence is not None else ""

    return f'''<div class="rep-section" id="{anchor(rep)}">
  <div class="rep-header">
    <div>
      <h3>{esc(rep)} <span style="font-size:12px;font-weight:400;color:rgba(255,255,255,0.7)">— {esc(branch)}</span></h3>
      <span style="font-size:12px;color:rgba(255,255,255,0.6)">{len(entries)} call(s) &nbsp;·&nbsp; {presence_str}</span>
    </div>
    <div style="text-align:right">{avg_html}</div>
  </div>
  <div class="rep-calls">
    {"".join(cards)}
  </div>
</div>'''

# ---------- assemble page ----------

sec_table_rows = "".join(
    f'<tr><td>{SECTION_LABELS[k]}</td><td style="color:#aaa">{SECTION_MAX[k]}</td><td><strong>{sec_stats[k]["avg"]}</strong></td>'
    f'<td><div class="bar"><div class="bf" style="width:{sec_stats[k]["pct"]}%;background:{sec_color(sec_stats[k]["avg"], SECTION_MAX[k])}"></div></div></td></tr>'
    for k in SECTION_KEYS
)

presence_bars = ""
for lbl in presence_labels:
    n = presence_counts[lbl]
    pct = round(100 * n / n_graded) if n_graded else 0
    presence_bars += f'''<div style="margin-bottom:8px">
      <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:3px">
        <span style="color:{presence_colors[lbl]};font-weight:600">{lbl}</span><span style="color:#888">{n} ({pct}%)</span>
      </div>
      <div class="pbr" style="background:#f0f0ec"><div style="height:100%;width:{pct}%;background:{presence_colors[lbl]};border-radius:4px"></div></div>
    </div>'''

diff_cards = "".join(
    f'<div class="sc" style="text-align:center"><div class="sv" style="color:{score_color(diff_pct[f]*0.85) if False else (RED if diff_pct[f]<20 else (ORANGE if diff_pct[f]<40 else (BLUE if diff_pct[f]<70 else GREEN)))};font-size:20px">{diff_pct[f]}%</div><div class="sl" style="text-align:center">{lbl}</div></div>'
    for f, lbl in [("save_your_ass_hit","Save Your Ass"), ("meet_your_mover_hit","Meet Your Mover"),
                   ("on_time_guarantee_hit","On-Time Guarantee"), ("email_handoff_hit","Email Handoff"),
                   ("agenda_opener_hit","Agenda Opener")]
)

worst_diff = min(diff_fields, key=lambda f: diff_pct[f])
worst_diff_label = {"save_your_ass_hit":"Save Your Ass","meet_your_mover_hit":"Meet Your Mover","on_time_guarantee_hit":"On-Time Guarantee","email_handoff_hit":"Email Handoff","agenda_opener_hit":"Agenda opener"}[worst_diff]

leaderboard_html = leaderboard_rows()
rep_sections_html = "".join(rep_section(rep, entries) for rep, entries in sorted(by_rep.items(), key=lambda kv: -(next((r["avg"] for r in rep_rows if r["rep"]==kv[0] and r["avg"] is not None), -1))))

html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Einstein AI Call Grading — {RUN_DATE}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:Arial,sans-serif;background:#f5f5f2;color:#1e1e1e;font-size:14px;padding:24px}}
.hdr{{background:linear-gradient(135deg,#1e3a5f,#2d5a8e);color:#fff;padding:24px 28px;border-radius:12px;margin-bottom:20px}}
.hdr h1{{font-size:22px;font-weight:700;margin-bottom:4px}}
.hdr p{{font-size:13px;color:rgba(255,255,255,0.7)}}
.og{{color:#E8630A}}
.sg{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.sc{{background:#fff;border-radius:8px;padding:16px;border:1px solid #e5e5e0}}
.sl{{font-size:11px;color:#888;margin-bottom:6px;text-transform:uppercase;letter-spacing:.5px}}
.sv{{font-size:24px;font-weight:700}}
.ss{{font-size:11px;color:#aaa;margin-top:4px}}
.alert{{background:#fff3f0;border-left:4px solid #E8630A;padding:12px 16px;margin-bottom:20px;font-size:13px;border-radius:0 8px 8px 0}}
h2{{font-size:16px;font-weight:700;margin-bottom:12px;color:#1e3a5f}}
.card{{background:#fff;border-radius:10px;padding:20px;margin-bottom:20px;border:1px solid #e5e5e0}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{text-align:left;padding:8px 10px;border-bottom:2px solid #e5e5e0;color:#666;font-weight:600;font-size:11px;text-transform:uppercase}}
td{{padding:7px 10px;border-bottom:1px solid #f0f0ec;vertical-align:middle}}
tr:last-child td{{border-bottom:none}}
tr:hover td{{background:#fafaf8}}
.bar{{height:6px;background:#f0f0ec;border-radius:3px;width:90px;display:inline-block;vertical-align:middle}}
.bf{{height:100%;border-radius:3px}}
.bdg{{display:inline-block;font-size:10px;padding:2px 7px;border-radius:10px;font-weight:600}}
.bg{{background:#eaf3de;color:#3b6d11}}
.bb{{background:#e6f1fb;color:#185fa5}}
.bo{{background:#faeeda;color:#854f0b}}
.br{{background:#fcebeb;color:#a32d2d}}
a{{color:#185fa5;text-decoration:none}}
a:hover{{text-decoration:underline}}
.rep-section{{margin-bottom:32px}}
.rep-header{{background:#1e3a5f;color:#fff;padding:12px 18px;border-radius:10px 10px 0 0;display:flex;align-items:center;justify-content:space-between}}
.rep-header h3{{color:#fff;margin:0;font-size:15px}}
.rep-header .rep-avg{{font-size:18px;font-weight:700;color:#E8630A}}
.rep-calls{{border:1px solid #ddd;border-top:none;border-radius:0 0 10px 10px;overflow:hidden}}
.call-card{{padding:16px 20px;border-bottom:1px solid #f0f0ec;background:#fff}}
.call-card:last-child{{border-bottom:none}}
.call-header{{display:flex;align-items:center;gap:12px;margin-bottom:12px;flex-wrap:wrap}}
.call-score{{font-size:26px;font-weight:700}}
.call-meta{{font-size:12px;color:#888}}
.call-meta span{{margin-right:12px}}
.sections-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:12px 0}}
.sec-item{{background:#f8f8f6;border-radius:6px;padding:8px 10px}}
.sec-name{{font-size:10px;color:#999;text-transform:uppercase;letter-spacing:.3px;margin-bottom:4px}}
.sec-score{{font-size:16px;font-weight:700}}
.diff-flags{{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}}
.call-notes{{margin-top:10px;display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.note-box{{background:#f8f8f6;border-radius:6px;padding:10px 12px;font-size:12px}}
.note-label{{font-size:10px;color:#999;text-transform:uppercase;letter-spacing:.3px;margin-bottom:4px;font-weight:700}}
.presence-row{{display:flex;align-items:center;gap:8px;margin:8px 0;font-size:12px}}
.listen-btn{{display:inline-block;background:#1e3a5f;color:#fff;padding:5px 14px;border-radius:6px;font-size:12px;font-weight:600;text-decoration:none;margin-top:8px}}
.listen-btn:hover{{background:#2d5a8e;color:#fff;text-decoration:none}}
.pbr{{height:8px;border-radius:4px;overflow:hidden;margin-bottom:8px}}
.skip-card{{padding:12px 20px;border-bottom:1px solid #f0f0ec;background:#fafafa;font-size:12px;color:#999;font-style:italic}}
.skip-card:last-child{{border-bottom:none}}
</style>
</head>
<body>

<div class="hdr">
  <h1>⚡ Einstein AI Call Grading Report — <span class="og">Week of {RUN_DATE}</span></h1>
  <p>{len(unique_reps)}-rep roster &nbsp;·&nbsp; {n_graded} graded calls &nbsp;·&nbsp; phone presence &nbsp;·&nbsp; recording links &nbsp;·&nbsp; Powered by Gary</p>
</div>

<div class="sg">
  <div class="sc"><div class="sl">Calls graded</div><div class="sv">{n_graded}</div><div class="ss">{len(unique_reps)} reps &middot; {total_calls} calls pulled total</div></div>
  <div class="sc"><div class="sl">Team avg score</div><div class="sv">{avg_score}<span style="font-size:16px;font-weight:400">/85</span></div><div class="ss">{round(100*avg_score/85)}% of max &middot; mastery = 77</div></div>
  <div class="sc"><div class="sl">Mastery calls (77+)</div><div class="sv" style="color:{RED if mastery_count==0 else GREEN}">{mastery_count}</div><div class="ss">of {n_graded} graded</div></div>
  <div class="sc"><div class="sl">Not scored</div><div class="sv" style="color:{ORANGE}">{len(skipped)}</div><div class="ss">service/logistics calls + walkthrough intakes</div></div>
</div>

<div class="alert"><strong>Biggest gap this week: {worst_diff_label}</strong> hit on only {diff_pct[worst_diff]}% of scored calls. Save Your Ass ({diff_pct['save_your_ass_hit']}%), Meet Your Mover ({diff_pct['meet_your_mover_hit']}%), and On-Time Guarantee ({diff_pct['on_time_guarantee_hit']}%) remain the other chronic misses; Email Handoff stays the one differentiator most reps deliver ({diff_pct['email_handoff_hit']}%). {audio_flag_count} call(s) flagged for audio review this week.</div>

<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:20px">
  {diff_cards}
</div>

<div class="two" style="margin-bottom:20px">
  <div class="card">
    <h2>Section performance</h2>
    <table>
      <tr><th>Section</th><th>Max</th><th>Avg</th><th>Rate</th></tr>
      {sec_table_rows}
    </table>
  </div>
  <div class="card">
    <h2>Phone presence — {n_graded} calls</h2>
    <p style="font-size:11px;color:#888;margin-bottom:12px">Transcript-based language assessment &middot; not vocal tone</p>
    {presence_bars}
    <div style="margin-top:12px;padding-top:10px;border-top:1px solid #f0f0ec;font-size:11px;color:#888">
      <strong>{audio_flag_count} call(s) flagged for audio review</strong> — recording links on each call card below.
    </div>
  </div>
</div>

<div class="card">
  <h2>Rep leaderboard</h2>
  <table>
    <tr><th>#</th><th>Rep</th><th>Branch</th><th>Calls</th><th>Avg score</th><th>Presence</th><th>SYA</th></tr>
    {leaderboard_html}
  </table>
</div>

<hr style="border:none;border-top:2px solid #e5e5e0;margin:32px 0">
<h2 style="font-size:20px;color:#1e3a5f;margin-bottom:20px">\U0001f4cb Per-Rep Call Detail</h2>
<p style="font-size:13px;color:#666;margin-bottom:20px">Full scorecard for every graded call. Click <strong>▶ Listen</strong> to open the call recording. Excluded calls (service/logistics/walkthrough) show inline with their reason.</p>
{rep_sections_html}

<p style="font-size:12px;color:#999;margin-top:24px">Rubric: Einstein Sales Call Scorecard, 85 pts (77 standard + 8 bonus). Mastery = 77+ on 3 straight gradings. Generated by Gary (Amanda Ware's AI Chief of Staff).</p>

</body>
</html>
"""

OUT_PATH.write_text(html_out)
print("Wrote", OUT_PATH, "-", len(html_out), "chars")
