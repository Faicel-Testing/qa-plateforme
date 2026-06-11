# ============================================================
# Notification Agent — Slack / Teams / Webhook
# ============================================================
# Envoie un résumé du run QA vers un canal Slack (ou Teams)
# via Incoming Webhook. Le résumé narratif est généré par LLM.
#
# Variables d'environnement requises :
#   SLACK_WEBHOOK_URL   → webhook Slack (ex: https://hooks.slack.com/services/...)
#   TEAMS_WEBHOOK_URL   → webhook Teams (optionnel, alternative à Slack)
#
# Usage:
#   python agents/notification-agent.py             → post Slack depuis allure-results
#   python agents/notification-agent.py --dry-run   → affiche le message sans envoyer
#   python agents/notification-agent.py teams        → envoie vers Teams au lieu de Slack
# ============================================================

import sys, os, json, glob
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import requests as _req
import llm

FRAMEWORK   = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS_DIR = os.path.join(FRAMEWORK, "allure-results")
DRY_RUN     = "--dry-run" in sys.argv
TARGET      = "teams" if "teams" in sys.argv else "slack"

SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "")
TEAMS_WEBHOOK = os.getenv("TEAMS_WEBHOOK_URL", "")

G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"; R = "\033[31m"; E = "\033[0m"; W = "\033[1m"

SUMMARY_SCHEMA = {
    "headline":    "string — titre court du run (max 80 chars), ex: '✅ API Tests — 48/51 PASSED'",
    "status":      "PASSED | FAILED | DEGRADED",
    "narrative":   "string — résumé narratif en 2-3 phrases. Mentionne les vraies causes si échecs.",
    "top_failure": "string — nom du TC le plus important en échec (vide si aucun)",
    "action":      "string — action recommandée en 1 phrase (vide si PASSED)"
}


# ── Chargement ────────────────────────────────────────────────────────────────

def load_allure_results() -> list[dict]:
    results = []
    for path in glob.glob(os.path.join(RESULTS_DIR, "*-result.json")):
        try:
            with open(path, encoding="utf-8") as f:
                results.append(json.load(f))
        except Exception:
            pass
    return results


def compute_stats(results: list[dict]) -> dict:
    stats = {"passed": 0, "failed": 0, "broken": 0, "skipped": 0, "total": 0}
    for r in results:
        s = r.get("status", "unknown")
        if s in stats:
            stats[s] += 1
        stats["total"] += 1
    stats["pass_rate"] = round(stats["passed"] / stats["total"] * 100, 1) if stats["total"] else 0.0
    return stats


# ── Génération du résumé LLM ──────────────────────────────────────────────────

def generate_summary(results: list[dict], stats: dict) -> dict:
    failures = [
        {
            "name": r.get("name", "?"),
            "status": r.get("status"),
            "message": (r.get("statusDetails") or {}).get("message", "")[:200],
        }
        for r in results if r.get("status") in ("failed", "broken")
    ][:10]

    prompt = f"""Tu es un expert QA. Génère un résumé concis d'un run de tests API pour un canal Slack.

RÉSULTATS :
- Total : {stats['total']} TCs
- Pass rate : {stats['pass_rate']}%
- Passed: {stats['passed']} | Failed: {stats['failed']} | Broken: {stats['broken']}

ECHECS ({len(failures)}) :
{json.dumps(failures, ensure_ascii=False, indent=2)}

Le ton doit être direct et informatif. Si PASSED → positif et rassurant. Si FAILED → factuel, cause principale, action recommandée.
"""
    return llm.chat_structured([{"role": "user", "content": prompt}], SUMMARY_SCHEMA)


# ── Formatage des messages ────────────────────────────────────────────────────

def build_slack_payload(summary: dict, stats: dict) -> dict:
    status_emoji = {"PASSED": "✅", "FAILED": "❌", "DEGRADED": "⚠️"}.get(summary.get("status", ""), "📊")
    color = {"PASSED": "#43e97b", "FAILED": "#ef4444", "DEGRADED": "#ffd700"}.get(summary.get("status", ""), "#6c63ff")

    fields = [
        {"type": "mrkdwn", "text": f"*Pass Rate*\n{stats['pass_rate']}%"},
        {"type": "mrkdwn", "text": f"*Passed*\n{stats['passed']}/{stats['total']}"},
        {"type": "mrkdwn", "text": f"*Failed*\n{stats['failed']}"},
        {"type": "mrkdwn", "text": f"*Broken*\n{stats['broken']}"},
    ]

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"{status_emoji} {summary.get('headline', 'QA Run')}", "emoji": True}},
        {"type": "section", "text": {"type": "mrkdwn", "text": summary.get("narrative", "")}},
        {"type": "section", "fields": fields},
    ]

    if summary.get("top_failure"):
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Top échec :* `{summary['top_failure']}`"}})

    if summary.get("action"):
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Action recommandée :* {summary['action']}"}})

    blocks.append({"type": "divider"})
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": f"Généré par notification-agent · {llm.MODEL}"}]})

    return {
        "attachments": [{"color": color, "blocks": blocks}]
    }


def build_teams_payload(summary: dict, stats: dict) -> dict:
    status_emoji = {"PASSED": "✅", "FAILED": "❌", "DEGRADED": "⚠️"}.get(summary.get("status", ""), "📊")
    color = {"PASSED": "Good", "FAILED": "Attention", "DEGRADED": "Warning"}.get(summary.get("status", ""), "Emphasis")

    facts = [
        {"name": "Pass Rate", "value": f"{stats['pass_rate']}%"},
        {"name": "Passed", "value": str(stats["passed"])},
        {"name": "Failed", "value": str(stats["failed"])},
        {"name": "Broken", "value": str(stats["broken"])},
    ]

    sections = [{
        "activityTitle": f"{status_emoji} {summary.get('headline', 'QA Run')}",
        "activitySubtitle": summary.get("narrative", ""),
        "facts": facts,
        "markdown": True
    }]

    if summary.get("action"):
        sections.append({"text": f"**Action recommandée :** {summary['action']}"})

    return {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": {"PASSED": "00b894", "FAILED": "d63031", "DEGRADED": "fdcb6e"}.get(summary.get("status", ""), "6c63ff"),
        "summary": summary.get("headline", "QA Run"),
        "sections": sections
    }


# ── Envoi ─────────────────────────────────────────────────────────────────────

def send_notification(payload: dict, webhook_url: str, target: str) -> bool:
    try:
        resp = _req.post(webhook_url, json=payload, timeout=15)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"  {R}✗ Erreur envoi {target} : {e}{E}")
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    print(f"\n{W}=== NOTIFICATION AGENT [{llm.MODEL}] ==={E}")

    results = load_allure_results()
    if not results:
        print(f"  {Y}⚠  Aucun résultat Allure dans {RESULTS_DIR}{E}")
        return

    stats = compute_stats(results)
    print(f"  {C}{stats['total']} TCs · Pass rate {stats['pass_rate']}%{E}")

    print(f"  Génération résumé LLM...")
    summary = generate_summary(results, stats)

    headline = summary.get("headline", "QA Run")
    status   = summary.get("status", "?")
    color    = G if status == "PASSED" else R if status == "FAILED" else Y
    print(f"\n  {color}{headline}{E}")
    print(f"  {summary.get('narrative', '')}")

    if DRY_RUN:
        print(f"\n  {Y}[DRY-RUN] Message non envoyé.{E}")
        print(f"  Cible : {TARGET}")
        print(f"  Webhook : {'configuré' if (SLACK_WEBHOOK if TARGET == 'slack' else TEAMS_WEBHOOK) else 'MANQUANT'}")
        return

    # Envoi Slack
    if TARGET == "slack":
        if not SLACK_WEBHOOK:
            print(f"  {Y}⚠  SLACK_WEBHOOK_URL non configurée. Ajoute-la dans .env{E}")
            return
        payload = build_slack_payload(summary, stats)
        if send_notification(payload, SLACK_WEBHOOK, "Slack"):
            print(f"  {G}✓ Message Slack envoyé{E}")

    # Envoi Teams
    elif TARGET == "teams":
        if not TEAMS_WEBHOOK:
            print(f"  {Y}⚠  TEAMS_WEBHOOK_URL non configurée. Ajoute-la dans .env{E}")
            return
        payload = build_teams_payload(summary, stats)
        if send_notification(payload, TEAMS_WEBHOOK, "Teams"):
            print(f"  {G}✓ Message Teams envoyé{E}")


if __name__ == "__main__":
    run()
