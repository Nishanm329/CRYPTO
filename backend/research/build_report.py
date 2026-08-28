"""Builds the final HTML report: registry table, champion equity curve
(VALIDATE+HOLDOUT only), Monte Carlo distribution, verdict, lessons list."""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import load_split_config, run_variant_pooled

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(OUT_DIR, "champion.json")) as f:
    champion = json.load(f)
with open(os.path.join(OUT_DIR, "holdout_result.json")) as f:
    holdout_result = json.load(f)

registry_rows = []
with open(os.path.join(OUT_DIR, "registry.csv")) as f:
    reader = csv.DictReader(f)
    registry_rows = list(reader)


def svg_equity_curve(trades_validate, trades_holdout, width=760, height=280):
    all_trades = sorted(trades_validate + trades_holdout, key=lambda t: t["entry_time"])
    r_values = [t["r_multiple"] for t in all_trades]
    equity = []
    running = 0.0
    for r in r_values:
        running += r
        equity.append(running)
    if not equity:
        return "<p>No trades.</p>"

    split_point = len(trades_validate)  # index where holdout begins
    n = len(equity)
    min_e, max_e = min(0, min(equity)), max(equity)
    pad = (max_e - min_e) * 0.1 or 1
    min_e -= pad
    max_e += pad

    def x(i):
        return 40 + (i / max(n - 1, 1)) * (width - 60)

    def y(v):
        return height - 30 - ((v - min_e) / (max_e - min_e)) * (height - 60)

    points_validate = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(equity[:split_point]))
    points_holdout = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(equity) if i >= split_point - 1)

    zero_y = y(0)
    split_x = x(split_point - 1) if split_point > 0 else 40

    return f"""
    <svg width="{width}" height="{height}" style="background:#111;border-radius:8px">
      <line x1="40" y1="{zero_y:.1f}" x2="{width-20}" y2="{zero_y:.1f}" stroke="#444" stroke-dasharray="4,4"/>
      <line x1="{split_x:.1f}" y1="20" x2="{split_x:.1f}" y2="{height-20}" stroke="#f59e0b" stroke-dasharray="4,4"/>
      <text x="{split_x+4:.1f}" y="18" fill="#f59e0b" font-size="11">HOLDOUT starts</text>
      <polyline points="{points_validate}" fill="none" stroke="#3b82f6" stroke-width="2"/>
      <polyline points="{points_holdout}" fill="none" stroke="#ef4444" stroke-width="2"/>
      <text x="40" y="{height-6}" fill="#999" font-size="11">trade #0</text>
      <text x="{width-90}" y="{height-6}" fill="#999" font-size="11">trade #{n}</text>
    </svg>
    <div style="color:#999;font-size:12px;margin-top:4px">
      <span style="color:#3b82f6">■</span> VALIDATE &nbsp; <span style="color:#ef4444">■</span> HOLDOUT — cumulative R
    </div>
    """


split_config = load_split_config()
full_result = run_variant_pooled(champion["params"], split_config)
equity_svg = svg_equity_curve(full_result["trades_validate_raw"], full_result["trades_holdout_raw"])

registry_html_rows = "\n".join(
    f"<tr class=\"{'bug' if r['verdict']=='BUG_SUSPECT_EXCLUDED' else 'champ' if r['variant_id']==champion['variant_id'] else ''}\">"
    f"<td>{r['iteration']}</td><td>{r['variant_id']}</td>"
    f"<td>{r['train_expectancy']}</td><td>{r['validate_expectancy']}</td>"
    f"<td>{r['PF']}</td><td>{r['maxDD']}</td><td>{r['sharpe']}</td><td>{r['trades']}</td>"
    f"<td>{r['verdict']}</td></tr>"
    for r in registry_rows
)

mc = holdout_result["monte_carlo_validate_plus_holdout"]
verdict = holdout_result["verdict"]
verdict_color = {"EDGE PLAUSIBLE": "#22c55e", "INCONCLUSIVE": "#f59e0b", "NO EDGE": "#ef4444"}[verdict]

lessons = [
    "Naive in-sample \"best combo per symbol\" selection (the legacy combination_backtester's own ranking) is symbol-inconsistent and overfits on small samples — a combo that wins on BTCUSDT can be the worst performer on ETHUSDT.",
    "Any backtest result with Sharpe>3 or win rate>75% should be treated as a bug/lookahead suspect by default, not celebrated — this was reproduced empirically before the formal loop even started (full_confluence: 75-100% win rate on n=1-4 trades).",
    "Entry price matters: the legacy engine's same-bar-close entry is a lookahead simplification; this loop fixed it to next-candle-open execution.",
    f"Volume confirmation (>1.1x 20-period average) was the single strongest filter found on VALIDATE ({champion['validate_expectancy']}R expectancy, PF {full_result['validate']['profit_factor']}), beating ADX-trend, HTF-EMA200, RSI, wider stops, and the slower EMA7/99 baseline.",
    f"The champion's edge shrank substantially from VALIDATE to HOLDOUT (expectancy {full_result['validate']['expectancy']}R → {full_result['holdout']['expectancy']}R, ratio {holdout_result['ratio_holdout_to_validate']}), which is exactly what multiple-testing correction predicts can happen even to a legitimately-selected best-of-N candidate — this is why the verdict is INCONCLUSIVE rather than a promotion to live trading.",
    "Costs (0.30% round trip) plus realistic next-open execution meaningfully compress edges that look attractive on a lookahead-biased same-close backtest — several filters (ADX, RSI) that seemed promising in ad-hoc pre-checks did not hold up under this stricter methodology.",
]

html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Strategy Research Report</title>
<style>
body {{ background:#0a0a0a; color:#e5e5e5; font-family:-apple-system,Segoe UI,Roboto,sans-serif; max-width:900px; margin:40px auto; padding:0 20px; line-height:1.5; }}
h1,h2 {{ color:#fff; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; margin:16px 0; }}
th,td {{ padding:6px 8px; border-bottom:1px solid #2a2a2a; text-align:right; }}
th:nth-child(2), td:nth-child(2) {{ text-align:left; }}
th {{ color:#999; font-weight:600; }}
tr.champ {{ background:#0f2a1a; }}
tr.bug {{ background:#2a0f0f; color:#f88; }}
.verdict {{ font-size:28px; font-weight:800; color:{verdict_color}; padding:16px; border:2px solid {verdict_color}; border-radius:12px; display:inline-block; }}
.card {{ background:#141414; border-radius:12px; padding:20px; margin:16px 0; }}
.grid {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; }}
.stat {{ background:#1a1a1a; border-radius:8px; padding:12px; }}
.stat .v {{ font-size:20px; font-weight:700; }}
.stat .l {{ font-size:11px; color:#999; }}
ul {{ padding-left:20px; }}
li {{ margin-bottom:8px; }}
code {{ background:#1a1a1a; padding:1px 5px; border-radius:4px; }}
</style></head>
<body>
<h1>Strategy Research Report</h1>
<p style="color:#999">EMA-cross signal research loop — TRAIN/VALIDATE/HOLDOUT discipline, next-open execution, realistic costs.
Basket: BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT, ADAUSDT · Timeframe: 4h</p>

<div class="verdict">{verdict}</div>
<p>{holdout_result['recommendation']}</p>

<div class="card">
<h2>Champion: {champion['variant_id']}</h2>
<p><code>{json.dumps(champion['params'])}</code></p>
<div class="grid">
  <div class="stat"><div class="v">{full_result['validate']['expectancy']}R</div><div class="l">VALIDATE expectancy</div></div>
  <div class="stat"><div class="v">{full_result['holdout']['expectancy']}R</div><div class="l">HOLDOUT expectancy</div></div>
  <div class="stat"><div class="v">{holdout_result['ratio_holdout_to_validate']}</div><div class="l">Holdout/Validate ratio</div></div>
  <div class="stat"><div class="v">{full_result['validate']['win_rate']}%</div><div class="l">VALIDATE win rate</div></div>
  <div class="stat"><div class="v">{full_result['holdout']['win_rate']}%</div><div class="l">HOLDOUT win rate</div></div>
  <div class="stat"><div class="v">{full_result['holdout']['trades']}</div><div class="l">HOLDOUT trades</div></div>
</div>
</div>

<div class="card">
<h2>Equity curve — VALIDATE + HOLDOUT only</h2>
{equity_svg}
</div>

<div class="card">
<h2>Monte Carlo (2,000 bootstrap paths, VALIDATE+HOLDOUT trades)</h2>
<div class="grid">
  <div class="stat"><div class="v">{mc['p5_final_r']}R</div><div class="l">P5 final equity</div></div>
  <div class="stat"><div class="v">{mc['p50_final_r']}R</div><div class="l">P50 final equity</div></div>
  <div class="stat"><div class="v">{mc['p95_final_r']}R</div><div class="l">P95 final equity</div></div>
  <div class="stat"><div class="v">{mc['p5_maxdd']}R</div><div class="l">P5 max drawdown</div></div>
  <div class="stat"><div class="v">{mc['p95_maxdd']}R</div><div class="l">P95 max drawdown</div></div>
  <div class="stat"><div class="v">{holdout_result['n_variants_tried']}</div><div class="l">Variants tried (multiple-testing context)</div></div>
</div>
</div>

<div class="card">
<h2>Registry — all iterations</h2>
<table>
<tr><th>#</th><th>Variant</th><th>Train exp.</th><th>Validate exp.</th><th>PF</th><th>MaxDD</th><th>Sharpe</th><th>Trades</th><th>Verdict</th></tr>
{registry_html_rows}
</table>
</div>

<div class="card">
<h2>Lessons learned</h2>
<ul>
{''.join(f'<li>{l}</li>' for l in lessons)}
</ul>
</div>

<p style="color:#666;font-size:12px">Generated by backend/research/build_report.py — see SPEC.md, registry.csv, research_log.md for full methodology and detail.</p>
</body></html>
"""

with open(os.path.join(OUT_DIR, "report.html"), "w") as f:
    f.write(html)

print(f"Wrote {os.path.join(OUT_DIR, 'report.html')}")
