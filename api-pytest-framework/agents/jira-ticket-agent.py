# ============================================
# Jira Ticket Agent — Crée les tickets Bug depuis les échecs pytest
# ============================================
# Lit les résultats Allure / pytest, génère des tickets Bug structurés
# via LLM, évite les doublons automatiquement.
#
# Usage:
#   python agents/jira-ticket-agent.py
#   python agents/jira-ticket-agent.py --dry-run
#   python agents/jira-ticket-agent.py --type=Story
# ============================================

import sys
import os
import json
sys.path.insert(0, os.path.dirname(__file__))

from jira_fetcher_agent import JiraClient
import llm

DRY_RUN     = "--dry-run" in sys.argv
ISSUE_TYPE  = next((a.split("=")[1] for a in sys.argv if a.startswith("--type=")), "Bug")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "../allure-results")


def load_failures() -> list[dict]:
    failures = []
    if not os.path.exists(RESULTS_DIR):
        return failures
    for f in os.listdir(RESULTS_DIR):
        if f.endswith("-result.json"):
            with open(os.path.join(RESULTS_DIR, f)) as fh:
                data = json.load(fh)
            if data.get("status") in ("failed", "broken"):
                failures.append({
                    "name":    data.get("name", ""),
                    "message": data.get("statusDetails", {}).get("message", ""),
                    "trace":   data.get("statusDetails", {}).get("trace", "")[:500],
                })
    return failures


def generate_tickets(failures: list[dict]) -> list[dict]:
    if not failures:
        return []
    prompt = f"""Tu es un expert QA. Pour chaque échec de test API ci-dessous,
génère un ticket {ISSUE_TYPE} Jira structuré.
Réponds UNIQUEMENT en JSON : liste d'objets avec summary, description, priority (Low/Medium/High/Highest), labels.

Échecs :
{json.dumps(failures, ensure_ascii=False, indent=2)}"""

    raw = llm.chat([{"role": "user", "content": prompt}])
    start, end = raw.find("["), raw.rfind("]") + 1
    tickets = json.loads(raw[start:end]) if start != -1 else []

    seen = set()
    deduped = []
    for t in tickets:
        key = t["summary"].lower().strip()
        if key not in seen:
            seen.add(key)
            deduped.append(t)
    return deduped


def run():
    print(f"\n=== JIRA TICKET AGENT [{llm.MODEL}] ===")
    if DRY_RUN:
        print("   MODE DRY-RUN\n")

    failures = load_failures()
    print(f"📂 {len(failures)} échec(s) trouvé(s)")
    if not failures:
        print("✅ Aucun échec — aucun ticket à créer.")
        return

    tickets = generate_tickets(failures)
    print(f"🤖 {len(tickets)} ticket(s) généré(s)")

    if DRY_RUN:
        for t in tickets:
            print(f"  [{t.get('priority')}] {t.get('summary')}")
        return

    jira = JiraClient()
    existing = {s["fields"]["summary"].lower() for s in jira.get_stories()}

    created = 0
    for t in tickets:
        if t["summary"].lower() in existing:
            print(f"  ⏭️  Doublon ignoré : {t['summary']}")
            continue
        issue = jira.create_story(t["summary"], t.get("description", ""), t.get("priority", "Medium"))
        print(f"  ✅ Créé : {issue.get('key')} — {t['summary']}")
        created += 1

    print(f"\n✅ {created} ticket(s) créé(s) dans Jira.")


if __name__ == "__main__":
    run()
