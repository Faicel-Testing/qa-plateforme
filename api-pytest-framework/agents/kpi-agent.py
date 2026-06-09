# ============================================================
# KPI Agent — Tableau de bord qualité professionnel
# ============================================================
# Génère les KPIs depuis allure-results et produit :
#   1. environment.properties  → widget Allure ENVIRONMENT
#   2. docs/kpi-dashboard.html → dashboard HTML standalone
#
# Usage:
#   python agents/kpi-agent.py             → génère tout
#   python agents/kpi-agent.py dashboard   → HTML uniquement
#   python agents/kpi-agent.py env         → environment.properties uniquement
#   python agents/kpi-agent.py summary     → résumé console
# ============================================================

import sys, os, json, glob, re, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FRAMEWORK   = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS_DIR = os.path.join(FRAMEWORK, "allure-results")
DOCS_DIR    = os.path.join(FRAMEWORK, "docs")
FLAKY_FILE  = os.path.join(DOCS_DIR, "flaky-report.json")
BASELINE    = os.path.join(DOCS_DIR, "baseline.json")
TREND_FILE  = os.path.join(FRAMEWORK, "allure-report", "history", "history-trend.json")
ENV_FILE    = os.path.join(RESULTS_DIR, "environment.properties")
DASH_FILE   = os.path.join(DOCS_DIR, "kpi-dashboard.html")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"


# ── Collecte des données ───────────────────────────────────────────────────

def collect_kpis() -> dict:
    stats   = {"passed": 0, "failed": 0, "broken": 0, "skipped": 0, "total": 0}
    suites  = {}
    durations = []
    failures  = []
    tc_tags   = set()

    for f in glob.glob(os.path.join(RESULTS_DIR, "*-result.json")):
        try:
            with open(f, encoding="utf-8") as fp:
                d = json.load(fp)
            s = d.get("status", "unknown")
            if s in stats:
                stats[s] += 1
            stats["total"] += 1

            start = d.get("start", 0)
            stop  = d.get("stop", 0)
            if start and stop:
                durations.append(stop - start)

            labels = d.get("labels", [])
            suite  = next((lb["value"] for lb in labels if lb["name"] == "tag" and lb["value"].startswith("us-")), "other")
            suites[suite] = suites.get(suite, {"passed": 0, "failed": 0, "broken": 0, "total": 0})
            suites[suite]["total"] += 1
            if s in suites[suite]:
                suites[suite][s] += 1

            tc = next((lb["value"] for lb in labels if lb["name"] == "tag" and re.match(r"tc-\d+", lb["value"])), None)
            if tc:
                tc_tags.add(tc)

            if s in ("failed", "broken"):
                msg = (d.get("statusDetails") or {}).get("message", "")[:120]
                failures.append({"name": d.get("name", "?"), "status": s, "message": msg, "tc": tc})
        except Exception:
            pass

    # Flaky
    flaky_data = {}
    if os.path.exists(FLAKY_FILE):
        with open(FLAKY_FILE, encoding="utf-8") as fp:
            flaky_data = json.load(fp).get("flaky_tests", {})

    # Trend
    trend = []
    if os.path.exists(TREND_FILE):
        with open(TREND_FILE, encoding="utf-8") as fp:
            raw = json.load(fp)
        trend = [{"run": t.get("buildOrder", i+1), "passed": t["data"]["passed"],
                  "failed": t["data"]["failed"], "broken": t["data"].get("broken", 0),
                  "total": t["data"]["total"]} for i, t in enumerate(reversed(raw))]

    total   = stats["total"] or 1
    passed  = stats["passed"]
    failed  = stats["failed"]
    broken  = stats["broken"]
    flaky_n = len(flaky_data)
    anomalies = failed + broken + flaky_n
    total_exec_ms = sum(durations)
    avg_ms  = total_exec_ms / len(durations) if durations else 0
    total_tcs_defined = 51  # TCs définis dans le projet

    pass_rate      = round(passed / total * 100, 1)
    fail_rate      = round(failed / total * 100, 1)
    broken_rate    = round(broken / total * 100, 1)
    anomaly_rate   = round(anomalies / total * 100, 1)
    flaky_rate     = round(flaky_n / total_tcs_defined * 100, 1)
    coverage       = round(len(tc_tags) / total_tcs_defined * 100, 1)

    # ── Quality Gate ──────────────────────────────────────────
    # Seuils professionnels — chaque critère contribue au verdict final
    GATE = [
        ("Pass Rate >= 90%",         pass_rate >= 90,    f"{pass_rate}%"),
        ("Fail Rate <= 5%",          fail_rate <= 5,     f"{fail_rate}%"),
        ("Anomaly Rate <= 10%",      anomaly_rate <= 10, f"{anomaly_rate}%"),
        ("Flaky Rate <= 20%",        flaky_rate <= 20,   f"{flaky_rate}%"),
        ("Automation Coverage >= 80%", coverage >= 80,   f"{coverage}%"),
    ]
    gate_passed  = [g for g in GATE if g[1]]
    gate_failed  = [g for g in GATE if not g[1]]
    gate_verdict = "PASSED" if not gate_failed else "FAILED"

    return {
        "stats": stats,
        "pass_rate":      pass_rate,
        "fail_rate":      fail_rate,
        "broken_rate":    broken_rate,
        "anomaly_rate":   anomaly_rate,
        "flaky_count":    flaky_n,
        "flaky_rate":     flaky_rate,
        "automation_coverage": coverage,
        "total_exec_ms":  total_exec_ms,
        "avg_test_ms":    round(avg_ms),
        "exec_time_fmt":  fmt_duration(total_exec_ms),
        "avg_time_fmt":   fmt_duration(avg_ms),
        "suites":         suites,
        "failures":       failures,
        "flaky_data":     flaky_data,
        "trend":          trend,
        "total_tcs":      total_tcs_defined,
        "generated_at":   time.strftime("%Y-%m-%d %H:%M"),
        "framework":      "pytest-bdd 7.3 + Requests 2.32",
        "llm":            "Groq LLaMA 3.3 70B",
        "api_under_test": "Restful-Booker REST API",
        "gate":           GATE,
        "gate_passed":    gate_passed,
        "gate_failed":    gate_failed,
        "gate_verdict":   gate_verdict,
    }


def fmt_duration(ms: float) -> str:
    if ms <= 0:
        return "0s"
    s = int(ms / 1000)
    if s < 60:
        return f"{s}s"
    return f"{s // 60}m {s % 60:02d}s"


# ── 1. environment.properties ──────────────────────────────────────────────

def write_env_properties(kpi: dict):
    verdict = kpi["gate_verdict"]
    blocked = " | ".join(f"{g[0]} ({g[2]})" for g in kpi["gate_failed"]) or "None"
    lines = [
        f"Quality.Gate={verdict}",
        f"Gate.Criteria.Passed={len(kpi['gate_passed'])}/{len(kpi['gate'])}",
        f"Gate.Blockers={blocked}",
        f"Pass.Rate={kpi['pass_rate']}%",
        f"Fail.Rate={kpi['fail_rate']}%",
        f"Broken.Rate={kpi['broken_rate']}%",
        f"Anomaly.Rate={kpi['anomaly_rate']}%",
        f"Flaky.Tests={kpi['flaky_count']} ({kpi['flaky_rate']}%)",
        f"Automation.Coverage={kpi['automation_coverage']}%",
        f"Total.TCs={kpi['total_tcs']}",
        f"Passed={kpi['stats']['passed']}",
        f"Failed={kpi['stats']['failed']}",
        f"Execution.Time={kpi['exec_time_fmt']}",
        f"Avg.Test.Duration={kpi['avg_time_fmt']}",
        f"Framework={kpi['framework']}",
        f"LLM.Engine={kpi['llm']}",
        f"API.Under.Test={kpi['api_under_test']}",
        f"Report.Generated={kpi['generated_at']}",
    ]
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"{G}  [OK] environment.properties → allure-results/{E}")


# ── 2. KPI Dashboard HTML ─────────────────────────────────────────────────

def _gate_banner(kpi: dict) -> str:
    verdict  = kpi["gate_verdict"]
    css      = "passed" if verdict == "PASSED" else "failed"
    icon     = "✅" if verdict == "PASSED" else "❌"
    n_ok     = len(kpi["gate_passed"])
    n_total  = len(kpi["gate"])
    rows = ""
    for name, ok, val in kpi["gate"]:
        dot = "ok" if ok else "ko"
        rows += f'<div class="gate-row"><div class="gate-dot {dot}"></div><span class="gate-name">{name}</span><span class="gate-val">{val}</span></div>\n'
    return f"""
  <div class="gate-banner {css}">
    <div>
      <div class="gate-label">Quality Gate</div>
      <div class="gate-verdict {css}">{icon} {verdict}</div>
      <div class="gate-score" style="margin-top:6px">{n_ok}/{n_total} critères satisfaits</div>
    </div>
    <div class="gate-criteria">
      {rows}
    </div>
  </div>"""


def write_dashboard(kpi: dict):
    os.makedirs(DOCS_DIR, exist_ok=True)
    s = kpi["stats"]

    # Données suites pour le graphe
    suite_labels = list(kpi["suites"].keys())
    suite_pass   = [kpi["suites"][k]["passed"] for k in suite_labels]
    suite_fail   = [kpi["suites"][k]["failed"] + kpi["suites"][k]["broken"] for k in suite_labels]

    # Données trend
    trend_labels = [f"Run {t['run']}" for t in kpi["trend"]]
    trend_pass   = [t["passed"] for t in kpi["trend"]]
    trend_fail   = [t["failed"] + t["broken"] for t in kpi["trend"]]

    # Couleurs KPI cards
    def rate_color(rate, inverse=False):
        if inverse:
            return "#10b981" if rate == 0 else "#ef4444" if rate > 10 else "#f59e0b"
        return "#10b981" if rate >= 90 else "#f59e0b" if rate >= 70 else "#ef4444"

    # Tableau failures
    fail_rows = ""
    for f in kpi["failures"][:10]:
        status_badge = f'<span class="badge badge-fail">{f["status"].upper()}</span>'
        msg = f["message"][:80].replace("<", "&lt;").replace(">", "&gt;")
        fail_rows += f"""
        <tr>
          <td>{f["tc"] or "—"}</td>
          <td>{f["name"][:55]}</td>
          <td>{status_badge}</td>
          <td class="msg">{msg}</td>
        </tr>"""

    # Tableau flaky
    flaky_rows = ""
    for name, info in list(kpi["flaky_data"].items())[:8]:
        score_pct = int(info["score"] * 100)
        color = "#ef4444" if score_pct > 50 else "#f59e0b"
        flaky_rows += f"""
        <tr>
          <td>{info.get("tc_tag", "—")}</td>
          <td>{name[:55]}</td>
          <td><div class="score-bar"><div class="score-fill" style="width:{score_pct}%;background:{color}"></div></div> {score_pct}%</td>
          <td>{'&nbsp;'.join(['<span class="run-dot pass">P</span>' if s == "passed" else '<span class="run-dot fail">F</span>' for s in info.get("statuses", [])])}</td>
        </tr>"""

    if not flaky_rows:
        flaky_rows = '<tr><td colspan="4" style="text-align:center;color:#10b981;padding:16px">✓ Aucun test flaky détecté</td></tr>'

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>QA KPI Dashboard — api-pytest-framework</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f172a; --card: #1e293b; --border: #334155;
    --text: #e2e8f0; --muted: #94a3b8; --accent: #6366f1;
    --green: #10b981; --red: #ef4444; --yellow: #f59e0b; --blue: #3b82f6;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }}

  /* Header */
  .header {{ background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border-bottom: 1px solid var(--border); padding: 24px 32px;
    display: flex; align-items: center; justify-content: space-between; }}
  .header h1 {{ font-size: 22px; font-weight: 700; color: #fff; }}
  .header h1 span {{ color: var(--accent); }}
  .header-meta {{ text-align: right; color: var(--muted); font-size: 13px; line-height: 1.6; }}
  .badge-live {{ background: var(--green); color: #fff; font-size: 11px;
    padding: 2px 10px; border-radius: 999px; font-weight: 600; margin-left: 10px; }}

  /* Main layout */
  .main {{ padding: 28px 32px; max-width: 1400px; margin: 0 auto; }}

  /* KPI Cards */
  .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px; margin-bottom: 28px; }}
  .kpi-card {{ background: var(--card); border: 1px solid var(--border);
    border-radius: 12px; padding: 20px; position: relative; overflow: hidden; }}
  .kpi-card::before {{ content: ''; position: absolute; top: 0; left: 0;
    right: 0; height: 3px; background: var(--kpi-color, var(--accent)); }}
  .kpi-label {{ font-size: 12px; font-weight: 600; color: var(--muted);
    text-transform: uppercase; letter-spacing: .06em; margin-bottom: 8px; }}
  .kpi-value {{ font-size: 36px; font-weight: 800; color: var(--kpi-color, #fff); line-height: 1; }}
  .kpi-sub {{ font-size: 12px; color: var(--muted); margin-top: 6px; }}
  .kpi-icon {{ position: absolute; right: 16px; top: 16px; font-size: 28px; opacity: .15; }}

  /* Charts grid */
  .charts-grid {{ display: grid; grid-template-columns: 1fr 2fr; gap: 20px; margin-bottom: 28px; }}
  .chart-card {{ background: var(--card); border: 1px solid var(--border);
    border-radius: 12px; padding: 20px; }}
  .chart-title {{ font-size: 14px; font-weight: 600; color: var(--text);
    margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }}
  .chart-title::before {{ content: ''; display: inline-block; width: 3px;
    height: 16px; background: var(--accent); border-radius: 2px; }}
  .chart-wrap {{ position: relative; }}

  /* Trend */
  .trend-card {{ background: var(--card); border: 1px solid var(--border);
    border-radius: 12px; padding: 20px; margin-bottom: 28px; }}

  /* Tables */
  .table-card {{ background: var(--card); border: 1px solid var(--border);
    border-radius: 12px; padding: 20px; margin-bottom: 20px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ text-align: left; padding: 10px 12px; font-size: 11px; font-weight: 600;
    color: var(--muted); text-transform: uppercase; letter-spacing: .05em;
    border-bottom: 1px solid var(--border); }}
  td {{ padding: 10px 12px; border-bottom: 1px solid #1e293b; color: var(--text); vertical-align: middle; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: rgba(99,102,241,.06); }}
  .msg {{ color: var(--muted); font-size: 12px; max-width: 300px; word-break: break-word; }}

  /* Badges */
  .badge {{ font-size: 11px; font-weight: 700; padding: 3px 8px;
    border-radius: 4px; display: inline-block; }}
  .badge-fail {{ background: rgba(239,68,68,.2); color: #ef4444; }}
  .badge-broken {{ background: rgba(245,158,11,.2); color: #f59e0b; }}
  .badge-pass {{ background: rgba(16,185,129,.2); color: #10b981; }}

  /* Score bar */
  .score-bar {{ background: var(--border); border-radius: 4px;
    height: 8px; width: 100px; display: inline-block; overflow: hidden; vertical-align: middle; }}
  .score-fill {{ height: 100%; border-radius: 4px; }}

  /* Run dots */
  .run-dot {{ display: inline-block; width: 20px; height: 20px; border-radius: 4px;
    font-size: 10px; font-weight: 700; text-align: center; line-height: 20px; }}
  .run-dot.pass {{ background: rgba(16,185,129,.2); color: var(--green); }}
  .run-dot.fail {{ background: rgba(239,68,68,.2); color: var(--red); }}

  /* Footer */
  .footer {{ text-align: center; padding: 24px; color: var(--muted); font-size: 12px;
    border-top: 1px solid var(--border); margin-top: 12px; }}
  .footer strong {{ color: var(--accent); }}

  /* Section title */
  .section-title {{ font-size: 16px; font-weight: 700; color: #fff;
    margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }}

  /* Quality Gate */
  .gate-banner {{ border-radius: 12px; padding: 20px 28px; margin-bottom: 28px;
    display: flex; align-items: center; justify-content: space-between;
    border: 1px solid; }}
  .gate-banner.passed {{ background: rgba(16,185,129,.1); border-color: rgba(16,185,129,.4); }}
  .gate-banner.failed {{ background: rgba(239,68,68,.1);  border-color: rgba(239,68,68,.4); }}
  .gate-verdict {{ font-size: 32px; font-weight: 900; letter-spacing: .05em; }}
  .gate-verdict.passed {{ color: #10b981; }}
  .gate-verdict.failed {{ color: #ef4444; }}
  .gate-label {{ font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: .08em; color: var(--muted); margin-bottom: 4px; }}
  .gate-score {{ font-size: 18px; font-weight: 700; color: var(--text); }}
  .gate-criteria {{ display: flex; flex-direction: column; gap: 6px; }}
  .gate-row {{ display: flex; align-items: center; gap: 10px; font-size: 13px; }}
  .gate-dot {{ width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }}
  .gate-dot.ok {{ background: #10b981; }}
  .gate-dot.ko {{ background: #ef4444; }}
  .gate-name {{ color: var(--text); }}
  .gate-val  {{ color: var(--muted); margin-left: auto; font-size: 12px; font-weight: 600; }}
</style>
</head>
<body>

<!-- HEADER -->
<div class="header">
  <div>
    <h1>QA <span>KPI</span> Dashboard <span class="badge-live">LIVE</span></h1>
    <div style="color:var(--muted);font-size:13px;margin-top:4px">{kpi["api_under_test"]}</div>
  </div>
  <div class="header-meta">
    <div>{kpi["framework"]}</div>
    <div>LLM · {kpi["llm"]}</div>
    <div>Généré le {kpi["generated_at"]}</div>
  </div>
</div>

<div class="main">

  <!-- QUALITY GATE BANNER -->
  {_gate_banner(kpi)}

  <!-- KPI CARDS -->
  <div class="kpi-grid">
    <div class="kpi-card" style="--kpi-color:{rate_color(kpi['pass_rate'])}">
      <div class="kpi-icon">✅</div>
      <div class="kpi-label">Pass Rate</div>
      <div class="kpi-value">{kpi['pass_rate']}%</div>
      <div class="kpi-sub">{s['passed']} / {s['total']} tests passés</div>
    </div>
    <div class="kpi-card" style="--kpi-color:{rate_color(kpi['fail_rate'], inverse=True)}">
      <div class="kpi-icon">❌</div>
      <div class="kpi-label">Fail Rate</div>
      <div class="kpi-value">{kpi['fail_rate']}%</div>
      <div class="kpi-sub">{s['failed']} échecs · {s['broken']} broken</div>
    </div>
    <div class="kpi-card" style="--kpi-color:{rate_color(kpi['anomaly_rate'], inverse=True)}">
      <div class="kpi-icon">⚠️</div>
      <div class="kpi-label">Taux d'anomalies</div>
      <div class="kpi-value">{kpi['anomaly_rate']}%</div>
      <div class="kpi-sub">{s['failed'] + s['broken']} défauts + {kpi['flaky_count']} flaky</div>
    </div>
    <div class="kpi-card" style="--kpi-color:{rate_color(kpi['flaky_rate'], inverse=True)}">
      <div class="kpi-icon">🔀</div>
      <div class="kpi-label">Flaky Rate</div>
      <div class="kpi-value">{kpi['flaky_rate']}%</div>
      <div class="kpi-sub">{kpi['flaky_count']} tests instables détectés</div>
    </div>
    <div class="kpi-card" style="--kpi-color:{rate_color(kpi['automation_coverage'])}">
      <div class="kpi-icon">🤖</div>
      <div class="kpi-label">Couverture Automation</div>
      <div class="kpi-value">{kpi['automation_coverage']}%</div>
      <div class="kpi-sub">{s['total']} TCs exécutés / {kpi['total_tcs']} définis</div>
    </div>
    <div class="kpi-card" style="--kpi-color:#6366f1">
      <div class="kpi-icon">⏱️</div>
      <div class="kpi-label">Temps d'exécution</div>
      <div class="kpi-value" style="font-size:28px">{kpi['exec_time_fmt']}</div>
      <div class="kpi-sub">Moy. par test : {kpi['avg_time_fmt']}</div>
    </div>
    <div class="kpi-card" style="--kpi-color:#3b82f6">
      <div class="kpi-icon">🧪</div>
      <div class="kpi-label">Tests Automatisés</div>
      <div class="kpi-value">{s['total']}</div>
      <div class="kpi-sub">Smoke: 5 · Critical: 9 · Régression: 51</div>
    </div>
    <div class="kpi-card" style="--kpi-color:#8b5cf6">
      <div class="kpi-icon">🏃</div>
      <div class="kpi-label">Runs Historiques</div>
      <div class="kpi-value">{len(kpi['trend'])}</div>
      <div class="kpi-sub">Exécutions tracées dans Allure</div>
    </div>
  </div>

  <!-- CHARTS -->
  <div class="charts-grid">
    <div class="chart-card">
      <div class="chart-title">Distribution des résultats</div>
      <div class="chart-wrap" style="max-height:280px">
        <canvas id="donutChart"></canvas>
      </div>
    </div>
    <div class="chart-card">
      <div class="chart-title">Résultats par suite</div>
      <div class="chart-wrap" style="max-height:280px">
        <canvas id="suiteChart"></canvas>
      </div>
    </div>
  </div>

  <!-- TREND -->
  <div class="trend-card">
    <div class="chart-title">Évolution de la qualité (trend)</div>
    <div class="chart-wrap" style="max-height:220px">
      <canvas id="trendChart"></canvas>
    </div>
  </div>

  <!-- FAILURES TABLE -->
  <div class="section-title">Tests en échec</div>
  <div class="table-card">
    <table>
      <thead>
        <tr><th>TC</th><th>Nom du test</th><th>Statut</th><th>Message d'erreur</th></tr>
      </thead>
      <tbody>
        {fail_rows if fail_rows else '<tr><td colspan="4" style="text-align:center;color:#10b981;padding:16px">✓ Aucun test en échec</td></tr>'}
      </tbody>
    </table>
  </div>

  <!-- FLAKY TABLE -->
  <div class="section-title">Tests Flaky</div>
  <div class="table-card">
    <table>
      <thead>
        <tr><th>TC</th><th>Nom du test</th><th>Score d'instabilité</th><th>Runs</th></tr>
      </thead>
      <tbody>{flaky_rows}</tbody>
    </table>
  </div>

</div><!-- /main -->

<div class="footer">
  Généré par <strong>kpi-agent.py</strong> · Framework <strong>{kpi["framework"]}</strong> ·
  LLM <strong>{kpi["llm"]}</strong> · {kpi["generated_at"]}
</div>

<script>
const COLORS = {{
  green:  '#10b981', red: '#ef4444', yellow: '#f59e0b',
  blue:   '#3b82f6', purple: '#8b5cf6', muted: '#475569'
}};
const FONT = {{ color: '#94a3b8', size: 12 }};

// Donut
new Chart(document.getElementById('donutChart'), {{
  type: 'doughnut',
  data: {{
    labels: ['Passés', 'Échoués', 'Broken', 'Skipped'],
    datasets: [{{ data: [{s['passed']}, {s['failed']}, {s['broken']}, {s['skipped']}],
      backgroundColor: [COLORS.green, COLORS.red, COLORS.yellow, COLORS.muted],
      borderWidth: 0, hoverOffset: 6 }}]
  }},
  options: {{
    cutout: '70%', plugins: {{
      legend: {{ position: 'bottom', labels: {{ color: '#94a3b8', padding: 14, font: {{ size: 12 }} }} }},
      tooltip: {{ callbacks: {{
        label: ctx => ` ${{ctx.label}}: ${{ctx.parsed}} (${{Math.round(ctx.parsed/{s['total']}*100)}}%)`
      }} }}
    }}
  }}
}});

// Suite bar
new Chart(document.getElementById('suiteChart'), {{
  type: 'bar',
  data: {{
    labels: {json.dumps(suite_labels)},
    datasets: [
      {{ label: 'Passés',   data: {json.dumps(suite_pass)}, backgroundColor: COLORS.green, borderRadius: 4 }},
      {{ label: 'Échoués',  data: {json.dumps(suite_fail)}, backgroundColor: COLORS.red,   borderRadius: 4 }}
    ]
  }},
  options: {{
    responsive: true, maintainAspectRatio: true,
    plugins: {{ legend: {{ labels: {{ color: '#94a3b8' }} }} }},
    scales: {{
      x: {{ stacked: true, ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#1e293b' }} }},
      y: {{ stacked: true, ticks: {{ color: '#94a3b8', stepSize: 1 }}, grid: {{ color: '#1e293b' }} }}
    }}
  }}
}});

// Trend line
new Chart(document.getElementById('trendChart'), {{
  type: 'line',
  data: {{
    labels: {json.dumps(trend_labels)},
    datasets: [
      {{ label: 'Passés', data: {json.dumps(trend_pass)},
        borderColor: COLORS.green, backgroundColor: 'rgba(16,185,129,.15)',
        fill: true, tension: .4, pointRadius: 5, pointHoverRadius: 7 }},
      {{ label: 'Échoués', data: {json.dumps(trend_fail)},
        borderColor: COLORS.red, backgroundColor: 'rgba(239,68,68,.1)',
        fill: true, tension: .4, pointRadius: 5, pointHoverRadius: 7 }}
    ]
  }},
  options: {{
    responsive: true, maintainAspectRatio: true,
    plugins: {{ legend: {{ labels: {{ color: '#94a3b8' }} }} }},
    scales: {{
      x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#1e293b' }} }},
      y: {{ ticks: {{ color: '#94a3b8', stepSize: 5 }}, grid: {{ color: '#1e293b' }}, min: 0 }}
    }}
  }}
}});
</script>
</body>
</html>"""

    with open(DASH_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"{G}  [OK] KPI Dashboard → docs/kpi-dashboard.html{E}")


# ── Résumé console ─────────────────────────────────────────────────────────

def print_summary(kpi: dict):
    s = kpi["stats"]
    verdict = kpi["gate_verdict"]
    gcolor  = G if verdict == "PASSED" else R
    print(f"\n{W}{'='*55}{E}")
    print(f"{W}  QA KPI SUMMARY — {kpi['generated_at']}{E}")
    print(f"{W}{'='*55}{E}")
    print(f"\n  QUALITY GATE : {gcolor}{W} {verdict} {E}  ({len(kpi['gate_passed'])}/{len(kpi['gate'])} critères)")
    for name, ok, val in kpi["gate"]:
        sym = f"{G}✓{E}" if ok else f"{R}✗{E}"
        print(f"  {sym}  {name:<35} {val}")
    print()
    print(f"\n  {'KPI':<30} {'Valeur':>12}")
    print(f"  {'-'*44}")

    def row(label, value, color=None):
        c = color or E
        print(f"  {label:<30} {c}{str(value):>12}{E}")

    row("Pass Rate",              f"{kpi['pass_rate']}%",          G if kpi['pass_rate'] >= 90 else R)
    row("Fail Rate",              f"{kpi['fail_rate']}%",          G if kpi['fail_rate'] == 0 else R)
    row("Taux d'anomalies",       f"{kpi['anomaly_rate']}%",       G if kpi['anomaly_rate'] == 0 else Y)
    row("Flaky Rate",             f"{kpi['flaky_rate']}%",         G if kpi['flaky_count'] == 0 else Y)
    row("Couverture Automation",  f"{kpi['automation_coverage']}%", G)
    row("Tests exécutés",         s['total'],                       C)
    row("Passés / Échoués",       f"{s['passed']} / {s['failed']}", C)
    row("Temps d'exécution",      kpi['exec_time_fmt'],             C)
    row("Moy. par test",          kpi['avg_time_fmt'],              C)
    row("Runs historiques",       len(kpi['trend']),                C)
    print(f"  {'-'*44}")
    print(f"\n  Framework  : {kpi['framework']}")
    print(f"  LLM Engine : {kpi['llm']}")
    print(f"  API testée : {kpi['api_under_test']}\n")


# ── Main ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    print(f"\n{C}[KPI Agent] Collecte des données depuis allure-results...{E}")
    kpi = collect_kpis()

    if cmd in ("all", "env"):
        write_env_properties(kpi)
    if cmd in ("all", "dashboard"):
        write_dashboard(kpi)
    if cmd in ("all", "summary"):
        print_summary(kpi)
    if cmd == "all":
        print(f"\n{G}  Done. Regenerer le rapport Allure pour voir l'ENVIRONMENT widget :{E}")
        print(f"  allure generate allure-results -o allure-report --clean\n")
