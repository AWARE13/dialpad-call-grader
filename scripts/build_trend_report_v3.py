#!/usr/bin/env python3
"""
build_trend_report_v3.py — Builds a standalone week-over-week trend page from
output/patterns_v3_history.json. Unlike the per-week snapshot reports (which get
a new file every week), this page is persistent — rerun this script each week
after patterns_v3_history.json is updated, and it overwrites the same file.

This is a fresh v3 baseline, separate from the v2 trend page (cet_trend_report.html,
still built by build_trend_report.py from patterns_v2_history.json) — the two rubrics'
scores aren't comparable, so their trend lines are kept in separate files rather than
one page silently splicing incompatible numbers together.

Usage:
    python3 scripts/build_trend_report_v3.py
"""
import json, html
from pathlib import Path

BASE = Path(__file__).parent.parent
HISTORY_PATH = BASE / "output" / "patterns_v3_history.json"
OUT_PATH = BASE / "output" / "weekly" / "cet_trend_report_v3.html"

GREEN, BLUE, ORANGE, RED = "#639922", "#185fa5", "#E8630A", "#a32d2d"
NAVY = "#1a2744"

def esc(x):
    return html.escape(str(x)) if x is not None else ""

def fmt_week(w):
    return f"{w['week_start']} to {w['week_end']}"

def delta_html(delta):
    if delta is None:
        return '<span style="color:#888;">—</span>'
    if delta > 0:
        return f'<span style="color:{GREEN};font-weight:700;">&#9650; +{delta:.1f}</span>'
    if delta < 0:
        return f'<span style="color:{RED};font-weight:700;">&#9660; {delta:.1f}</span>'
    return f'<span style="color:#888;">&#9679; +0.0</span>'

def build():
    history = json.load(open(HISTORY_PATH))
    weeks = history["company_avg_by_week"]
    per_rep_trend = history["per_rep_trend"]

    week_labels = [fmt_week(w) for w in weeks]
    week_keys = [(w["week_start"], w["week_end"]) for w in weeks]

    # Build per-rep rows: score per week + week-over-week deltas
    rows = []
    for rep, wlist in per_rep_trend.items():
        by_week = {(w["week_start"], w["week_end"]): w["avg_score"] for w in wlist}
        scores = [by_week.get(k) for k in week_keys]
        last_two = [s for s in scores if s is not None][-2:]
        latest_delta = round(last_two[-1] - last_two[0], 1) if len(last_two) == 2 else None
        rows.append((rep, scores, latest_delta))

    # Sort by most recent available score, descending; reps with no recent data go last
    def sort_key(r):
        rep, scores, delta = r
        latest = next((s for s in reversed(scores) if s is not None), None)
        return (latest is None, -(latest or 0))
    rows.sort(key=sort_key)

    company_row = "".join(
        f'<td style="text-align:center;padding:10px;">{w["avg"]}</td>' for w in weeks
    )
    header_cells = "".join(
        f'<th style="padding:10px;text-align:center;font-weight:600;">{esc(lbl)}</th>' for lbl in week_labels
    )

    rep_rows_html = ""
    for rep, scores, delta in rows:
        cells = "".join(
            f'<td style="text-align:center;padding:10px;">{s if s is not None else "—"}</td>'
            for s in scores
        )
        rep_rows_html += f"""
        <tr style="border-bottom:1px solid #e5e5e5;">
          <td style="padding:10px;font-weight:600;">{esc(rep)}</td>
          {cells}
          <td style="text-align:center;padding:10px;">{delta_html(delta)}</td>
        </tr>"""

    n_weeks = len(weeks)
    trend_note = ""
    if n_weeks >= 2:
        latest_avg = weeks[-1]["avg"]
        prev_avg = weeks[-2]["avg"]
        company_delta = round(latest_avg - prev_avg, 1)
        direction = "up" if company_delta > 0 else ("down" if company_delta < 0 else "flat")
        trend_note = f'<p style="font-size:15px;color:#444;">Company average moved <strong>{direction}</strong> {abs(company_delta)} points week over week ({prev_avg} &rarr; {latest_avg}).</p>'

    out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>CET Call Grading — Trend (v3)</title>
<meta name="robots" content="noindex, nofollow">
<style>
  body {{ font-family: Arial, Helvetica, sans-serif; margin: 0; background: #f4f4f4; color: #222; }}
  .header {{ background: {NAVY}; color: white; padding: 32px 40px; }}
  .header h1 {{ margin: 0 0 6px 0; font-size: 28px; }}
  .header p {{ margin: 0; opacity: 0.85; }}
  .container {{ max-width: 1100px; margin: 0 auto; padding: 30px 40px 60px; }}
  table {{ width: 100%; border-collapse: collapse; background: white; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
  th {{ background: {NAVY}; color: white; }}
  .company-table td {{ font-size: 20px; font-weight: 700; color: {ORANGE}; }}
  .legend {{ font-size: 13px; color: #666; margin-top: 8px; }}
</style>
</head>
<body>
  <div class="header">
    <h1>CET Call Grading — Week-over-Week Trend (v3)</h1>
    <p>Section Map rubric (v3, 100 pts, graded directly against the 15-Minute Quote Call script) &middot; {n_weeks} week{'s' if n_weeks != 1 else ''} tracked</p>
  </div>
  <div class="container">
    <h2 style="color:{NAVY};">Company Average</h2>
    {trend_note}
    <table class="company-table">
      <tr>{header_cells}</tr>
      <tr>{company_row}</tr>
    </table>

    <h2 style="color:{NAVY};margin-top:40px;">Per-Rep Progression</h2>
    <table>
      <tr>
        <th style="padding:10px;text-align:left;">Rep</th>
        {header_cells}
        <th style="padding:10px;">Latest Change</th>
      </tr>
      {rep_rows_html}
    </table>
    <p class="legend">&#9650; improved &nbsp;&#9660; declined &nbsp;&#9679; flat/no change &nbsp;— no calls graded that week. "Latest Change" compares the two most recent weeks each rep has data for.</p>
  </div>
</body>
</html>"""

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        f.write(out)
    print(f"Written: {OUT_PATH} ({len(out)//1024} KB)")

if __name__ == "__main__":
    build()
