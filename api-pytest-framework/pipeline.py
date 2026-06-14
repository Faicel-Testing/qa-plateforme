"""
Pipeline complet QA — exécute tous les agents dans l'ordre puis ouvre le dashboard.

Usage:
    python pipeline.py              → pipeline complet (gherkin + tests + IA + dashboard)
    python pipeline.py --skip-tests → pipeline IA seul (réutilise allure-results existants)
    python pipeline.py --suite auth → une seule suite BDD
    python pipeline.py --no-browser → ne pas ouvrir le browser automatiquement
"""

import subprocess, sys, os, time, json, glob, webbrowser, datetime

SKIP_TESTS  = "--skip-tests"  in sys.argv
NO_BROWSER  = "--no-browser"  in sys.argv
SUITE       = next((sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--suite"), "all")

ROOT     = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(ROOT, "docs")
PY       = sys.executable

G = "\033[32m"; Y = "\033[33m"; R = "\033[31m"
C = "\033[36m"; W = "\033[1m";  E = "\033[0m"

STEPS = {}          # label → bool (success)
TIMINGS = {}        # label → float (seconds)


# ── Exécution d'une étape ──────────────────────────────────────────────────────

def run(label, cmd, *, required=False):
    print(f"\n{W}{'─'*60}{E}")
    print(f"{C}  ▶  {label}{E}")
    print(f"{W}{'─'*60}{E}")
    t0 = time.time()
    rc = subprocess.run(cmd, cwd=ROOT).returncode
    elapsed = time.time() - t0
    TIMINGS[label] = elapsed
    ok = rc == 0
    STEPS[label] = ok
    if ok:
        print(f"{G}  ✓  {label}  ({elapsed:.1f}s){E}")
    else:
        print(f"{R}  ✗  {label} — code {rc}  ({elapsed:.1f}s){E}")
        if required:
            print(f"{R}  Étape critique — arrêt du pipeline.{E}")
            sys.exit(rc)
    return ok


# ── Lecture des résultats Allure pour le dashboard ────────────────────────────

def read_allure_stats() -> dict:
    stats = {"passed": 0, "failed": 0, "broken": 0, "skipped": 0, "total": 0}
    for f in glob.glob(os.path.join(ROOT, "allure-results", "*-result.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
            s = d.get("status", "unknown")
            if s in stats:
                stats[s] += 1
            stats["total"] += 1
        except Exception:
            pass
    stats["pass_rate"] = round(stats["passed"] / stats["total"] * 100, 1) if stats["total"] else 0.0
    return stats


# ── Génération du dashboard maître ────────────────────────────────────────────

def build_dashboard(total_elapsed: float) -> str:
    os.makedirs(DOCS_DIR, exist_ok=True)
    stats   = read_allure_stats()
    now     = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    passed  = sum(1 for v in STEPS.values() if v)
    total   = len(STEPS)

    # Cartes métriques tests
    rate_color = "#43e97b" if stats["pass_rate"] >= 90 else "#fcd34d" if stats["pass_rate"] >= 70 else "#ef4444"

    # Lignes du tableau des étapes
    step_rows = ""
    for label, ok in STEPS.items():
        icon  = "✓" if ok else "✗"
        color = "#43e97b" if ok else "#ef4444"
        t     = TIMINGS.get(label, 0)
        step_rows += f"""
        <tr>
          <td style="color:{color};font-size:16px;text-align:center">{icon}</td>
          <td style="color:#e2e8f0">{label}</td>
          <td style="color:#94a3b8;text-align:right">{t:.1f}s</td>
        </tr>"""

    # Liens vers les rapports individuels
    reports = [
        ("kpi-dashboard.html",   "KPI Dashboard",       "📊"),
        ("triage-report.html",   "Triage des échecs",   "🔍"),
        ("rca-report.html",      "Root Cause Analysis", "🧠"),
        ("release-report.html",  "Go / No-Go Release",  "🚀"),
        ("qa-report.html",       "Qualité BDD",         "✅"),
    ]
    cards = ""
    for filename, title, icon in reports:
        filepath = os.path.join(DOCS_DIR, filename)
        exists   = os.path.exists(filepath)
        href     = filename if exists else "#"
        opacity  = "1" if exists else "0.35"
        badge    = "" if exists else "<span style='font-size:10px;color:#64748b;margin-left:6px'>non généré</span>"
        cards += f"""
        <a href="{href}" style="text-decoration:none;opacity:{opacity}" {'target="_blank"' if exists else ''}>
          <div class="report-card">
            <div style="font-size:28px;margin-bottom:8px">{icon}</div>
            <div style="font-weight:700;color:#e2e8f0;font-size:14px">{title}{badge}</div>
            <div style="font-size:11px;color:#64748b;margin-top:4px">{filename}</div>
          </div>
        </a>"""

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="0; url=pipeline-dashboard.html">
<title>Pipeline QA — Dashboard</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0 }}
  body {{
    font-family: 'Segoe UI', sans-serif;
    background: #0f1117;
    color: #e2e8f0;
    padding: 32px;
    line-height: 1.6;
  }}
  .header {{
    background: linear-gradient(135deg, #1a1d27, #1e2130);
    border: 1px solid #2a2d3e;
    border-radius: 16px;
    padding: 28px 32px;
    margin-bottom: 28px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .header h1 {{ font-size: 22px; font-weight: 800; color: #a78bfa }}
  .header .meta {{ font-size: 12px; color: #64748b; text-align: right }}
  .metrics {{
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 14px;
    margin-bottom: 28px;
  }}
  .metric {{
    background: #1a1d27;
    border: 1px solid #2a2d3e;
    border-radius: 12px;
    padding: 18px;
    text-align: center;
  }}
  .metric .val {{
    font-size: 30px;
    font-weight: 900;
    display: block;
    margin-bottom: 4px;
  }}
  .metric .lbl {{
    font-size: 10px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
  }}
  .section {{
    background: #1a1d27;
    border: 1px solid #2a2d3e;
    border-radius: 12px;
    padding: 22px 26px;
    margin-bottom: 20px;
  }}
  .section h2 {{
    font-size: 14px;
    font-weight: 700;
    color: #7dd3fc;
    margin-bottom: 16px;
    padding-bottom: 10px;
    border-bottom: 1px solid #2a2d3e;
    text-transform: uppercase;
    letter-spacing: 1px;
  }}
  table {{ width: 100%; border-collapse: collapse }}
  td {{ padding: 10px 12px; border-bottom: 1px solid rgba(255,255,255,.05); font-size: 13px }}
  .reports-grid {{
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 14px;
  }}
  .report-card {{
    background: #1a1d27;
    border: 1px solid #2a2d3e;
    border-radius: 12px;
    padding: 20px 16px;
    text-align: center;
    transition: border-color .2s, background .2s;
    cursor: pointer;
  }}
  .report-card:hover {{
    border-color: #a78bfa;
    background: #1e2130;
  }}
  .footer {{
    text-align: center;
    color: #475569;
    font-size: 11px;
    margin-top: 28px;
  }}
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>🧪 Pipeline QA — Dashboard</h1>
    <div style="color:#94a3b8;font-size:13px;margin-top:6px">
      Suite : <strong>{SUITE}</strong> &nbsp;·&nbsp; Durée totale : <strong>{total_elapsed:.0f}s</strong>
    </div>
  </div>
  <div class="meta">
    Généré le {now}<br>
    <span style="color:{'#43e97b' if passed == total else '#fcd34d'}">{passed}/{total} étapes OK</span>
  </div>
</div>

<!-- Métriques tests -->
<div class="metrics">
  <div class="metric">
    <span class="val" style="color:#43e97b">{stats['passed']}</span>
    <span class="lbl">Passed</span>
  </div>
  <div class="metric">
    <span class="val" style="color:#ef4444">{stats['failed']}</span>
    <span class="lbl">Failed</span>
  </div>
  <div class="metric">
    <span class="val" style="color:#fcd34d">{stats['broken']}</span>
    <span class="lbl">Broken</span>
  </div>
  <div class="metric">
    <span class="val" style="color:#94a3b8">{stats['skipped']}</span>
    <span class="lbl">Skipped</span>
  </div>
  <div class="metric">
    <span class="val" style="color:{rate_color}">{stats['pass_rate']}%</span>
    <span class="lbl">Pass Rate</span>
  </div>
</div>

<!-- Étapes du pipeline -->
<div class="section">
  <h2>Étapes du pipeline</h2>
  <table>
    <tr>
      <th style="width:40px"></th>
      <th style="text-align:left;color:#7dd3fc;font-size:11px;letter-spacing:1px">ÉTAPE</th>
      <th style="text-align:right;color:#7dd3fc;font-size:11px;letter-spacing:1px">DURÉE</th>
    </tr>
    {step_rows}
  </table>
</div>

<!-- Rapports individuels -->
<div class="section">
  <h2>Rapports détaillés</h2>
  <div class="reports-grid">
    {cards}
  </div>
</div>

<div class="footer">
  pipeline.py · api-pytest-framework · {now}
</div>

</body>
</html>"""

    out = os.path.join(DOCS_DIR, "pipeline-dashboard.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    return out


# ── Pipeline principal ────────────────────────────────────────────────────────

def main():
    total_start = time.time()

    print(f"\n{W}{'='*60}{E}")
    print(f"{W}  PIPELINE QA — api-pytest-framework{E}")
    print(f"{W}  Suite : {SUITE}  |  Skip tests : {SKIP_TESTS}{E}")
    print(f"{W}{'='*60}{E}")

    # 1. Vérification Gherkin
    run("Vérification Gherkin (verifier-agent)",
        [PY, "agents/verifier-agent.py", "gherkin"])

    # 2. Tests BDD
    if not SKIP_TESTS:
        os.makedirs(os.path.join(ROOT, "allure-results"), exist_ok=True)
        if SUITE == "all":
            test_cmd = [PY, "-m", "pytest", "tests/", "-v",
                        "--alluredir=allure-results", "--tb=short", "-q"]
        else:
            test_cmd = [PY, "-m", "pytest", f"tests/test_{SUITE}_bdd.py",
                        "-v", "--alluredir=allure-results", "--tb=short"]
        run(f"Tests BDD (suite={SUITE})", test_cmd)
    else:
        print(f"\n{Y}  ⚡  Tests ignorés (--skip-tests){E}")
        STEPS[f"Tests BDD (suite={SUITE})"] = True
        TIMINGS[f"Tests BDD (suite={SUITE})"] = 0.0

    # 3. KPI dashboard
    run("KPI Dashboard (kpi-agent)",
        [PY, "agents/kpi-agent.py"])

    # 4. Triage — mode rapport HTML
    run("Triage des échecs (triage-agent)",
        [PY, "agents/triage-agent.py", "report"])

    # 5. RCA — Root Cause Analysis
    run("Root Cause Analysis (rca-agent)",
        [PY, "agents/rca-agent.py", "analyse"])

    # 6. Tickets Jira
    run("Création tickets Jira (jira-ticket-agent)",
        [PY, "agents/jira-ticket-agent.py"])

    # 7. Go/No-Go
    run("Go/No-Go release (release-advisor-agent)",
        [PY, "agents/release-advisor-agent.py"])

    # ── Dashboard maître ──────────────────────────────────────────────
    total_elapsed = time.time() - total_start
    dashboard = build_dashboard(total_elapsed)

    passed = sum(1 for v in STEPS.values() if v)
    total  = len(STEPS)

    print(f"\n{W}{'='*60}{E}")
    print(f"{W}  PIPELINE TERMINÉ  —  {total_elapsed:.0f}s{E}")
    print(f"{W}{'='*60}{E}")
    for label, ok in STEPS.items():
        icon = f"{G}✓{E}" if ok else f"{R}✗{E}"
        print(f"  {icon}  {label}  ({TIMINGS.get(label,0):.1f}s)")
    print(f"\n  {G if passed == total else Y}{passed}/{total} étapes réussies{E}")
    print(f"\n  {C}Dashboard → {dashboard}{E}\n")

    if not NO_BROWSER:
        webbrowser.open(f"file:///{dashboard.replace(os.sep, '/')}")


if __name__ == "__main__":
    main()
