# ============================================================
# Notification Agent — Mobile (Slack / Teams)
# ============================================================
# Envoie un résumé du run Appium vers Slack ou Teams.
# Le résumé narratif est généré par LLM.
#
# Usage:
#   python agents/notification-agent.py             → Slack
#   python agents/notification-agent.py teams       → Teams
#   python agents/notification-agent.py --dry-run   → affiche sans envoyer
# ============================================================

import sys, os, json, glob
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import requests as _req
import llm

FRAMEWORK   = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS_DIR = os.path.join(FRAMEWORK, "target", "allure-results")
DRY_RUN     = "--dry-run" in sys.argv
TARGET      = "teams" if "teams" in sys.argv else "slack"

from dotenv import load_dotenv
load_dotenv()
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "")
TEAMS_WEBHOOK = os.getenv("TEAMS_WEBHOOK_URL", "")

G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"; R = "\033[31m"; E = "\033[0m"; W = "\033[1m"

SUMMARY_SCHEMA = {
    "headline":    "string — titre court du run mobile (max 80 chars), ex: '✅ Mobile Tests — 14/17 PASSED'",
    "status":      "PASSED | FAILED | DEGRADED",
    "narrative":   "string — résumé narratif en 2-3 phrases. Contexte mobile : app Android, Appium.",
    "top_failure": "string — nom du test le plus critique en échec (vide si aucun)",
    "action":      "string — action recommandée en 1 phrase (vide si PASSED)"
}


def load_allure_results() -> list:
    results = []
    for path in glob.glob(os.path.join(RESULTS_DIR, "*-result.json")):
        try:
            with open(path, encoding="utf-8") as f:
                results.append(json.load(f))
        except Exception:
            pass
    return results


def compute_stats(results: list) -> dict:
    stats = {"passed": 0, "failed": 0, "broken": 0, "skipped": 0, "total": 0}
    smoke_failed = 0
    for r in results:
        s = r.get("status", "unknown")
        if s in stats:
            stats[s] += 1
        stats["total"] += 1
        labels = r.get("labels", [])
        groups = [lb["value"] for lb in labels if lb["name"] == "tag"]
        if s in ("failed", "broken") and "smoke" in groups:
            smoke_failed += 1
    stats["pass_rate"]    = round(stats["passed"] / stats["total"] * 100, 1) if stats["total"] else 0.0
    stats["smoke_failed"] = smoke_failed
    return stats


def generate_summary(results: list, stats: dict) -> dict:
    failures = [
        {
            "test_class": next((lb["value"].split(".")[-1] for lb in r.get("labels", []) if lb["name"] == "testClass"), "?"),
            "name":   r.get("name", "?"),
            "status": r.get("status"),
            "message": (r.get("statusDetails") or {}).get("message", "")[:200],
        }
        for r in results if r.get("status") in ("failed", "broken")
    ][:10]

    prompt = f"""Tu es un expert QA Mobile. Génère un résumé concis d'un run de tests Appium/Android pour Slack.

RÉSULTATS :
- App : QAcart-To-Do.apk (Android)
- Framework : Appium 9.2.2 + TestNG 7.10.2
- Total     : {stats['total']} tests
- Pass rate : {stats['pass_rate']}%
- Passed    : {stats['passed']} | Failed : {stats['failed']} | Broken : {stats['broken']}
- Tests smoke en échec : {stats['smoke_failed']}

ECHECS ({len(failures)}) :
{json.dumps(failures, ensure_ascii=False, indent=2)}

Ton résumé doit mentionner le contexte mobile (Android, Appium). Si PASSED → positif et rassurant.
Si FAILED → factuel, cause principale (locator ? crash ? timeout ?), action recommandée.
"""
    return llm.chat_structured([{"role": "user", "content": prompt}], SUMMARY_SCHEMA)


def build_slack_payload(summary: dict, stats: dict) -> dict:
    status_emoji = {"PASSED": "✅", "FAILED": "❌", "DEGRADED": "⚠️"}.get(summary.get("status",""), "📱")
    color        = {"PASSED": "#43e97b", "FAILED": "#ef4444", "DEGRADED": "#ffd700"}.get(summary.get("status",""), "#6c63ff")

    fields = [
        {"type": "mrkdwn", "text": f"*Pass Rate*\n{stats['pass_rate']}%"},
        {"type": "mrkdwn", "text": f"*Passés*\n{stats['passed']}/{stats['total']}"},
        {"type": "mrkdwn", "text": f"*Failed*\n{stats['failed']}"},
        {"type": "mrkdwn", "text": f"*Smoke KO*\n{stats['smoke_failed']}"},
    ]

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"{status_emoji} {summary.get('headline','Mobile QA Run')}", "emoji": True}},
        {"type": "section", "text": {"type": "mrkdwn", "text": summary.get("narrative","")}},
        {"type": "section", "fields": fields},
    ]

    if summary.get("top_failure"):
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Top échec :* `{summary['top_failure']}`"}})

    if summary.get("action"):
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Action :* {summary['action']}"}})

    blocks.append({"type": "divider"})
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn",
        "text": f"📱 QAcart-To-Do.apk · Appium 9.2.2 · notification-agent · {llm.MODEL}"}]})

    return {"attachments": [{"color": color, "blocks": blocks}]}


def build_teams_payload(summary: dict, stats: dict) -> dict:
    status_emoji = {"PASSED": "✅", "FAILED": "❌", "DEGRADED": "⚠️"}.get(summary.get("status",""), "📱")

    facts = [
        {"name": "App",       "value": "QAcart-To-Do.apk (Android)"},
        {"name": "Pass Rate", "value": f"{stats['pass_rate']}%"},
        {"name": "Passés",    "value": str(stats["passed"])},
        {"name": "Failed",    "value": str(stats["failed"])},
        {"name": "Smoke KO",  "value": str(stats["smoke_failed"])},
    ]

    sections = [{
        "activityTitle":    f"{status_emoji} {summary.get('headline','Mobile QA Run')}",
        "activitySubtitle": summary.get("narrative",""),
        "facts":            facts,
        "markdown":         True,
    }]

    if summary.get("action"):
        sections.append({"text": f"**Action recommandée :** {summary['action']}"})

    return {
        "@type":      "MessageCard",
        "@context":   "http://schema.org/extensions",
        "themeColor": {"PASSED": "00b894", "FAILED": "d63031", "DEGRADED": "fdcb6e"}.get(summary.get("status",""), "6c63ff"),
        "summary":    summary.get("headline","Mobile QA Run"),
        "sections":   sections,
    }


def send_notification(payload: dict, webhook_url: str, target: str) -> bool:
    try:
        resp = _req.post(webhook_url, json=payload, timeout=15)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"  {R}✗ Erreur envoi {target} : {e}{E}")
        return False


def run():
    print(f"\n{W}=== NOTIFICATION AGENT MOBILE [{llm.MODEL}] ==={E}")

    results = load_allure_results()
    if not results:
        print(f"  {Y}⚠  Aucun résultat dans target/allure-results/{E}")
        return

    stats = compute_stats(results)
    print(f"  {C}{stats['total']} tests · Pass rate {stats['pass_rate']}% · Smoke KO : {stats['smoke_failed']}{E}")

    print(f"  Génération résumé LLM...")
    summary  = generate_summary(results, stats)
    headline = summary.get("headline", "Mobile QA Run")
    status   = summary.get("status", "?")
    color    = G if status == "PASSED" else R if status == "FAILED" else Y

    print(f"\n  {color}{headline}{E}")
    print(f"  {summary.get('narrative','')}")

    if DRY_RUN:
        print(f"\n  {Y}[DRY-RUN] Message non envoyé.{E}")
        print(f"  Cible   : {TARGET}")
        print(f"  Webhook : {'configuré' if (SLACK_WEBHOOK if TARGET=='slack' else TEAMS_WEBHOOK) else 'MANQUANT'}")
        return

    if TARGET == "slack":
        if not SLACK_WEBHOOK:
            print(f"  {Y}⚠  SLACK_WEBHOOK_URL non configurée dans .env{E}")
            return
        payload = build_slack_payload(summary, stats)
        if send_notification(payload, SLACK_WEBHOOK, "Slack"):
            print(f"  {G}✓ Message Slack envoyé{E}")

    elif TARGET == "teams":
        if not TEAMS_WEBHOOK:
            print(f"  {Y}⚠  TEAMS_WEBHOOK_URL non configurée dans .env{E}")
            return
        payload = build_teams_payload(summary, stats)
        if send_notification(payload, TEAMS_WEBHOOK, "Teams"):
            print(f"  {G}✓ Message Teams envoyé{E}")


if __name__ == "__main__":
    run()
