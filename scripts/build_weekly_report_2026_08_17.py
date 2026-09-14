#!/usr/bin/env python3
"""Build the weekly AI sales call grading report for a given run date."""
import json, glob, os, sys, html
from collections import defaultdict

RUN = sys.argv[1] if len(sys.argv) > 1 else "2026-08-17"
ROOT = os.path.expanduser("~/Documents/GitHub/dialpad-call-grader")
GRADES = sorted(glob.glob(f"{ROOT}/output/weekly/grades/{RUN}/*.json"))
OUT = f"{ROOT}/output/weekly/{RUN}_weekly_report.html"

G = [json.load(open(f)) for f in GRADES]
graded = [g for g in G if g["call_type"] != "skip"]
skipped = [g for g in G if g["call_type"] == "skip"]
scores = [g["total_score"] for g in graded]
avg = sum(scores) / len(scores)
mastery = [g for g in graded if g["total_score"] >= 77]

DIFFS = [
    ("save_your_ass_hit", "Save Your Ass", "The prep speech — prep before move day = shorter move = lower bill"),
    ("meet_your_mover_hit", "Meet Your Mover", "Pre-move email with the mover's photo and info"),
    ("on_time_guarantee_hit", "On-Time Guarantee", "We discount immediately if we miss the window"),
    ("email_handoff_hit", "Email Handoff", "\"I'll send you a confirmation email\""),
    ("agenda_opener_hit", "Agenda Opener", "Agenda statement + explicit \"sound good?\""),
]
SECTIONS = [
    ("1_set_agenda", "1 — Set the Agenda", 7),
    ("2_probe", "2 — Probe for Info", 9),
    ("3_pricing", "3 — Pricing / Differentiators", 20),
    ("4_clock", "4 — Clock", 4),
    ("5_estimate", "5 — Estimate", 13),
    ("6_save_your_ass", "6 — Save Your Ass", 10),
    ("7_quote_booking", "7 — Quote / Booking", 11),
    ("8_politeness", "8 — Politeness", 3),
    ("9_bonus", "9 — Bonus / Helpfulness", 8),
]

sec_pct = {}
for key, label, den in SECTIONS:
    tot = n = 0
    for g in graded:
        v = (g.get("section_scores") or {}).get(key)
        if v:
            tot += int(v.split("/")[0]); n += 1
    sec_pct[key] = (tot / n, 100 * tot / (n * den)) if n else (0, 0)

byrep = defaultdict(list)
for g in graded:
    byrep[g["rep_name"]].append(g)
rank = sorted(byrep.items(), key=lambda x: -sum(c["total_score"] for c in x[1]) / len(x[1]))
top_rep, top_calls = rank[0]
low_rep, low_calls = rank[-1]
top_avg = sum(c["total_score"] for c in top_calls) / len(top_calls)
low_avg = sum(c["total_score"] for c in low_calls) / len(low_calls)

pp = [g["phone_presence_score"] for g in graded if g.get("phone_presence_score")]
audio_flags = [g for g in G if g.get("audio_review_flag")]

pat = json.load(open(f"{ROOT}/output/patterns.json"))


def band(s):
    return "g" if s >= 77 else ("a" if s >= 60 else "r")


def esc(s):
    return html.escape(str(s or ""))


rows = []
for rep, calls in rank:
    calls = sorted(calls, key=lambda c: -c["total_score"])
    ravg = sum(c["total_score"] for c in calls) / len(calls)
    cells = "".join(
        f'<td class="sc {band(c["total_score"])}">{c["total_score"]}</td>' for c in calls
    )
    cells += '<td class="sc na">—</td>' * (2 - len(calls))
    best = calls[0]
    rows.append(f"""<tr>
      <td class="rep">{esc(rep)}<span class="br">{esc(best['branch'].replace(' Einstein Moving Company',''))}</span></td>
      <td class="sc {band(round(ravg))}"><b>{ravg:.1f}</b></td>
      {cells}
      <td class="txt">{esc(best['top_strength'])}</td>
      <td class="txt">{esc(best['coaching_note'])}</td>
    </tr>""")

diff_cards = ""
for key, label, desc in DIFFS:
    n = sum(1 for g in graded if g.get(key))
    pct = 100 * n / len(graded)
    at = pat.get(key, 0); atp = 100 * at / pat["total_calls_graded"]
    cls = "g" if pct >= 60 else ("a" if pct >= 25 else "r")
    diff_cards += f"""<div class="dcard">
      <div class="dlabel">{label}</div>
      <div class="dpct {cls}">{pct:.0f}%</div>
      <div class="dbar"><span class="{cls}" style="width:{pct:.0f}%"></span></div>
      <div class="dsub">{n} of {len(graded)} calls &nbsp;·&nbsp; all-time {atp:.0f}%</div>
      <div class="ddesc">{desc}</div>
    </div>"""

sec_rows = ""
for key, label, den in SECTIONS:
    a, pct = sec_pct[key]
    cls = "g" if pct >= 75 else ("a" if pct >= 55 else "r")
    sec_rows += f"""<tr><td class="txt"><b>{label}</b></td>
      <td class="sc">{a:.1f} / {den}</td>
      <td style="width:45%"><div class="dbar"><span class="{cls}" style="width:{pct:.0f}%"></span></div></td>
      <td class="sc {cls}">{pct:.0f}%</td></tr>"""

skip_rows = "".join(
    f'<tr><td class="rep">{esc(g["rep_name"])}</td><td class="txt">{esc(g["skip_reason"])}</td></tr>'
    for g in skipped
)
audio_rows = "".join(
    f'<tr><td class="rep">{esc(g["rep_name"])}</td><td class="sc">{g.get("phone_presence_score") or "—"}</td>'
    f'<td class="txt">{esc(g.get("audio_review_reason"))}</td></tr>'
    for g in sorted(audio_flags, key=lambda x: (x.get("phone_presence_score") or 9))
)

HTML = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Weekly Sales Call Grading — {RUN}</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:#f4f5f7;color:#1c2434;font:15px/1.55 Roboto,Arial,Helvetica,sans-serif}}
.wrap{{max-width:1240px;margin:0 auto;padding:0 20px 60px}}
header{{background:#E8630A;color:#fff;padding:30px 20px 26px}}
header .inner{{max-width:1240px;margin:0 auto}}
header h1{{margin:0;font-size:26px;font-weight:700;letter-spacing:-.3px}}
header .sub{{margin-top:6px;opacity:.92;font-size:14px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;margin:-22px 0 26px}}
.card{{background:#fff;border-radius:10px;padding:16px 18px;box-shadow:0 1px 3px rgba(16,24,40,.10)}}
.card .k{{font-size:11px;letter-spacing:.7px;text-transform:uppercase;color:#6b7382;font-weight:600}}
.card .v{{font-size:30px;font-weight:700;line-height:1.15;margin-top:4px}}
.card .n{{font-size:12px;color:#6b7382;margin-top:2px}}
h2{{font-size:17px;margin:32px 0 12px;padding-bottom:8px;border-bottom:2px solid #E8630A;font-weight:700}}
.panel{{background:#fff;border-radius:10px;box-shadow:0 1px 3px rgba(16,24,40,.10);overflow:hidden}}
.tblwrap{{overflow-x:auto}}
table{{border-collapse:collapse;width:100%;min-width:820px}}
th{{background:#1c2434;color:#fff;font-size:11px;letter-spacing:.6px;text-transform:uppercase;
   text-align:left;padding:10px 12px;font-weight:600;white-space:nowrap}}
td{{padding:11px 12px;border-bottom:1px solid #eceef2;vertical-align:top}}
tr:last-child td{{border-bottom:0}}
tbody tr:nth-child(even){{background:#fafbfc}}
.rep{{font-weight:600;white-space:nowrap}}
.rep .br{{display:block;font-weight:400;font-size:11px;color:#8a919e;margin-top:1px}}
.sc{{text-align:center;font-variant-numeric:tabular-nums;font-weight:600;white-space:nowrap}}
.txt{{font-size:13px;color:#39414f;line-height:1.5;min-width:230px}}
td.g,.dpct.g{{color:#137a41}} td.a,.dpct.a{{color:#a86400}} td.r,.dpct.r{{color:#b3261e}}
td.na{{color:#c3c8d1}}
.dgrid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:14px}}
.dcard{{background:#fff;border-radius:10px;padding:16px 18px;box-shadow:0 1px 3px rgba(16,24,40,.10)}}
.dlabel{{font-size:13px;font-weight:700}}
.dpct{{font-size:28px;font-weight:700;line-height:1.2;margin:2px 0 6px}}
.dbar{{background:#eceef2;border-radius:99px;height:7px;overflow:hidden}}
.dbar span{{display:block;height:100%;border-radius:99px}}
.dbar span.g{{background:#1a9955}} .dbar span.a{{background:#e8a600}} .dbar span.r{{background:#d1372c}}
.dsub{{font-size:11px;color:#6b7382;margin-top:7px;font-weight:500}}
.ddesc{{font-size:11.5px;color:#8a919e;margin-top:5px;line-height:1.45}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
@media(max-width:820px){{.two{{grid-template-columns:1fr}}}}
.spot{{background:#fff;border-radius:10px;box-shadow:0 1px 3px rgba(16,24,40,.10);padding:18px 20px;border-left:4px solid #1a9955}}
.spot.warn{{border-left-color:#d1372c}}
.spot .h{{font-size:11px;letter-spacing:.7px;text-transform:uppercase;color:#6b7382;font-weight:600}}
.spot .n{{font-size:21px;font-weight:700;margin:3px 0 2px}}
.spot .s{{font-size:13px;color:#39414f;line-height:1.5;margin-top:8px}}
.note{{background:#fff6ec;border:1px solid #f6d5b3;border-radius:10px;padding:14px 18px;
      font-size:13px;color:#5c4326;line-height:1.55;margin-top:14px}}
.legend{{font-size:12px;color:#8a919e;margin-top:9px}}
footer{{margin-top:34px;font-size:12px;color:#8a919e;line-height:1.6}}
</style></head><body>
<header><div class="inner">
  <h1>Weekly Sales Call Grading</h1>
  <div class="sub">Einstein Moving Company &nbsp;·&nbsp; week ending {RUN} &nbsp;·&nbsp; Dialpad transcripts, graded against the 85-pt Sales Call Scorecard</div>
</div></header>

<div class="wrap">
<div class="cards">
  <div class="card"><div class="k">Avg Score</div><div class="v {band(round(avg))}">{avg:.1f}</div><div class="n">out of 85 · mastery = 77</div></div>
  <div class="card"><div class="k">Calls Graded</div><div class="v">{len(graded)}</div><div class="n">{len(byrep)} reps · {len(skipped)} skipped</div></div>
  <div class="card"><div class="k">At Mastery</div><div class="v {'g' if mastery else 'r'}">{len(mastery)}</div><div class="n">77+ this week</div></div>
  <div class="card"><div class="k">Score Range</div><div class="v">{min(scores)}–{max(scores)}</div><div class="n">low to high</div></div>
  <div class="card"><div class="k">Phone Presence</div><div class="v">{sum(pp)/len(pp):.1f}</div><div class="n">avg of 5 · {len(audio_flags)} audio flags</div></div>
</div>

<h2>Differentiator hit rates</h2>
<div class="dgrid">{diff_cards}</div>

<h2>Where the points are going</h2>
<div class="panel"><div class="tblwrap"><table>
<thead><tr><th>Scorecard section</th><th style="text-align:center">Avg earned</th><th>Coverage</th><th style="text-align:center">%</th></tr></thead>
<tbody>{sec_rows}</tbody></table></div></div>
<div class="legend">Green ≥75% · amber 55–74% · red &lt;55%. N/A bullets earn the point automatically, so sections can score high on calls where they barely applied.</div>

<h2>Top performer &amp; coaching priority</h2>
<div class="two">
  <div class="spot">
    <div class="h">Top performer this week</div>
    <div class="n">{esc(top_rep)} — {top_avg:.1f} avg</div>
    <div class="n" style="font-size:12px;color:#6b7382;font-weight:500">{' · '.join(str(c['total_score']) for c in sorted(top_calls,key=lambda x:-x['total_score']))} &nbsp;|&nbsp; {esc(top_calls[0]['branch'].replace(' Einstein Moving Company',''))}</div>
    <div class="s">{esc(sorted(top_calls,key=lambda x:-x['total_score'])[0]['top_strength'])}</div>
  </div>
  <div class="spot warn">
    <div class="h">Coaching priority this week</div>
    <div class="n">{esc(low_rep)} — {low_avg:.1f} avg</div>
    <div class="n" style="font-size:12px;color:#6b7382;font-weight:500">{' · '.join(str(c['total_score']) for c in sorted(low_calls,key=lambda x:-x['total_score']))} &nbsp;|&nbsp; {esc(low_calls[0]['branch'].replace(' Einstein Moving Company',''))}</div>
    <div class="s">{esc(sorted(low_calls,key=lambda x:x['total_score'])[0]['coaching_note'])}</div>
  </div>
</div>
<div class="note"><b>#1 gap company-wide:</b> Save Your Ass — the prep speech landed on {sum(1 for g in graded if g.get('save_your_ass_hit'))} of {len(graded)} calls ({100*sum(1 for g in graded if g.get('save_your_ass_hit'))/len(graded):.0f}%), and the section averaged {sec_pct['6_save_your_ass'][0]:.1f} of 10 points. It is the single largest recoverable block on the scorecard and it is the one most directly tied to move-time accuracy — a customer who preps runs a shorter move, which pulls the actual closer to the estimate.</div>

<h2>Per-rep results</h2>
<div class="panel"><div class="tblwrap"><table>
<thead><tr><th>Rep</th><th style="text-align:center">Avg</th><th style="text-align:center">Call 1</th><th style="text-align:center">Call 2</th><th>Top strength (best call)</th><th>Coaching note</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div></div>
<div class="legend">Sorted by average. Green 77+ · amber 60–76 · red below 60.</div>

<h2>Flagged for audio review ({len(audio_flags)})</h2>
<div class="panel"><div class="tblwrap"><table>
<thead><tr><th>Rep</th><th style="text-align:center">Presence</th><th>Why flagged</th></tr></thead>
<tbody>{audio_rows}</tbody></table></div></div>

<h2>Skipped calls ({len(skipped)})</h2>
<div class="panel"><div class="tblwrap"><table>
<thead><tr><th>Rep</th><th>Reason</th></tr></thead>
<tbody>{skip_rows}</tbody></table></div></div>

<h2>All-time pattern totals</h2>
<div class="panel"><div class="tblwrap"><table>
<thead><tr><th>Differentiator</th><th style="text-align:center">All-time hits</th><th style="text-align:center">All-time rate</th><th style="text-align:center">This week</th></tr></thead>
<tbody>{''.join(
  f'<tr><td class="txt"><b>{label}</b></td><td class="sc">{pat[key]} / {pat["total_calls_graded"]}</td>'
  f'<td class="sc">{100*pat[key]/pat["total_calls_graded"]:.0f}%</td>'
  f'<td class="sc {"g" if 100*sum(1 for g in graded if g.get(key))/len(graded)>=60 else ("a" if 100*sum(1 for g in graded if g.get(key))/len(graded)>=25 else "r")}">'
  f'{100*sum(1 for g in graded if g.get(key))/len(graded):.0f}%</td></tr>'
  for key,label,_ in DIFFS)}</tbody></table></div></div>
<div class="legend">{pat['total_calls_graded']} calls graded all-time across all runs.</div>
<div class="note">{esc(pat['notes'])}</div>

<footer>
Generated {RUN} by Gary (AI Chief of Staff) · scheduled task <code>weekly-call-grading</code>.<br>
Rubric: <code>config/rubric.md</code> (85 pts, mastery = 77+). Grades: <code>output/weekly/grades/{RUN}/</code>. Transcripts: <code>output/weekly/calls/{RUN}/</code>.<br>
Scoring method: sections whose bullet count differs from their point value were scored proportionally to coverage. Per the rubric, bullets that genuinely do not apply to a call are granted automatically — which lifts Section 5 (Estimate) on short calls where little was actually quoted.<br>
Phone presence is assessed from transcript language only, not vocal tone.
</footer>
</div></body></html>"""

open(OUT, "w").write(HTML)
print("wrote", OUT, len(HTML), "bytes")
