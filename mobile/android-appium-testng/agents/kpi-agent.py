# ============================================================
# KPI Agent — Mobile (Appium / Android)
# ============================================================
# Génère les KPIs depuis target/allure-results/ et produit :
#   1. target/allure-results/environment.properties → widget Allure ENVIRONMENT
#   2. docs/kpi-dashboard.html → dashboard HTML standalone
#
# Usage:
#   python agents/kpi-agent.py             → génère tout
#   python agents/kpi-agent.py dashboard   → HTML uniquement
#   python agents/kpi-agent.py env         → environment.properties uniquement
#   python agents/kpi-agent.py summary     → résumé console
# ============================================================

import sys, os, json, glob, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FRAMEWORK   = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS_DIR = os.path.join(FRAMEWORK, "target", "allure-results")
DOCS_DIR    = os.path.join(FRAMEWORK, "docs")
FLAKY_FILE  = os.path.join(DOCS_DIR, "flaky-report.json")
TREND_FILE  = os.path.join(FRAMEWORK, "target", "allure-report", "history", "history-trend.json")
ENV_FILE    = os.path.join(RESULTS_DIR, "environment.properties")
DASH_FILE   = os.path.join(DOCS_DIR, "kpi-dashboard.html")

# Méta du projet mobile
TOTAL_TCS_DEFINED = 17   # Test01→Test15 + 2 méthodes Test09
FRAMEWORK_NAME    = "Appium 9.2.2 + TestNG 7.10.2 (Java 17)"
APP_UNDER_TEST    = "QAcart-To-Do.apk (Android)"
LLM_ENGINE        = "Groq LLaMA 3.3 70B"

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"


# ── Collecte des données ───────────────────────────────────────────────────

def collect_kpis() -> dict:
    stats     = {"passed": 0, "failed": 0, "broken": 0, "skipped": 0, "total": 0}
    groups    = {}
    durations = []
    failures  = []

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

            labels     = d.get("labels", [])
            test_class = next((lb["value"] for lb in labels if lb["name"] == "testClass"), "?")
            short_cls  = test_class.split(".")[-1] if "." in test_class else test_class
            grp_tags   = [lb["value"] for lb in labels if lb["name"] == "tag"]

            for grp in (grp_tags or ["other"]):
                groups[grp] = groups.get(grp, {"passed": 0, "failed": 0, "broken": 0, "total": 0})
                groups[grp]["total"] += 1
                if s in groups[grp]:
                    groups[grp][s] += 1

            if s in ("failed", "broken"):
                msg = (d.get("statusDetails") or {}).get("message", "")[:120]
                failures.append({
                    "name":       d.get("name", "?"),
                    "test_class": short_cls,
                    "status":     s,
                    "message":    msg,
                })
        except Exception:
            pass

    # Flaky data
    flaky_data = {}
    if os.path.exists(FLAKY_FILE):
        with open(FLAKY_FILE, encoding="utf-8") as fp:
            flaky_data = json.load(fp).get("flaky_tests", {})

    # Trend
    trend = []
    if os.path.exists(TREND_FILE):
        with open(TREND_FILE, encoding="utf-8") as fp:
            raw = json.load(fp)
        trend = [{"run": t.get("buildOrder", i+1),
                  "passed": t["data"]["passed"],
                  "failed": t["data"]["failed"],
                  "broken": t["data"].get("broken", 0),
                  "total":  t["data"]["total"]}
                 for i, t in enumerate(reversed(raw))]

    total      = stats["total"] or 1
    passed     = stats["passed"]
    failed     = stats["failed"]
    broken     = stats["broken"]
    flaky_n    = len(flaky_data)
    anomalies  = failed + broken + flaky_n
    total_exec_ms = sum(durations)
    avg_ms     = total_exec_ms / len(durations) if durations else 0

    pass_rate     = round(passed / total * 100, 1)
    fail_rate     = round(failed / total * 100, 1)
    broken_rate   = round(broken / total * 100, 1)
    anomaly_rate  = round(anomalies / total * 100, 1)
    flaky_rate    = round(flaky_n / TOTAL_TCS_DEFINED * 100, 1)
    coverage      = round(total / TOTAL_TCS_DEFINED * 100, 1)

    # Quality Gate Mobile
    GATE = [
        ("Pass Rate >= 85%",          pass_rate >= 85,    f"{pass_rate}%"),
        ("Fail Rate <= 10%",          fail_rate <= 10,    f"{fail_rate}%"),
        ("Anomaly Rate <= 15%",       anomaly_rate <= 15, f"{anomaly_rate}%"),
        ("Flaky Rate <= 25%",         flaky_rate <= 25,   f"{flaky_rate}%"),
        ("Automation Coverage >= 70%", coverage >= 70,    f"{coverage}%"),
    ]
    gate_passed  = [g for g in GATE if g[1]]
    gate_failed  = [g for g in GATE if not g[1]]
    gate_verdict = "PASSED" if not gate_failed else "FAILED"

    return {
        "stats": stats,
        "pass_rate":     pass_rate,
        "fail_rate":     fail_rate,
        "broken_rate":   broken_rate,
        "anomaly_rate":  anomaly_rate,
        "flaky_count":   flaky_n,
        "flaky_rate":    flaky_rate,
        "coverage":      coverage,
        "total_exec_ms": total_exec_ms,
        "avg_test_ms":   round(avg_ms),
        "exec_time_fmt": fmt_duration(total_exec_ms),
        "avg_time_fmt":  fmt_duration(avg_ms),
        "groups":        groups,
        "failures":      failures,
        "flaky_data":    flaky_data,
        "trend":         trend,
        "total_tcs":     TOTAL_TCS_DEFINED,
        "generated_at":  time.strftime("%Y-%m-%d %H:%M"),
        "framework":     FRAMEWORK_NAME,
        "llm":           LLM_ENGINE,
        "app_under_test": APP_UNDER_TEST,
        "gate":          GATE,
        "gate_passed":   gate_passed,
        "gate_failed":   gate_failed,
        "gate_verdict":  gate_verdict,
    }


def fmt_duration(ms: float) -> str:
    if ms <= 0:
        return "0s"
    s = int(ms / 1000)
    return f"{s}s" if s < 60 else f"{s // 60}m {s % 60:02d}s"


# ── 1. environment.properties ──────────────────────────────────────────────

def write_env_properties(kpi: dict):
    verdict = kpi["gate_verdict"]
    blocked = " | ".join(f"{g[0]} ({g[2]})" for g in kpi["gate_failed"]) or "None"
    lines   = [
        f"Quality.Gate={verdict}",
        f"Gate.Criteria.Passed={len(kpi['gate_passed'])}/{len(kpi['gate'])}",
        f"Gate.Blockers={blocked}",
        f"Pass.Rate={kpi['pass_rate']}%",
        f"Fail.Rate={kpi['fail_rate']}%",
        f"Anomaly.Rate={kpi['anomaly_rate']}%",
        f"Flaky.Tests={kpi['flaky_count']} ({kpi['flaky_rate']}%)",
        f"Automation.Coverage={kpi['coverage']}%",
        f"Total.TCs.Defined={kpi['total_tcs']}",
        f"Total.TCs.Executed={kpi['stats']['total']}",
        f"Passed={kpi['stats']['passed']}",
        f"Failed={kpi['stats']['failed']}",
        f"Execution.Time={kpi['exec_time_fmt']}",
        f"Avg.Test.Duration={kpi['avg_time_fmt']}",
        f"Framework={kpi['framework']}",
        f"LLM.Engine={kpi['llm']}",
        f"App.Under.Test={kpi['app_under_test']}",
        f"Report.Generated={kpi['generated_at']}",
    ]
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"{G}  [OK] environment.properties → target/allure-results/{E}")


# ── 2. KPI Dashboard HTML ─────────────────────────────────────────────────

def _gate_banner(kpi: dict) -> str:
    verdict = kpi["gate_verdict"]
    css     = "passed" if verdict == "PASSED" else "failed"
    icon    = "✅" if verdict == "PASSED" else "❌"
    n_ok    = len(kpi["gate_passed"])
    n_total = len(kpi["gate"])
    rows    = ""
    for name, ok, val in kpi["gate"]:
        dot = "ok" if ok else "ko"
        rows += f'<div class="gate-row"><div class="gate-dot {dot}"></div><span class="gate-name">{name}</span><span class="gate-val">{val}</span></div>\n'
    return f"""
  <div class="gate-banner {css}">
    <div>
      <div class="gate-label">Quality Gate Mobile</div>
      <div class="gate-verdict {css}">{icon} {verdict}</div>
      <div class="gate-score" style="margin-top:6px">{n_ok}/{n_total} critères satisfaits</div>
    </div>
    <div class="gate-criteria">{rows}</div>
  </div>"""


def write_dashboard(kpi: dict):
    os.makedirs(DOCS_DIR, exist_ok=True)
    s = kpi["stats"]

    grp_labels = list(kpi["groups"].keys())
    grp_pass   = [kpi["groups"][k].get("passed", 0) for k in grp_labels]
    grp_fail   = [kpi["groups"][k].get("failed", 0) + kpi["groups"][k].get("broken", 0) for k in grp_labels]

    trend_labels = [f"Run {t['run']}" for t in kpi["trend"]]
    trend_pass   = [t["passed"] for t in kpi["trend"]]
    trend_fail   = [t["failed"] + t["broken"] for t in kpi["trend"]]

    def rate_color(rate, inverse=False):
        if inverse:
            return "#10b981" if rate == 0 else "#ef4444" if rate > 10 else "#f59e0b"
        return "#10b981" if rate >= 85 else "#f59e0b" if rate >= 70 else "#ef4444"

    fail_rows = ""
    for f in kpi["failures"][:10]:
        badge = f'<span style="background:rgba(239,68,68,.2);color:#ef4444;font-size:11px;font-weight:700;padding:2px 7px;border-radius:4px">{f["status"].upper()}</span>'
        msg   = f["message"][:80].replace("<", "&lt;").replace(">", "&gt;")
        fail_rows += f"""
        <tr>
          <td style="font-family:monospace;font-size:12px">{f['test_class']}</td>
          <td style="font-size:12px">{f['name'][:45]}</td>
          <td>{badge}</td>
          <td style="color:#94a3b8;font-size:12px;max-width:300px;word-break:break-word">{msg}</td>
        </tr>"""

    flaky_rows = ""
    for key, info in list(kpi["flaky_data"].items())[:8]:
        score_pct = int(info["score"] * 100)
        color     = "#ef4444" if score_pct >= 75 else "#f59e0b"
        flaky_rows += f"""
        <tr>
          <td style="font-family:monospace;font-size:12px">{key}</td>
          <td><span style="background:rgba(245,158,11,.2);color:#f59e0b;font-size:11px;padding:2px 7px;border-radius:4px">{info.get('pattern','?')}</span></td>
          <td><div style="background:#334155;border-radius:4px;height:8px;width:100px;display:inline-block;overflow:hidden;vertical-align:middle"><div style="background:{color};width:{score_pct}%;height:100%"></div></div> {score_pct}%</td>
        </tr>"""

    if not flaky_rows:
        flaky_rows = '<tr><td colspan="3" style="text-align:center;color:#10b981;padding:16px">✓ Aucun test flaky détecté</td></tr>'

    html = f"""<!DOCTYPE html>
<html lang="fr"><head>
<meta charset="UTF-8">
<title>QA KPI Dashboard — Mobile</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{--bg:#0f172a;--card:#1e293b;--border:#334155;--text:#e2e8f0;--muted:#94a3b8;--accent:#6366f1;--green:#10b981;--red:#ef4444;--yellow:#f59e0b;--blue:#3b82f6}}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh}}
  .header{{background:linear-gradient(135deg,#1e293b 0%,#0f172a 100%);border-bottom:1px solid var(--border);padding:24px 32px;display:flex;align-items:center;justify-content:space-between}}
  .header h1{{font-size:22px;font-weight:700;color:#fff}}.header h1 span{{color:var(--accent)}}
  .header-meta{{text-align:right;color:var(--muted);font-size:13px;line-height:1.6}}
  .badge-live{{background:var(--green);color:#fff;font-size:11px;padding:2px 10px;border-radius:999px;font-weight:600;margin-left:10px}}
  .main{{padding:28px 32px;max-width:1400px;margin:0 auto}}
  .kpi-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:28px}}
  .kpi-card{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px;position:relative;overflow:hidden}}
  .kpi-card::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--kpi-color,var(--accent))}}
  .kpi-label{{font-size:12px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px}}
  .kpi-value{{font-size:36px;font-weight:800;color:var(--kpi-color,#fff);line-height:1}}
  .kpi-sub{{font-size:12px;color:var(--muted);margin-top:6px}}
  .kpi-icon{{position:absolute;right:16px;top:16px;font-size:28px;opacity:.15}}
  .charts-grid{{display:grid;grid-template-columns:1fr 2fr;gap:20px;margin-bottom:28px}}
  .chart-card{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px}}
  .chart-title{{font-size:14px;font-weight:600;color:var(--text);margin-bottom:16px;display:flex;align-items:center;gap:8px}}
  .chart-title::before{{content:'';display:inline-block;width:3px;height:16px;background:var(--accent);border-radius:2px}}
  .table-card{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px;margin-bottom:20px}}
  table{{width:100%;border-collapse:collapse;font-size:13px}}
  th{{text-align:left;padding:10px 12px;font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid var(--border)}}
  td{{padding:10px 12px;border-bottom:1px solid #1e293b;color:var(--text);vertical-align:middle}}
  tr:last-child td{{border-bottom:none}}
  tr:hover td{{background:rgba(99,102,241,.06)}}
  .section-title{{font-size:16px;font-weight:700;color:#fff;margin-bottom:16px;padding-bottom:8px;border-bottom:1px solid var(--border)}}
  .gate-banner{{border-radius:12px;padding:20px 28px;margin-bottom:28px;display:flex;align-items:center;justify-content:space-between;border:1px solid}}
  .gate-banner.passed{{background:rgba(16,185,129,.1);border-color:rgba(16,185,129,.4)}}
  .gate-banner.failed{{background:rgba(239,68,68,.1);border-color:rgba(239,68,68,.4)}}
  .gate-verdict{{font-size:32px;font-weight:900}}.gate-verdict.passed{{color:#10b981}}.gate-verdict.failed{{color:#ef4444}}
  .gate-label{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:4px}}
  .gate-score{{font-size:18px;font-weight:700;color:var(--text)}}
  .gate-criteria{{display:flex;flex-direction:column;gap:6px}}
  .gate-row{{display:flex;align-items:center;gap:10px;font-size:13px}}
  .gate-dot{{width:10px;height:10px;border-radius:50%;flex-shrink:0}}
  .gate-dot.ok{{background:#10b981}}.gate-dot.ko{{background:#ef4444}}
  .gate-name{{color:var(--text)}}.gate-val{{color:var(--muted);margin-left:auto;font-size:12px;font-weight:600}}
  .footer{{text-align:center;padding:24px;color:var(--muted);font-size:12px;border-top:1px solid var(--border);margin-top:12px}}
  .footer strong{{color:var(--accent)}}
</style>
</head><body>

<div class="header">
  <div>
    <h1>📱 QA <span>KPI</span> Dashboard Mobile <span class="badge-live">LIVE</span></h1>
    <div style="color:var(--muted);font-size:13px;margin-top:4px">{kpi["app_under_test"]}</div>
  </div>
  <div class="header-meta">
    <div>{kpi["framework"]}</div>
    <div>LLM · {kpi["llm"]}</div>
    <div>Généré le {kpi["generated_at"]}</div>
  </div>
</div>

<div class="main">
  {_gate_banner(kpi)}

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
      <div class="kpi-sub">{kpi['flaky_count']} tests instables</div>
    </div>
    <div class="kpi-card" style="--kpi-color:{rate_color(kpi['coverage'])}">
      <div class="kpi-icon">🤖</div>
      <div class="kpi-label">Couverture Automation</div>
      <div class="kpi-value">{kpi['coverage']}%</div>
      <div class="kpi-sub">{s['total']} / {kpi['total_tcs']} TCs définis</div>
    </div>
    <div class="kpi-card" style="--kpi-color:#6366f1">
      <div class="kpi-icon">⏱️</div>
      <div class="kpi-label">Temps d'exécution</div>
      <div class="kpi-value" style="font-size:28px">{kpi['exec_time_fmt']}</div>
      <div class="kpi-sub">Moy. par test : {kpi['avg_time_fmt']}</div>
    </div>
    <div class="kpi-card" style="--kpi-color:#3b82f6">
      <div class="kpi-icon">📱</div>
      <div class="kpi-label">Tests Mobile</div>
      <div class="kpi-value">{s['total']}</div>
      <div class="kpi-sub">Smoke · Regression · Quarantine</div>
    </div>
    <div class="kpi-card" style="--kpi-color:#8b5cf6">
      <div class="kpi-icon">🏃</div>
      <div class="kpi-label">Runs Historiques</div>
      <div class="kpi-value">{len(kpi['trend'])}</div>
      <div class="kpi-sub">Exécutions tracées dans Allure</div>
    </div>
  </div>

  <div class="charts-grid">
    <div class="chart-card">
      <div class="chart-title">Distribution des résultats</div>
      <canvas id="donutChart" style="max-height:280px"></canvas>
    </div>
    <div class="chart-card">
      <div class="chart-title">Résultats par groupe TestNG</div>
      <canvas id="groupChart" style="max-height:280px"></canvas>
    </div>
  </div>

  <div class="table-card" style="margin-bottom:28px">
    <div class="chart-title">Évolution de la qualité</div>
    <canvas id="trendChart" style="max-height:220px"></canvas>
  </div>

  <div class="section-title">Tests en échec</div>
  <div class="table-card">
    <table>
      <thead><tr><th>Classe</th><th>Méthode</th><th>Statut</th><th>Message</th></tr></thead>
      <tbody>{fail_rows if fail_rows else '<tr><td colspan="4" style="text-align:center;color:#10b981;padding:16px">✓ Aucun test en échec</td></tr>'}</tbody>
    </table>
  </div>

  <div class="section-title">Tests Flaky</div>
  <div class="table-card">
    <table>
      <thead><tr><th>Test</th><th>Pattern détecté</th><th>Score instabilité</th></tr></thead>
      <tbody>{flaky_rows}</tbody>
    </table>
  </div>
</div>

<div class="footer">
  Généré par <strong>kpi-agent.py</strong> · App <strong>{kpi["app_under_test"]}</strong> · LLM <strong>{kpi["llm"]}</strong> · {kpi["generated_at"]}
</div>

<script>
const C = {{green:'#10b981',red:'#ef4444',yellow:'#f59e0b',blue:'#3b82f6',purple:'#8b5cf6',muted:'#475569'}};
new Chart(document.getElementById('donutChart'),{{
  type:'doughnut',
  data:{{labels:['Passés','Échoués','Broken','Skipped'],
    datasets:[{{data:[{s['passed']},{s['failed']},{s['broken']},{s['skipped']}],
    backgroundColor:[C.green,C.red,C.yellow,C.muted],borderWidth:0,hoverOffset:6}}]}},
  options:{{cutout:'70%',plugins:{{legend:{{position:'bottom',labels:{{color:'#94a3b8',padding:14,font:{{size:12}}}}}}}}}}
}});
new Chart(document.getElementById('groupChart'),{{
  type:'bar',
  data:{{labels:{json.dumps(grp_labels)},
    datasets:[
      {{label:'Passés',data:{json.dumps(grp_pass)},backgroundColor:C.green,borderRadius:4}},
      {{label:'Échoués',data:{json.dumps(grp_fail)},backgroundColor:C.red,borderRadius:4}}
    ]}},
  options:{{responsive:true,plugins:{{legend:{{labels:{{color:'#94a3b8'}}}}}},
    scales:{{x:{{stacked:true,ticks:{{color:'#94a3b8'}},grid:{{color:'#1e293b'}}}},
             y:{{stacked:true,ticks:{{color:'#94a3b8',stepSize:1}},grid:{{color:'#1e293b'}}}}}}}}
}});
new Chart(document.getElementById('trendChart'),{{
  type:'line',
  data:{{labels:{json.dumps(trend_labels)},
    datasets:[
      {{label:'Passés',data:{json.dumps(trend_pass)},borderColor:C.green,backgroundColor:'rgba(16,185,129,.15)',fill:true,tension:.4,pointRadius:5}},
      {{label:'Échoués',data:{json.dumps(trend_fail)},borderColor:C.red,backgroundColor:'rgba(239,68,68,.1)',fill:true,tension:.4,pointRadius:5}}
    ]}},
  options:{{responsive:true,plugins:{{legend:{{labels:{{color:'#94a3b8'}}}}}},
    scales:{{x:{{ticks:{{color:'#94a3b8'}},grid:{{color:'#1e293b'}}}},
             y:{{ticks:{{color:'#94a3b8',stepSize:1}},grid:{{color:'#1e293b'}},min:0}}}}}}
}});
</script>
</body></html>"""

    with open(DASH_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"{G}  [OK] KPI Dashboard → docs/kpi-dashboard.html{E}")


# ── Résumé console ─────────────────────────────────────────────────────────

def print_summary(kpi: dict):
    s       = kpi["stats"]
    verdict = kpi["gate_verdict"]
    gcolor  = G if verdict == "PASSED" else R
    print(f"\n{W}{'='*55}{E}")
    print(f"{W}  QA KPI MOBILE — {kpi['generated_at']}{E}")
    print(f"{W}{'='*55}{E}")
    print(f"\n  QUALITY GATE : {gcolor}{W} {verdict} {E}  ({len(kpi['gate_passed'])}/{len(kpi['gate'])} critères)")
    for name, ok, val in kpi["gate"]:
        sym = f"{G}✓{E}" if ok else f"{R}✗{E}"
        print(f"  {sym}  {name:<40} {val}")
    print()
    def row(lbl, val, color=None):
        c = color or E
        print(f"  {lbl:<35} {c}{str(val):>12}{E}")
    row("Pass Rate",             f"{kpi['pass_rate']}%",    G if kpi['pass_rate'] >= 85 else R)
    row("Fail Rate",             f"{kpi['fail_rate']}%",    G if kpi['fail_rate'] == 0  else R)
    row("Taux d'anomalies",      f"{kpi['anomaly_rate']}%", G if kpi['anomaly_rate']==0 else Y)
    row("Flaky Rate",            f"{kpi['flaky_rate']}%",   G if kpi['flaky_count']==0  else Y)
    row("Couverture Automation",  f"{kpi['coverage']}%",    G)
    row("Tests exécutés",         s['total'],                C)
    row("Passés / Échoués",      f"{s['passed']} / {s['failed']}", C)
    row("Temps d'exécution",      kpi['exec_time_fmt'],     C)
    print(f"\n  Framework  : {kpi['framework']}")
    print(f"  App testée : {kpi['app_under_test']}")
    print(f"  LLM Engine : {kpi['llm']}\n")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    print(f"\n{C}[KPI Agent Mobile] Collecte des données depuis target/allure-results/...{E}")
    kpi = collect_kpis()
    if cmd in ("all", "env"):
        write_env_properties(kpi)
    if cmd in ("all", "dashboard"):
        write_dashboard(kpi)
    if cmd in ("all", "summary"):
        print_summary(kpi)
    if cmd == "all":
        print(f"\n{G}  Done. Pour voir l'ENVIRONMENT widget dans Allure :{E}")
        print(f"  allure generate target/allure-results -o target/allure-report --clean\n")
