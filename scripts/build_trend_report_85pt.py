#!/usr/bin/env python3
"""
build_trend_report_85pt.py — Builds a standalone run-over-run trend page for
the company-wide 85-pt Sales Call Scorecard, sourced directly from
output/patterns.json (scores[] with date/rep/branch/score/type).

Unlike the per-run snapshot reports (a new file every run), this page is
persistent — rerun this script after each weekly grading run and it
overwrites the same file. Mirrors the CET v2 trend report
(build_trend_report.py / cet_trend_report.html) but for the 85-pt rubric,
its 65/75 Green/Super Green bars, and its full_sales vs walkthrough_scheduler
type split (headline average excludes walkthroughs — see
config/rubric.md and cos-amanda/memory/reference_call_grading_state.md).

Usage:
    python3 scripts/build_trend_report_85pt.py
"""
import json, html, statistics
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).parent.parent
PATTERNS_PATH = BASE / "output" / "patterns.json"
OUT_PATH = BASE / "output" / "weekly" / "trend_report_85pt.html"

GREEN, BLUE, ORANGE, RED, GRAY = "#639922", "#185fa5", "#E8630A", "#a32d2d", "#888"
NAVY = "#1a2744"
GREEN_BAR, SUPER_GREEN_BAR = 65, 75

def esc(x):
    return html.escape(str(x)) if x is not None else ""

def cell_color(score):
    if score is None:
        return GRAY
    if score >= SUPER_GREEN_BAR:
        return GREEN
    if score >= GREEN_BAR:
        return "#8fae1f"
    if score >= 55:
        return ORANGE
    return RED

def delta_html(delta):
    if delta is None:
        return f'<span style="color:{GRAY};">&mdash;</span>'
    if delta > 0.05:
        return f'<span style="color:{GREEN};font-weight:700;">&#9650; +{delta:.1f}</span>'
    if delta < -0.05:
        return f'<span style="color:{RED};font-weight:700;">&#9660; {delta:.1f}</span>'
    return f'<span style="color:{GRAY};">&#9679; +0.0</span>'

def build():
    patterns = json.load(open(PATTERNS_PATH))
    scores = patterns["scores"]

    by_date = defaultdict(list)
    for s in scores:
        by_date[s["date"]].append(s)
    dates = sorted(by_date)

    # Company average per run — headline methodology: exclude walkthrough_scheduler only
    # (both "full_sales" and "full_sales_call" type labels count; naming drifted 6/05-8/31).
    company_avg_by_date = {}
    n_graded_by_date = {}
    for d in dates:
        full = [r["score"] for r in by_date[d] if r.get("type") != "walkthrough_scheduler"]
        company_avg_by_date[d] = round(statistics.mean(full), 1) if full else None
        n_graded_by_date[d] = len(full)

    # Per-rep scores per run (average if a rep had 2 calls that run), full-sales only
    rep_by_date = defaultdict(dict)
    for d in dates:
        per_rep = defaultdict(list)
        for r in by_date[d]:
            if r.get("type") == "walkthrough_scheduler":
                continue
            per_rep[r["rep"]].append(r["score"])
        for rep, vals in per_rep.items():
            rep_by_date[rep][d] = round(statistics.mean(vals), 1)

    rows = []
    for rep, by_d in rep_by_date.items():
        run_scores = [by_d.get(d) for d in dates]
        available = [(d, s) for d, s in zip(dates, run_scores) if s is not None]
        latest_delta = round(available[-1][1] - available[-2][1], 1) if len(available) >= 2 else None
        rows.append((rep, run_scores, latest_delta))

    def sort_key(r):
        rep, run_scores, delta = r
        latest = next((s for s in reversed(run_scores) if s is not None), None)
        return (latest is None, -(latest or 0))
    rows.sort(key=sort_key)

    header_cells = "".join(
        f'<th style="padding:10px;text-align:center;font-weight:600;white-space:nowrap;">{esc(d)}</th>' for d in dates
    )
    company_row = "".join(
        f'<td style="text-align:center;padding:10px;color:{cell_color(company_avg_by_date[d])};">{company_avg_by_date[d] if company_avg_by_date[d] is not None else "&mdash;"}</td>'
        for d in dates
    )
    n_row = "".join(
        f'<td style="text-align:center;padding:6px;color:#999;font-size:12px;">n={n_graded_by_date[d]}</td>' for d in dates
    )

    rep_rows_html = ""
    for rep, run_scores, delta in rows:
        cells = "".join(
            f'<td style="text-align:center;padding:10px;color:{cell_color(s)};font-weight:{"700" if s is not None and s >= GREEN_BAR else "400"};">{s if s is not None else "&mdash;"}</td>'
            for s in run_scores
        )
        rep_rows_html += f"""
        <tr style="border-bottom:1px solid #e5e5e5;">
          <td style="padding:10px;font-weight:600;white-space:nowrap;">{esc(rep)}</td>
          {cells}
          <td style="text-align:center;padding:10px;">{delta_html(delta)}</td>
        </tr>"""

    n_runs = len(dates)
    trend_note = ""
    if n_runs >= 2:
        latest_avg = company_avg_by_date[dates[-1]]
        prev_avg = company_avg_by_date[dates[-2]]
        company_delta = round(latest_avg - prev_avg, 1)
        direction = "up" if company_delta > 0 else ("down" if company_delta < 0 else "flat")
        trend_note = f'<p style="font-size:15px;color:#444;">Company average moved <strong>{direction}</strong> {abs(company_delta)} points run over run ({prev_avg} &rarr; {latest_avg}), against a Green bar of {GREEN_BAR} and Super Green of {SUPER_GREEN_BAR}.</p>'

    all_full = [s["score"] for s in scores if s.get("type") != "walkthrough_scheduler"]
    cumulative_avg = round(statistics.mean(all_full), 1) if all_full else None
    mastery_count = sum(1 for s in all_full if s >= 77)
    green_count = sum(1 for s in all_full if s >= GREEN_BAR)

    out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Sales Call Grading — Trend (85-pt)</title>
<meta name="robots" content="noindex, nofollow">
<style>
  body {{ font-family: Arial, Helvetica, sans-serif; margin: 0; background: #f4f4f4; color: #222; }}
  .header {{ background: {NAVY}; color: white; padding: 32px 40px; }}
  .header h1 {{ margin: 0 0 6px 0; font-size: 28px; }}
  .header p {{ margin: 0; opacity: 0.85; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 30px 40px 60px; overflow-x: auto; }}
  table {{ border-collapse: collapse; background: white; box-shadow: 0 1px 4px rgba(0,0,0,0.08); min-width: 100%; }}
  th {{ background: {NAVY}; color: white; }}
  .company-table td {{ font-size: 20px; font-weight: 700; }}
  .legend {{ font-size: 13px; color: #666; margin-top: 8px; }}
  .stat-row {{ display:flex; gap:24px; margin: 18px 0 28px; flex-wrap: wrap; }}
  .stat {{ background:white; border-radius:8px; padding:14px 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); min-width:160px; }}
  .stat .num {{ font-size: 26px; font-weight: 700; color: {ORANGE}; }}
  .stat .label {{ font-size: 12px; color: #666; text-transform: uppercase; letter-spacing: 0.03em; }}
</style>
</head>
<body>
  <div class="header">
    <h1>Sales Call Grading &mdash; Run-over-Run Trend</h1>
    <p>Einstein 85-pt Sales Call Scorecard &middot; {n_runs} run{'s' if n_runs != 1 else ''} tracked &middot; last updated {esc(dates[-1])}</p>
  </div>
  <div class="container">
    <div class="stat-row">
      <div class="stat"><div class="num">{cumulative_avg}</div><div class="label">Cumulative avg / 85</div></div>
      <div class="stat"><div class="num">{len(all_full)}</div><div class="label">Full sales calls graded</div></div>
      <div class="stat"><div class="num">{green_count}</div><div class="label">Calls &ge; {GREEN_BAR} (Green)</div></div>
      <div class="stat"><div class="num">{mastery_count}</div><div class="label">Calls &ge; 77 (Mastery)</div></div>
    </div>

    <h2 style="color:{NAVY};">Company Average</h2>
    {trend_note}
    <table class="company-table">
      <tr>{header_cells}</tr>
      <tr>{company_row}</tr>
      <tr>{n_row}</tr>
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
    <p class="legend">&#9650; improved &nbsp;&#9660; declined &nbsp;&#9679; flat/no change &nbsp;&mdash; no gradeable call that run. Bold = cleared the {GREEN_BAR}-pt Green bar. "Latest Change" compares each rep's two most recent runs with data, which may not be consecutive weeks. Walkthrough-scheduler calls are excluded (rubric mismatch, mini-rubric still pending).</p>
  </div>
</body>
</html>"""

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        f.write(out)
    print(f"Written: {OUT_PATH} ({len(out)//1024} KB)")
    print(f"Runs tracked: {n_runs} | Cumulative avg: {cumulative_avg} | Reps tracked: {len(rows)}")

if __name__ == "__main__":
    build()
