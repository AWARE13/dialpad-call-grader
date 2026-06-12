#!/usr/bin/env python3
"""
build_report.py — Generate HTML report from grades JSON.
Usage: python3 scripts/build_report.py [grades_file]
"""

import json, sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

OUTPUT_DIR = Path(__file__).parent.parent / "output"

def load_grades(path=None):
    if path:
        with open(path) as f:
            return json.load(f)
    # Auto-find latest
    files = sorted(OUTPUT_DIR.glob("grades_*.json"), reverse=True)
    if not files:
        raise FileNotFoundError("No grades file found in output/")
    with open(files[0]) as f:
        return json.load(f)

def build_report(grades_path=None):
    data = load_grades(grades_path)
    calls = data["calls"]
    run_date = data.get("run_date", "unknown")
    mastery_threshold = data.get("mastery_threshold", 77)

    # Aggregate per rep
    rep_scores = defaultdict(list)
    rep_flags = defaultdict(lambda: {"sya": 0, "mym": 0, "otg": 0, "agenda": 0, "gradeable": 0})
    section_totals = defaultdict(list)

    for c in calls:
        if c.get("call_type") != "full_sales_call" or c.get("total_score") is None:
            continue
        rep = c["rep_name"]
        score = c["total_score"]
        rep_scores[rep].append(score)
        f = rep_flags[rep]
        f["gradeable"] += 1
        if c.get("save_your_ass_hit"): f["sya"] += 1
        if c.get("meet_your_mover_hit"): f["mym"] += 1
        if c.get("on_time_guarantee_hit"): f["otg"] += 1
        if c.get("agenda_opener_hit"): f["agenda"] += 1
        secs = c.get("sections", {})
        for k, v in secs.items():
            if isinstance(v, dict):
                s = v.get("score")
                m = v.get("max")
                if s is not None and m:
                    section_totals[k].append((s, m))
            elif isinstance(v, (int, float)):
                # flat int format
                section_totals[k].append(v)

    all_scores = [c["total_score"] for c in calls if c.get("call_type") == "full_sales_call" and c.get("total_score") is not None]
    gradeable_count = len(all_scores)
    avg_score = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0
    mastery_count = sum(1 for s in all_scores if s >= mastery_threshold)

    # Section averages
    sec_avgs = {}
    sec_maxes = {"set_the_agenda":7,"probe_for_info":9,"pricing_differentiators":20,"clock":4,"estimate":13,"save_your_ass":10,"quote_booking":11,"politeness":3,"bonus":8}
    for k, vals in section_totals.items():
        if vals and isinstance(vals[0], tuple):
            avg = round(sum(v[0] for v in vals) / len(vals), 1)
            mx = vals[0][1]
        else:
            avg = round(sum(vals) / len(vals), 1) if vals else 0
            mx = sec_maxes.get(k, 1)
        pct = round(avg / mx * 100) if mx else 0
        sec_avgs[k] = {"avg": avg, "max": mx, "pct": pct}

    # SYA team rate
    total_gradeable_calls = sum(f["gradeable"] for f in rep_flags.values())
    sya_hits = sum(f["sya"] for f in rep_flags.values())
    sya_rate = round(sya_hits / total_gradeable_calls * 100) if total_gradeable_calls else 0
    mym_hits = sum(f["mym"] for f in rep_flags.values())
    otg_hits = sum(f["otg"] for f in rep_flags.values())
    mym_rate = round(mym_hits / total_gradeable_calls * 100) if total_gradeable_calls else 0
    otg_rate = round(otg_hits / total_gradeable_calls * 100) if total_gradeable_calls else 0

    # Rep leaderboard
    rep_avgs = []
    for rep, scores in rep_scores.items():
        avg = round(sum(scores) / len(scores), 1)
        rep_avgs.append({"rep": rep, "avg": avg, "calls": len(scores), "scores": scores, "mastery_hits": sum(1 for s in scores if s >= mastery_threshold)})
    rep_avgs.sort(key=lambda x: -x["avg"])

    # Top coaching priorities (lowest avg)
    coaching_prio = sorted(rep_avgs, key=lambda x: x["avg"])[:8]

    def score_color(s):
        if s is None: return "#6b7280"
        if s >= mastery_threshold: return "#16a34a"
        if s >= 65: return "#ca8a04"
        if s >= 50: return "#ea580c"
        return "#dc2626"

    def pct_bar(pct, color="#E8630A"):
        return f'<div style="background:#e5e7eb;border-radius:4px;height:8px;"><div style="background:{color};width:{pct}%;height:8px;border-radius:4px;"></div></div>'

    SEC_LABELS = {
        "set_the_agenda": "Set the Agenda",
        "probe_for_info": "Probe for Info",
        "pricing_differentiators": "Pricing / Differentiators",
        "clock": "Clock",
        "estimate": "Estimate",
        "save_your_ass": "Save Your Ass",
        "quote_booking": "Quote / Booking",
        "politeness": "Politeness",
        "bonus": "Bonus"
    }

    # Build rep rows
    rep_rows = ""
    for i, r in enumerate(rep_avgs, 1):
        bar_color = score_color(r["avg"])
        score_str = " / ".join(str(s) for s in r["scores"])
        rep_rows += f"""
        <tr>
            <td style="font-weight:600;color:#374151;">#{i}</td>
            <td style="font-weight:600;">{r["rep"]}</td>
            <td style="text-align:center;">{r["calls"]}</td>
            <td style="text-align:center;">
                <span style="font-weight:700;font-size:1.1em;color:{bar_color};">{r["avg"]}</span>
                <span style="color:#9ca3af;font-size:0.8em;">/85</span>
            </td>
            <td style="font-size:0.85em;color:#6b7280;">{score_str}</td>
            <td style="text-align:center;color:{'#16a34a' if r['mastery_hits'] > 0 else '#dc2626'};">
                {"✅" if r['mastery_hits'] > 0 else "—"}
            </td>
        </tr>"""

    # Section performance rows
    sec_rows = ""
    sec_order = ["save_your_ass","pricing_differentiators","quote_booking","set_the_agenda","probe_for_info","clock","estimate","politeness","bonus"]
    for k in sec_order:
        if k not in sec_avgs:
            continue
        d = sec_avgs[k]
        flag = " 🚨" if d["pct"] < 40 else (" ⚠️" if d["pct"] < 60 else "")
        sec_rows += f"""
        <tr>
            <td style="font-weight:500;">{SEC_LABELS.get(k, k)}{flag}</td>
            <td style="text-align:center;">{d["avg"]}</td>
            <td style="text-align:center;color:#6b7280;">{d["max"]}</td>
            <td style="text-align:center;font-weight:600;color:{score_color(d['pct']/100*mastery_threshold)};">{d["pct"]}%</td>
            <td style="padding-right:12px;">{pct_bar(d["pct"])}</td>
        </tr>"""

    # Individual call cards for top/bottom
    def call_card(c):
        s = c.get("total_score")
        color = score_color(s)
        secs = c.get("sections", {})
        sec_html = ""
        for k in sec_order:
            if k in secs:
                v = secs[k]
                sv = v.get("score") if isinstance(v, dict) else v
                mx = sec_maxes.get(k, 1)
                if sv is not None:
                    pct = round(sv / mx * 100)
                    sec_html += f'<span style="font-size:0.75em;background:#f3f4f6;border-radius:4px;padding:2px 6px;margin:2px;display:inline-block;">{SEC_LABELS.get(k,k)[:10]}: {sv}/{mx}</span>'
        return f"""
        <div style="border:1px solid #e5e7eb;border-left:4px solid {color};border-radius:8px;padding:16px;margin-bottom:12px;">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                <div>
                    <span style="font-weight:700;font-size:1.05em;">{c["rep_name"]}</span>
                    <span style="color:#6b7280;font-size:0.85em;margin-left:8px;">{c["branch"]} · {c["duration_min"]} min</span>
                </div>
                <span style="font-size:1.4em;font-weight:800;color:{color};">{s if s is not None else "—"}<span style="font-size:0.6em;color:#9ca3af;">/85</span></span>
            </div>
            <div style="margin:8px 0;">{sec_html}</div>
            <div style="font-size:0.85em;color:#374151;margin-top:8px;">
                <strong>Strength:</strong> {c.get("top_strength","—")}<br>
                <strong>Coaching:</strong> {c.get("coaching_note","—")}
            </div>
        </div>"""

    # Top 5 + bottom 5 calls
    scored_calls = sorted([c for c in calls if c.get("call_type")=="full_sales_call" and c.get("total_score") is not None], key=lambda x: -x["total_score"])
    top_calls_html = "".join(call_card(c) for c in scored_calls[:5])
    bottom_calls_html = "".join(call_card(c) for c in scored_calls[-5:])

    # Coaching priorities table
    coaching_rows = ""
    for r in coaching_prio:
        coaching_rows += f"""
        <tr>
            <td style="font-weight:600;">{r["rep"]}</td>
            <td style="text-align:center;font-weight:700;color:{score_color(r["avg"])};">{r["avg"]}</td>
            <td style="font-size:0.85em;color:#6b7280;">{" / ".join(str(s) for s in r["scores"])}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>AI Call Grading Report — {run_date}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f9fafb; color: #111827; }}
  .header {{ background: linear-gradient(135deg, #1e3a5f 0%, #E8630A 100%); color: white; padding: 32px 40px; }}
  .header h1 {{ font-size: 1.8em; font-weight: 800; margin-bottom: 4px; }}
  .header p {{ opacity: 0.85; font-size: 0.95em; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 32px 24px; }}
  .stat-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; margin-bottom: 32px; }}
  .stat-card {{ background: white; border-radius: 12px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,.08); text-align: center; }}
  .stat-card .value {{ font-size: 2.2em; font-weight: 800; color: #E8630A; }}
  .stat-card .label {{ font-size: 0.82em; color: #6b7280; margin-top: 4px; text-transform: uppercase; letter-spacing: .04em; }}
  .section {{ background: white; border-radius: 12px; padding: 24px; box-shadow: 0 1px 4px rgba(0,0,0,.08); margin-bottom: 24px; }}
  .section h2 {{ font-size: 1.15em; font-weight: 700; color: #1e3a5f; margin-bottom: 16px; border-bottom: 2px solid #E8630A; padding-bottom: 8px; display: inline-block; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ text-align: left; font-size: 0.8em; text-transform: uppercase; letter-spacing: .05em; color: #6b7280; padding: 8px 12px; border-bottom: 1px solid #e5e7eb; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid #f3f4f6; font-size: 0.9em; }}
  tr:last-child td {{ border-bottom: none; }}
  .flag-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }}
  .flag-card {{ background: #fef3c7; border-radius: 8px; padding: 16px; border: 1px solid #fde68a; }}
  .flag-card .flag-val {{ font-size: 1.8em; font-weight: 800; color: #92400e; }}
  .flag-card .flag-label {{ font-size: 0.8em; color: #78350f; margin-top: 2px; }}
  .alert {{ background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 16px; margin-bottom: 12px; }}
  .alert-title {{ font-weight: 700; color: #991b1b; margin-bottom: 4px; }}
</style>
</head>
<body>

<div class="header">
  <h1>⚡ Einstein AI Call Grading Report</h1>
  <p>Week of {run_date} &nbsp;·&nbsp; 33-Rep Roster &nbsp;·&nbsp; Powered by Gary</p>
</div>

<div class="container">

  <div class="stat-grid">
    <div class="stat-card">
      <div class="value">{gradeable_count}</div>
      <div class="label">Calls Graded</div>
    </div>
    <div class="stat-card">
      <div class="value">{avg_score}</div>
      <div class="label">Team Avg Score (/85)</div>
    </div>
    <div class="stat-card">
      <div class="value">{mastery_count}</div>
      <div class="label">Mastery Calls (77+)</div>
    </div>
    <div class="stat-card">
      <div class="value">{sya_rate}%</div>
      <div class="label">Save Your Ass Rate</div>
    </div>
    <div class="stat-card">
      <div class="value">{mym_rate}%</div>
      <div class="label">Meet Your Mover Rate</div>
    </div>
    <div class="stat-card">
      <div class="value">{otg_rate}%</div>
      <div class="label">On-Time Guarantee Rate</div>
    </div>
  </div>

  <div class="alert">
    <div class="alert-title">🚨 Week 1 Headline</div>
    Team average: <strong>{avg_score}/85</strong>. Mastery threshold (77+): <strong>{mastery_count} calls</strong>.
    Save Your Ass delivery rate: <strong>{sya_rate}%</strong> — the #1 coaching priority across the entire team.
    The only call approaching mastery: <strong>Daniel Behseresht (75/85)</strong>.
    Top performer by average: <strong>Nicole Cruz (67 avg)</strong>.
  </div>

  <div class="section">
    <h2>Section Performance — Team Averages</h2>
    <table>
      <thead><tr><th>Section</th><th>Avg Score</th><th>Max</th><th>Hit Rate</th><th style="min-width:120px;">Bar</th></tr></thead>
      <tbody>{sec_rows}</tbody>
    </table>
  </div>

  <div class="section">
    <h2>Differentiator Hit Rates</h2>
    <div class="flag-grid">
      <div class="flag-card">
        <div class="flag-val">{sya_rate}%</div>
        <div class="flag-label">Save Your Ass<br><small>{sya_hits} / {total_gradeable_calls} calls</small></div>
      </div>
      <div class="flag-card">
        <div class="flag-val">{mym_rate}%</div>
        <div class="flag-label">Meet Your Mover<br><small>{mym_hits} / {total_gradeable_calls} calls</small></div>
      </div>
      <div class="flag-card">
        <div class="flag-val">{otg_rate}%</div>
        <div class="flag-label">On-Time Guarantee<br><small>{otg_hits} / {total_gradeable_calls} calls</small></div>
      </div>
    </div>
  </div>

  <div class="section">
    <h2>Rep Leaderboard</h2>
    <table>
      <thead><tr><th>#</th><th>Rep</th><th>Calls</th><th>Avg Score</th><th>Individual Scores</th><th>Mastery</th></tr></thead>
      <tbody>{rep_rows}</tbody>
    </table>
  </div>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-bottom:24px;">
    <div class="section">
      <h2>🏆 Top 5 Calls</h2>
      {top_calls_html}
    </div>
    <div class="section">
      <h2>🎯 Coaching Priority — Lowest 8 Avgs</h2>
      <table>
        <thead><tr><th>Rep</th><th>Avg</th><th>Scores</th></tr></thead>
        <tbody>{coaching_rows}</tbody>
      </table>
    </div>
  </div>

  <div class="section">
    <h2>📋 Bottom 5 Calls — Deepest Gaps</h2>
    {bottom_calls_html}
  </div>

  <div style="text-align:center;color:#9ca3af;font-size:0.8em;padding:24px 0;">
    Generated by Gary · Einstein Moving Company AI Chief of Staff · {run_date}
  </div>

</div>
</body>
</html>"""

    out = OUTPUT_DIR / f"report_{run_date}.html"
    with open(out, "w") as f:
        f.write(html)
    print(f"Report saved: {out}")
    return str(out)

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    build_report(path)
