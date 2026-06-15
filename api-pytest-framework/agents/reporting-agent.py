# ============================================================
# Reporting Agent — Allure · Notifications · Publication
# ============================================================
# Absorbe : report-agent · api-reporter-agent · notification-agent
#
# Commandes :
#   python agents/reporting-agent.py generate   → génère le rapport Allure HTML
#   python agents/reporting-agent.py serve      → lance un serveur HTTP local
#   python agents/reporting-agent.py open       → ouvre le rapport dans le navigateur
#   python agents/reporting-agent.py notify     → envoie le résumé Slack/Teams
#   python agents/reporting-agent.py publish    → génère + notifie (pipeline complet)
# ============================================================

import sys, os, json, glob, subprocess, re, time, webbrowser, http.server, threading, requests
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm

FRAMEWORK   = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS_DIR = os.path.join(FRAMEWORK, "allure-results")
REPORT_DIR  = os.path.join(FRAMEWORK, "allure-report")
DOCS_DIR    = os.path.join(FRAMEWORK, "docs")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

SLACK_WEBHOOK  = os.getenv("SLACK_WEBHOOK_URL", "")
TEAMS_WEBHOOK  = os.getenv("TEAMS_WEBHOOK_URL", "")
ALLURE_CMD     = os.getenv("ALLURE_CMD", "allure")
DEFAULT_PORT   = 8080


# ── Helpers ────────────────────────────────────────────────────────────────

def collect_results() -> dict:
    stats    = {"passed": 0, "failed": 0, "broken": 0, "skipped": 0, "total": 0}
    failures = []
    for f in glob.glob(os.path.join(RESULTS_DIR, "*-result.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
            s = d.get("status", "unknown")
            if s in stats:
                stats[s] += 1
            stats["total"] += 1
            if s in ("failed", "broken"):
                tags   = [lb["value"] for lb in d.get("labels", []) if lb["name"] == "tag"]
                tc     = next((t for t in tags if re.match(r"tc-\d+", t)), None)
                msg    = (d.get("statusDetails") or {}).get("message", "")[:100]
                failures.append({"name": d.get("name", "?"), "tc": tc, "message": msg})
        except Exception:
            pass
    total = stats["total"] or 1
    return {
        "stats": stats,
        "failures": failures,
        "pass_rate": round(stats["passed"] / total * 100, 1),
        "fail_rate": round((stats["failed"] + stats["broken"]) / total * 100, 1),
    }


def allure_available() -> bool:
    try:
        result = subprocess.run([ALLURE_CMD, "--version"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


# ── Generate ───────────────────────────────────────────────────────────────

def cmd_generate() -> bool:
    print(f"\n{W}REPORTING AGENT — Generate Allure Report{E}\n")

    if not os.path.exists(RESULTS_DIR) or not glob.glob(os.path.join(RESULTS_DIR, "*-result.json")):
        print(f"{Y}  [WARN] Aucun resultat dans allure-results. Executez les tests d'abord.{E}")
        return False

    result_count = len(glob.glob(os.path.join(RESULTS_DIR, "*-result.json")))
    print(f"  {result_count} resultats Allure trouves")

    if not allure_available():
        print(f"{Y}  [WARN] Allure CLI introuvable. Rapport non genere.{E}")
        print(f"  Installez Allure : npm install -g allure-commandline")
        return False

    os.makedirs(REPORT_DIR, exist_ok=True)
    cmd = [ALLURE_CMD, "generate", RESULTS_DIR, "--output", REPORT_DIR, "--clean"]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")

    if result.returncode == 0:
        index = os.path.join(REPORT_DIR, "index.html")
        print(f"  {G}Rapport genere : {REPORT_DIR}/index.html{E}")
        return True
    else:
        print(f"  {R}Erreur Allure : {result.stderr[:200]}{E}")
        return False


# ── Serve ──────────────────────────────────────────────────────────────────

def cmd_serve(port: int = DEFAULT_PORT):
    index = os.path.join(REPORT_DIR, "index.html")
    if not os.path.exists(index):
        print(f"{Y}  Rapport non trouve. Generation en cours...{E}")
        if not cmd_generate():
            return

    print(f"\n{W}REPORTING AGENT — Serve (http://localhost:{port}){E}")
    print(f"  {G}Rapport disponible sur : http://localhost:{port}/index.html{E}")
    print(f"  {Y}Ctrl+C pour arreter{E}\n")

    os.chdir(REPORT_DIR)
    handler = http.server.SimpleHTTPRequestHandler
    with http.server.HTTPServer(("", port), handler) as httpd:
        webbrowser.open(f"http://localhost:{port}/index.html", new=2)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print(f"\n{Y}  Serveur arrete.{E}")


# ── Open ───────────────────────────────────────────────────────────────────

def cmd_open():
    index = os.path.join(REPORT_DIR, "index.html")
    if not os.path.exists(index):
        print(f"{Y}  Rapport non trouve. Generation en cours...{E}")
        cmd_generate()
    if os.path.exists(index):
        webbrowser.open(f"file://{index.replace(os.sep, '/')}")
        print(f"  {G}Rapport ouvert dans le navigateur.{E}")
    else:
        print(f"  {R}Impossible d'ouvrir le rapport.{E}")


# ── Notify — Slack/Teams ───────────────────────────────────────────────────

def cmd_notify(channel: str = "auto"):
    print(f"\n{W}REPORTING AGENT — Notify{E}\n")

    data = collect_results()
    s    = data["stats"]

    # Générer le résumé narratif via LLM
    failures_text = "\n".join([f"- [{f['tc'] or '?'}] {f['name']}: {f['message']}" for f in data["failures"][:5]])
    messages = [{"role": "user", "content": (
        f"Génère un résumé de run QA pour Slack (max 3 lignes, en français, sans emojis excessifs).\n\n"
        f"Résultats : {s['total']} tests | Pass: {s['passed']} ({data['pass_rate']}%) | "
        f"Fail: {s['failed']} | Broken: {s['broken']}\n"
        f"{'Echecs principaux:\n' + failures_text if data['failures'] else 'Aucun echec.'}\n\n"
        f"Inclure : verdict GO/NO-GO, pass rate, action recommandée si echec."
    )}]
    summary = llm.chat(messages)
    gate = data["pass_rate"] >= 90.0 and data["fail_rate"] <= 5.0
    verdict = "GO" if gate else "NO-GO"

    print(f"  Verdict : {G if gate else R}{verdict}{E} | Pass: {data['pass_rate']}%")
    print(f"\n{W}  Message :{E}")
    for line in summary.strip().split("\n"):
        print(f"  {line}")

    webhook_url = None
    if channel == "slack" or (channel == "auto" and SLACK_WEBHOOK):
        webhook_url = SLACK_WEBHOOK
        channel_name = "Slack"
    elif channel == "teams" or (channel == "auto" and TEAMS_WEBHOOK):
        webhook_url = TEAMS_WEBHOOK
        channel_name = "Teams"

    if not webhook_url:
        print(f"\n{Y}  [WARN] Aucun webhook configure (SLACK_WEBHOOK_URL / TEAMS_WEBHOOK_URL).{E}")
        print(f"  Message pret — ajoutez le webhook dans .env pour l'envoyer.")
        return

    payload = {
        "text": f"*QA Run — {verdict}* ({data['pass_rate']}%)\n{summary}",
        "attachments": [{
            "color": "#27ae60" if gate else "#e74c3c",
            "fields": [
                {"title": "Total", "value": str(s["total"]), "short": True},
                {"title": "Pass",  "value": f"{s['passed']} ({data['pass_rate']}%)", "short": True},
                {"title": "Fail",  "value": str(s["failed"]), "short": True},
                {"title": "Verdict", "value": verdict, "short": True},
            ]
        }]
    }
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code == 200:
            print(f"\n  {G}Notification envoyee sur {channel_name}.{E}")
        else:
            print(f"\n  {R}Erreur webhook {resp.status_code} : {resp.text[:100]}{E}")
    except Exception as ex:
        print(f"\n  {R}Erreur reseau : {ex}{E}")


# ── Publish — Pipeline complet ─────────────────────────────────────────────

def cmd_publish():
    print(f"\n{W}REPORTING AGENT — Publish (generate + notify){E}\n")
    generated = cmd_generate()
    if generated:
        print(f"\n{G}  Rapport genere avec succes.{E}")
    cmd_notify()


# ── Main ───────────────────────────────────────────────────────────────────

def print_help():
    print(f"""
{W}REPORTING AGENT — Allure · Notifications · Publication{E}

  python agents/reporting-agent.py generate      Génère le rapport Allure HTML
  python agents/reporting-agent.py serve         Lance un serveur HTTP local (port {DEFAULT_PORT})
  python agents/reporting-agent.py open          Ouvre le rapport dans le navigateur
  python agents/reporting-agent.py notify        Envoie le résumé sur Slack/Teams
  python agents/reporting-agent.py notify slack  Force l'envoi Slack
  python agents/reporting-agent.py notify teams  Force l'envoi Teams
  python agents/reporting-agent.py publish       Generate + notify (pipeline complet)

{W}Variables d'environnement :{E}
  SLACK_WEBHOOK_URL   Webhook Slack entrant
  TEAMS_WEBHOOK_URL   Webhook Teams entrant
  ALLURE_CMD          Chemin vers allure CLI (defaut: allure)

{W}Modules absorbes :{E} report-agent · api-reporter-agent · notification-agent
""")


if __name__ == "__main__":
    port_arg = int(next((a.split("=")[1] for a in sys.argv if a.startswith("--port=")), str(DEFAULT_PORT)))
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    sub = sys.argv[2] if len(sys.argv) > 2 else "auto"

    if cmd == "generate":
        cmd_generate()
    elif cmd == "serve":
        cmd_serve(port_arg)
    elif cmd == "open":
        cmd_open()
    elif cmd == "notify":
        cmd_notify(sub)
    elif cmd == "publish":
        cmd_publish()
    else:
        print_help()
