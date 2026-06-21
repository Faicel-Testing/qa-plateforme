# ============================================================
# Reporting Agent — Allure · KPI · Notifications · Jira
# ============================================================
# Commandes :
#   python agents/reporting-agent.py generate    → génère rapport Allure HTML
#   python agents/reporting-agent.py serve       → ouvre Allure dans le navigateur
#   python agents/reporting-agent.py notify      → notification Slack/Teams
#   python agents/reporting-agent.py dashboard   → KPI dashboard HTML
#   python agents/reporting-agent.py publish     → generate + notify
# ============================================================

import sys, os, json, glob, subprocess, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ALLURE = "allure.cmd" if sys.platform == "win32" else "allure"
MVN    = "mvn.cmd"    if sys.platform == "win32" else "mvn"
sys.path.insert(0, os.path.dirname(__file__))

import llm
from prompt_store import PromptStore

_ps = PromptStore()

FRAMEWORK  = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TARGET_DIR = os.path.join(FRAMEWORK, "target")
ALLURE_DIR = os.path.join(TARGET_DIR, "allure-results")
REPORT_DIR = os.path.join(TARGET_DIR, "allure-report")
DOCS_DIR   = os.path.join(FRAMEWORK, "docs")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

SLACK_WEBHOOK  = os.environ.get("SLACK_WEBHOOK_URL", "")
TEAMS_WEBHOOK  = os.environ.get("TEAMS_WEBHOOK_URL", "")


def load_stats() -> dict:
    results = []
    for f in glob.glob(os.path.join(ALLURE_DIR, "*.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            if "name" in data and "status" in data:
                results.append(data)
        except Exception:
            pass
    total   = len(results)
    passed  = sum(1 for r in results if r.get("status") == "passed")
    failed  = sum(1 for r in results if r.get("status") == "failed")
    broken  = sum(1 for r in results if r.get("status") == "broken")
    skipped = sum(1 for r in results if r.get("status") == "skipped")
    pass_rate = round(passed / total * 100, 1) if total else 0
    fail_rate = round((failed + broken) / total * 100, 1) if total else 0
    return dict(total=total, passed=passed, failed=failed, broken=broken,
                skipped=skipped, pass_rate=pass_rate, fail_rate=fail_rate)


def cmd_generate():
    print(f"\n{W}REPORTING — Génération rapport Allure{E}")
    rc = subprocess.run(
        [ALLURE, "generate", ALLURE_DIR, "--output", REPORT_DIR, "--clean"],
        cwd=FRAMEWORK
    )
    if rc.returncode == 0:
        print(f"  {G}Rapport généré : target/allure-report/{E}")
    else:
        print(f"  {Y}Allure CLI non disponible. Fallback → mvn allure:report{E}")
        subprocess.run([MVN, "allure:report"], cwd=FRAMEWORK)
    return rc.returncode


def cmd_serve():
    print(f"\n{W}REPORTING — Ouverture rapport Allure{E}")
    subprocess.Popen(
        [ALLURE, "open", REPORT_DIR],
        cwd=FRAMEWORK
    )
    print(f"  {G}Rapport ouvert dans le navigateur.{E}")


def cmd_dashboard():
    print(f"\n{W}REPORTING — Dashboard KPI HTML{E}")
    stats = load_stats()
    gate_ok = stats["pass_rate"] >= 90 and stats["fail_rate"] <= 5
    gate_color = "#2ecc71" if gate_ok else "#e74c3c"

    html = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<title>Reporting Dashboard — ui_selenium_bdd</title>
<style>
body{{background:#0d1117;color:#c9d1d9;font-family:'Segoe UI',sans-serif;margin:0;padding:20px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin:20px 0}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:18px;text-align:center}}
.metric{{font-size:2.2em;font-weight:bold;margin:8px 0}}
.label{{color:#8b949e;font-size:.8em;text-transform:uppercase;letter-spacing:1px}}
.gate{{padding:16px;text-align:center;font-size:1.4em;font-weight:bold;
       background:{gate_color}22;border:2px solid {gate_color};border-radius:12px;color:{gate_color}}}
h1{{color:#58a6ff;border-bottom:1px solid #30363d;padding-bottom:10px}}
</style></head><body>
<h1>📊 Reporting Dashboard — Selenium BDD</h1>
<p style="color:#8b949e">automationexercise.com · {time.strftime('%Y-%m-%d %H:%M')}</p>
<div class="gate">{'✅ QUALITY GATE : PASS' if gate_ok else '❌ QUALITY GATE : FAIL'}</div>
<div class="grid">
  <div class="card"><div class="metric" style="color:#58a6ff">{stats['total']}</div><div class="label">Tests</div></div>
  <div class="card"><div class="metric" style="color:#2ecc71">{stats['passed']}</div><div class="label">Passés</div></div>
  <div class="card"><div class="metric" style="color:#e74c3c">{stats['failed']}</div><div class="label">Échoués</div></div>
  <div class="card"><div class="metric" style="color:#f39c12">{stats['broken']}</div><div class="label">Brisés</div></div>
  <div class="card"><div class="metric" style="color:{gate_color}">{stats['pass_rate']}%</div><div class="label">Pass Rate</div></div>
  <div class="card"><div class="metric" style="color:{gate_color}">{stats['fail_rate']}%</div><div class="label">Fail Rate</div></div>
</div></body></html>"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, "reporting-dashboard.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  {G}Dashboard : docs/reporting-dashboard.html{E}")


def cmd_notify(channel: str = "slack"):
    print(f"\n{W}REPORTING — Notification {channel.upper()}{E}")
    stats = load_stats()
    gate_ok = stats["pass_rate"] >= 90 and stats["fail_rate"] <= 5

    _tpl = _ps.get("qa_notify") or (
        "Rédige une notification QA courte pour ce run Selenium BDD :\n\n"
        "Pass rate : {pass_rate}% ({passed}/{total})\n"
        "Échecs    : {failed_count}\n"
        "Gate      : {'PASS' if gate_ok else 'FAIL'}\n\n"
        "Ton professionnel, 2-3 phrases max, inclus les chiffres clés."
    )
    messages = [{"role": "user", "content": _tpl
        .replace("{pass_rate}", str(stats["pass_rate"]))
        .replace("{passed}", str(stats["passed"]))
        .replace("{total}", str(stats["total"]))
        .replace("{failed_count}", str(stats["failed"] + stats["broken"]))
        .replace("{gate_status}", "PASS" if gate_ok else "FAIL")
        .replace("{'PASS' if gate_ok else 'FAIL'}", "PASS" if gate_ok else "FAIL")
    }]
    try:
        narrative = llm.chat(messages)
        _ps.record_usage("qa_notify")
        print(f"\n  {C}Message :{E}\n  {narrative}")
    except Exception as e:
        print(f"  {Y}LLM indisponible : {e}{E}")
        narrative = f"Run Selenium BDD : {stats['pass_rate']}% pass ({stats['passed']}/{stats['total']})"

    # Envoi webhook
    import urllib.request
    webhook = SLACK_WEBHOOK if channel == "slack" else TEAMS_WEBHOOK
    if webhook:
        payload = json.dumps({"text": narrative}).encode("utf-8")
        req = urllib.request.Request(webhook, data=payload,
                                     headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=5)
            print(f"  {G}Notification envoyée ({channel}).{E}")
        except Exception as ex:
            print(f"  {R}Erreur webhook : {ex}{E}")
    else:
        print(f"  {Y}Webhook {channel.upper()} non configuré (SLACK_WEBHOOK_URL / TEAMS_WEBHOOK_URL).{E}")


def cmd_publish():
    print(f"\n{W}REPORTING — Publish (generate + dashboard + notify){E}")
    cmd_generate()
    cmd_dashboard()
    cmd_notify("slack")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reporting Agent — Selenium BDD")
    parser.add_argument("command", choices=["generate", "serve", "notify", "dashboard", "publish"])
    parser.add_argument("channel", nargs="?", default="slack")
    args = parser.parse_args()

    if args.command == "generate":  cmd_generate()
    elif args.command == "serve":   cmd_serve()
    elif args.command == "notify":  cmd_notify(args.channel)
    elif args.command == "dashboard": cmd_dashboard()
    elif args.command == "publish": cmd_publish()
