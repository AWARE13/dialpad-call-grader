#!/usr/bin/env python3
"""Build the 2026-08-25 weekly call-grading report + update patterns.json."""

import glob
import html
import json
import os
import statistics
from collections import defaultdict

RUN_DATE = "2026-08-25"
ROOT = os.path.expanduser("~/Documents/GitHub/dialpad-call-grader")
GRADES = os.path.join(ROOT, "output/weekly/grades", RUN_DATE)
PATTERNS = os.path.join(ROOT, "output/patterns.json")
REPORT = os.path.join(ROOT, "output/weekly", f"{RUN_DATE}_weekly_report.html")

GREEN_BAR = 65
SUPER_GREEN = 75
MASTERY = 77

grades = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(GRADES, "*.json")))]
full = [g for g in grades if g["call_type"] == "full_sales_call"]
walk = [g for g in grades if g["call_type"] == "walkthrough_scheduler"]
skipped = [g for g in grades if g["call_type"] == "skip"]
scored = full + walk

full_avg = statistics.mean([g["total_score"] for g in full])
walk_avg = statistics.mean([g["total_score"] for g in walk]) if walk else 0

# ---------------------------------------------------------------- patterns.json
pat = json.load(open(PATTERNS))
prior_total = pat["total_calls_graded"]
prior_scores = pat["scores"]

# cumulative average BEFORE this run, and last-3-runs average, for trend framing
prior_by_date = defaultdict(list)
for s in prior_scores:
    prior_by_date[s["date"]].append(s["score"])
prior_dates = sorted(prior_by_date)
prior_cum_avg = statistics.mean([s["score"] for s in prior_scores])

for g in scored:
    pat["scores"].append({
        "date": RUN_DATE,
        "rep": g["rep_name"],
        "branch": g["branch"].replace(" Einstein Moving Company", ""),
        "score": g["total_score"],
        "type": g["call_type"],
    })

pat["total_calls_graded"] = prior_total + len(scored)
for key in ("save_your_ass_hit", "meet_your_mover_hit", "on_time_guarantee_hit",
            "email_handoff_hit", "agenda_opener_hit"):
    pat[key] += sum(1 for g in scored if g.get(key))

json.dump(pat, open(PATTERNS, "w"), indent=2)

cum_avg = statistics.mean([s["score"] for s in pat["scores"]])
all_dates = sorted({s["date"] for s in pat["scores"]})
last3 = all_dates[-3:]
last3_avg = statistics.mean([s["score"] for s in pat["scores"] if s["date"] in last3])

# ---------------------------------------------------------------- per-rep rollup
by_rep = defaultdict(list)
for g in scored:
    by_rep[g["rep_name"]].append(g)
rep_rows = []
for rep, gs in by_rep.items():
    gs = sorted(gs, key=lambda x: x["call_id"])
    avg = statistics.mean([g["total_score"] for g in gs])
    best = max(gs, key=lambda x: x["total_score"])
    worst = min(gs, key=lambda x: x["total_score"])
    rep_rows.append({
        "rep": rep,
        "branch": gs[0]["branch"].replace(" Einstein Moving Company", ""),
        "scores": [(g["total_score"], g["call_type"]) for g in gs],
        "avg": avg,
        "strength": best["top_strength"],
        "coaching": worst["coaching_note"],
        "presence": statistics.mean([g["phone_presence_score"] for g in gs]),
        "flagged": any(g.get("audio_review_flag") for g in gs),
    })
rep_rows.sort(key=lambda r: -r["avg"])

full_only_rep = {}
for g in full:
    full_only_rep.setdefault(g["rep_name"], []).append(g["total_score"])
full_avgs = {r: statistics.mean(v) for r, v in full_only_rep.items()}
top_rep = max(full_avgs, key=lambda r: (full_avgs[r], len(full_only_rep[r])))
bottom_rep = min(full_avgs, key=lambda r: full_avgs[r])
bottom_worst = min([g for g in full if g["rep_name"] == bottom_rep],
                   key=lambda g: g["total_score"])
top_best = max([g for g in full if g["rep_name"] == top_rep],
               key=lambda g: g["total_score"])

# ---------------------------------------------------------------- differentiators
DIFFS = [
    ("Agenda Opener", "agenda_opener_hit"),
    ("Save Your Ass", "save_your_ass_hit"),
    ("Meet Your Mover", "meet_your_mover_hit"),
    ("On-Time Guarantee", "on_time_guarantee_hit"),
    ("Email Handoff", "email_handoff_hit"),
]
diff_rows = []
for label, key in DIFFS:
    hits = sum(1 for g in scored if g.get(key))
    diff_rows.append((label, key, hits, len(scored), 100 * hits / len(scored),
                      pat[key], pat["total_calls_graded"],
                      100 * pat[key] / pat["total_calls_graded"]))

# ---------------------------------------------------------------- section averages
SECTIONS = [
    ("1_set_agenda", "Set the Agenda", 7),
    ("2_probe", "Probe / Pain Points", 9),
    ("3_pricing", "Pricing + Differentiators", 20),
    ("4_clock", "Clock", 4),
    ("5_estimate", "Estimate", 13),
    ("6_save_your_ass", "Save Your Ass", 10),
    ("7_quote_booking", "Quote / Booking", 11),
    ("8_politeness", "Politeness", 3),
    ("9_bonus", "Bonus / Helpfulness", 8),
]
sec_rows = []
for key, label, denom in SECTIONS:
    vals = [int(g["section_scores"][key].split("/")[0]) for g in full]
    avg = statistics.mean(vals)
    sec_rows.append((label, avg, denom, 100 * avg / denom))
sec_sorted = sorted(sec_rows, key=lambda r: r[3])

presence_avg = statistics.mean([g["phone_presence_score"] for g in scored])
flagged = [g for g in scored if g.get("audio_review_flag")]


def band(score):
    if score >= MASTERY:
        return "green"
    if score >= 60:
        return "amber"
    return "red"


def esc(s):
    return html.escape(str(s)) if s else ""


rep_html = ""
for r in rep_rows:
    cells = ""
    for i in range(2):
        if i < len(r["scores"]):
            sc, ct = r["scores"][i]
            tag = ' <span class="wt">W</span>' if ct == "walkthrough_scheduler" else ""
            cells += f'<td class="score {band(sc)}">{sc}{tag}</td>'
        else:
            cells += '<td class="score none">&mdash;</td>'
    flag = ' <span class="flag" title="Flagged for audio review">&#9834;</span>' if r["flagged"] else ""
    rep_html += f"""      <tr>
        <td class="rep">{esc(r['rep'])}{flag}<span class="branch">{esc(r['branch'])}</span></td>
        {cells}
        <td class="score {band(r['avg'])}">{r['avg']:.0f}</td>
        <td class="pres">{r['presence']:.1f}</td>
        <td class="txt">{esc(r['strength'])}</td>
        <td class="txt coach">{esc(r['coaching'])}</td>
      </tr>
"""

diff_html = ""
for label, key, hits, n, pct, cum_hits, cum_n, cum_pct in diff_rows:
    barclass = "red" if pct < 35 else ("amber" if pct < 70 else "green")
    diff_html += f"""      <tr>
        <td class="rep">{label}</td>
        <td class="score {barclass}">{pct:.0f}%</td>
        <td class="mono">{hits} / {n}</td>
        <td class="mono dim">{cum_pct:.0f}%</td>
        <td class="mono dim">{cum_hits} / {cum_n}</td>
      </tr>
"""

sec_html = ""
for label, avg, denom, pct in sec_rows:
    barclass = "red" if pct < 45 else ("amber" if pct < 70 else "green")
    sec_html += f"""      <tr>
        <td class="rep">{label}</td>
        <td class="mono">{avg:.1f} / {denom}</td>
        <td class="score {barclass}">{pct:.0f}%</td>
        <td class="barcell"><div class="bar"><span class="{barclass}" style="width:{pct:.0f}%"></span></div></td>
      </tr>
"""

skip_html = ""
for g in sorted(skipped, key=lambda x: x["rep_name"]):
    skip_html += f"""      <tr>
        <td class="rep">{esc(g['rep_name'])}<span class="branch">{esc(g['branch'].replace(' Einstein Moving Company',''))}</span></td>
        <td class="mono dim">{g['duration_min']} min</td>
        <td class="txt">{esc(g['skip_reason'])}</td>
      </tr>
"""

trend_delta = full_avg - prior_cum_avg

HTML = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Einstein Sales Call Grading &mdash; Week of {RUN_DATE}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: #f4f5f7; color: #1c2434;
    font-family: Roboto, Arial, Helvetica, sans-serif; font-size: 15px; line-height: 1.5;
  }}
  .wrap {{ max-width: 1240px; margin: 0 auto; padding: 0 20px 64px; }}
  header {{ background: #E8630A; color: #fff; padding: 28px 0 24px; margin-bottom: 28px; }}
  header .wrap {{ padding-bottom: 0; }}
  header h1 {{ margin: 0 0 4px; font-size: 26px; font-weight: 700; letter-spacing: -0.01em; }}
  header p {{ margin: 0; opacity: .92; font-size: 15px; }}
  h2 {{ font-size: 18px; margin: 34px 0 12px; color: #1c2434; }}
  h2 .sub {{ font-weight: 400; color: #6b7280; font-size: 14px; margin-left: 8px; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(178px, 1fr)); gap: 14px; }}
  .card {{ background: #fff; border-radius: 8px; padding: 16px 18px; border: 1px solid #e4e7ec;
           box-shadow: 0 1px 2px rgba(16,24,40,.05); }}
  .card .label {{ font-size: 12px; text-transform: uppercase; letter-spacing: .06em; color: #6b7280;
                  font-weight: 600; margin-bottom: 6px; }}
  .card .value {{ font-size: 30px; font-weight: 700; line-height: 1.1; }}
  .card .note {{ font-size: 13px; color: #6b7280; margin-top: 4px; }}
  .green {{ color: #067647; }} .amber {{ color: #b54708; }} .red {{ color: #b42318; }}
  td.score {{ font-weight: 700; text-align: center; font-variant-numeric: tabular-nums; }}
  td.score.green {{ background: #ecfdf3; }} td.score.amber {{ background: #fffaeb; }}
  td.score.red {{ background: #fef3f2; }} td.score.none {{ color: #cbd2dc; background: #fafbfc; }}
  .panel {{ background: #fff; border: 1px solid #e4e7ec; border-radius: 8px; overflow: hidden;
            box-shadow: 0 1px 2px rgba(16,24,40,.05); }}
  .scroller {{ overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  th {{ background: #fafbfc; text-align: left; padding: 10px 12px; font-size: 12px;
        text-transform: uppercase; letter-spacing: .05em; color: #6b7280; font-weight: 600;
        border-bottom: 1px solid #e4e7ec; white-space: nowrap; }}
  td {{ padding: 11px 12px; border-bottom: 1px solid #f0f1f4; vertical-align: top; }}
  tr:last-child td {{ border-bottom: none; }}
  td.rep {{ font-weight: 600; white-space: nowrap; }}
  td.rep .branch {{ display: block; font-weight: 400; font-size: 12px; color: #6b7280; }}
  td.txt {{ font-size: 13px; color: #344054; min-width: 260px; }}
  td.coach {{ color: #7a3a06; }}
  td.mono {{ font-variant-numeric: tabular-nums; white-space: nowrap; }}
  td.dim {{ color: #6b7280; }}
  td.pres {{ text-align: center; font-variant-numeric: tabular-nums; color: #475467; }}
  .wt {{ font-size: 10px; background: #eef2ff; color: #3538cd; border-radius: 3px;
         padding: 1px 4px; vertical-align: super; font-weight: 700; }}
  .flag {{ color: #b54708; }}
  .barcell {{ width: 190px; }}
  .bar {{ background: #f0f1f4; border-radius: 3px; height: 8px; overflow: hidden; }}
  .bar span {{ display: block; height: 100%; border-radius: 3px; }}
  .bar span.green {{ background: #17b26a; }} .bar span.amber {{ background: #f79009; }}
  .bar span.red {{ background: #f04438; }}
  .callout {{ background: #fff; border-left: 4px solid #E8630A; border-radius: 6px;
              padding: 16px 20px; margin: 14px 0; border-top: 1px solid #e4e7ec;
              border-right: 1px solid #e4e7ec; border-bottom: 1px solid #e4e7ec; }}
  .callout h3 {{ margin: 0 0 6px; font-size: 15px; }}
  .callout p {{ margin: 0 0 8px; font-size: 14px; color: #344054; }}
  .callout p:last-child {{ margin-bottom: 0; }}
  .note-box {{ background: #fffaeb; border: 1px solid #fedf89; border-radius: 6px;
               padding: 14px 18px; font-size: 13.5px; color: #7a3a06; margin: 14px 0; }}
  footer {{ margin-top: 40px; padding-top: 18px; border-top: 1px solid #e4e7ec;
            font-size: 12.5px; color: #6b7280; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>Sales Call Grading &mdash; Week of {RUN_DATE}</h1>
    <p>Dialpad AI audit &middot; {len(grades)} calls pulled &middot; {len(scored)} graded &middot; {len(skipped)} skipped as non-sales</p>
  </div>
</header>
<div class="wrap">

  <div class="cards">
    <div class="card">
      <div class="label">Avg &mdash; full sales calls</div>
      <div class="value {band(full_avg)}">{full_avg:.1f}</div>
      <div class="note">out of 85 &middot; n={len(full)}</div>
    </div>
    <div class="card">
      <div class="label">Gap to green bar</div>
      <div class="value red">&minus;{GREEN_BAR - full_avg:.1f}</div>
      <div class="note">green bar = {GREEN_BAR}, super green = {SUPER_GREEN}</div>
    </div>
    <div class="card">
      <div class="label">Mastery (77+)</div>
      <div class="value red">0</div>
      <div class="note">of {len(scored)} graded calls</div>
    </div>
    <div class="card">
      <div class="label">Reps graded</div>
      <div class="value">{len(by_rep)}</div>
      <div class="note">{len(scored)} scored calls</div>
    </div>
    <div class="card">
      <div class="label">Vs. cumulative avg</div>
      <div class="value {'red' if trend_delta < 0 else 'green'}">{trend_delta:+.1f}</div>
      <div class="note">prior cumulative was {prior_cum_avg:.1f}</div>
    </div>
    <div class="card">
      <div class="label">Phone presence</div>
      <div class="value amber">{presence_avg:.1f}</div>
      <div class="note">of 5 &middot; {len(flagged)} flagged for audio</div>
    </div>
  </div>

  <div class="note-box">
    <strong>Read this before comparing scores.</strong> The {len(walk)} walkthrough-scheduler calls
    (marked <span class="wt">W</span>) score against a partial rubric &mdash; Pricing, Clock, Estimate and
    Save Your Ass do not apply, so those points are granted automatically. Their {walk_avg:.1f} average is
    <em>not</em> comparable to a full sales call. The headline number above is full sales calls only.
  </div>

  <div class="callout">
    <h3>Top performer &mdash; {esc(top_rep)} ({full_avgs[top_rep]:.1f} avg, {len(full_only_rep[top_rep])} call{'s' if len(full_only_rep[top_rep]) > 1 else ''})</h3>
    <p>{esc(top_best['top_strength'])}</p>
    <p><em>Still short of the {GREEN_BAR}-point green bar &mdash; nobody cleared it this week.</em></p>
  </div>

  <div class="callout">
    <h3>Coaching priority &mdash; {esc(bottom_rep)} ({full_avgs[bottom_rep]:.1f} avg)</h3>
    <p>{esc(bottom_worst['coaching_note'])}</p>
  </div>

  <div class="callout">
    <h3>#1 company-wide gap &mdash; {sec_sorted[0][0]} ({sec_sorted[0][3]:.0f}% of available points)</h3>
    <p>Across {len(full)} full sales calls the team averaged {sec_sorted[0][1]:.1f} of {sec_sorted[0][2]} points here.
    The prep speech is the single highest-leverage section for move efficiency &mdash; it is the direct lever on
    estimate accuracy, and it is being skipped on {100 - 100 * sum(1 for g in full if g.get('save_your_ass_hit')) / len(full):.0f}% of calls.</p>
  </div>

  <h2>Differentiator hit rates <span class="sub">this run vs. all-time</span></h2>
  <div class="panel"><div class="scroller"><table>
    <thead><tr><th>Differentiator</th><th>This run</th><th>Hits</th><th>All-time</th><th>All-time hits</th></tr></thead>
    <tbody>
{diff_html}    </tbody>
  </table></div></div>

  <h2>Section performance <span class="sub">full sales calls only, n={len(full)}</span></h2>
  <div class="panel"><div class="scroller"><table>
    <thead><tr><th>Section</th><th>Avg</th><th>%</th><th></th></tr></thead>
    <tbody>
{sec_html}    </tbody>
  </table></div></div>

  <h2>Per-rep results <span class="sub">ranked by average &middot; <span class="wt">W</span> = walkthrough scheduler (partial rubric) &middot; &#9834; = flagged for audio review</span></h2>
  <div class="panel"><div class="scroller"><table>
    <thead><tr><th>Rep</th><th>Call 1</th><th>Call 2</th><th>Avg</th><th>Pres.</th><th>Top strength</th><th>Coaching note</th></tr></thead>
    <tbody>
{rep_html}    </tbody>
  </table></div></div>

  <h2>Skipped calls <span class="sub">pulled by the roster query but not sales calls</span></h2>
  <div class="panel"><div class="scroller"><table>
    <thead><tr><th>Rep</th><th>Length</th><th>Why skipped</th></tr></thead>
    <tbody>
{skip_html}    </tbody>
  </table></div></div>

  <h2>All-time pattern totals</h2>
  <div class="cards">
    <div class="card">
      <div class="label">Calls graded, all time</div>
      <div class="value">{pat['total_calls_graded']}</div>
      <div class="note">+{len(scored)} this run</div>
    </div>
    <div class="card">
      <div class="label">Cumulative average</div>
      <div class="value {band(cum_avg)}">{cum_avg:.1f}</div>
      <div class="note">across all runs</div>
    </div>
    <div class="card">
      <div class="label">Last 3 runs</div>
      <div class="value {band(last3_avg)}">{last3_avg:.1f}</div>
      <div class="note">{', '.join(last3)}</div>
    </div>
    <div class="card">
      <div class="label">Runs completed</div>
      <div class="value">{len(all_dates)}</div>
      <div class="note">since 2026-06-05</div>
    </div>
  </div>

  <footer>
    Generated {RUN_DATE} by Gary (AI Chief of Staff) &middot; rubric: <code>config/rubric.md</code> (85 pts, mastery 77+)
    &middot; grades: <code>output/weekly/grades/{RUN_DATE}/</code> &middot; patterns: <code>output/patterns.json</code><br>
    Phone-presence scores are assessed from transcript language only, not vocal tone &mdash; flagged calls need an audio listen before they are used in a coaching conversation.
  </footer>
</div>
</body>
</html>
"""

with open(REPORT, "w") as f:
    f.write(HTML)

print(f"Report:   {REPORT}")
print(f"Patterns: {PATTERNS} -> {pat['total_calls_graded']} calls, cum avg {cum_avg:.1f}, last3 {last3_avg:.1f}")
print(f"Full sales avg this run: {full_avg:.1f} (prior cumulative {prior_cum_avg:.1f}, delta {trend_delta:+.1f})")
print(f"Top: {top_rep} {full_avgs[top_rep]:.1f} | Coaching: {bottom_rep} {full_avgs[bottom_rep]:.1f}")
print(f"Weakest section: {sec_sorted[0][0]} at {sec_sorted[0][3]:.0f}%")
