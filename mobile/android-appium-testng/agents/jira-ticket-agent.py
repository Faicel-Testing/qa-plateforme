# ============================================================
# Jira Ticket Agent — Mobile (Appium / Android)
# ============================================================
# Lit les résultats Allure (target/allure-results/), génère
# des tickets Bug Jira structurés pour chaque échec mobile.
#
# Contexte ticket mobile :
#   - Device : Android Emulator (UiAutomator2)
#   - Framework : Appium 9.2.2 + TestNG 7.10.2
#   - App : QAcart-To-Do.apk
#   - Steps to reproduce : login → navigate → assert
#
# Usage:
#   python agents/jira-ticket-agent.py             → crée les tickets
#   python agents/jira-ticket-agent.py --dry-run   → affiche sans créer
#   python agents/jira-ticket-agent.py --type=Bug  → type d'issue (défaut: Bug)
# ============================================================

import sys, os, json, glob
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

from jira_fetcher_agent import JiraClient
import llm

DRY_RUN    = "--dry-run" in sys.argv
ISSUE_TYPE = next((a.split("=")[1] for a in sys.argv if a.startswith("--type=")), "Bug")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "target", "allure-results")

TICKET_SCHEMA = {
    "summary":     "string — résumé du bug en 1 ligne (max 100 chars), préfixé [MOBILE]",
    "description": "string — description complète avec : Device, Framework, Steps to reproduce, Expected vs Actual, Error message",
    "priority":    "Low | Medium | High | Highest",
    "labels":      ["mobile", "appium", "android"]
}

G = "\033[32m"; R = "\033[31m"; Y = "\033[33m"; C = "\033[36m"; W = "\033[1m"; E = "\033[0m"


def load_failures() -> list:
    failures = []
    pattern  = os.path.join(RESULTS_DIR, "*-result.json")
    for f in glob.glob(pattern):
        try:
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
            if d.get("status") not in ("failed", "broken"):
                continue

            labels     = d.get("labels", [])
            test_class = next((lb["value"] for lb in labels if lb["name"] == "testClass"), "?")
            short_cls  = test_class.split(".")[-1] if "." in test_class else test_class
            groups     = [lb["value"] for lb in labels if lb["name"] == "tag"]
            detail     = d.get("statusDetails") or {}

            failures.append({
                "name":       d.get("name", "?"),
                "test_class": short_cls,
                "status":     d.get("status"),
                "groups":     groups,
                "message":    detail.get("message", "")[:400],
                "trace":      detail.get("trace",   "")[:500],
            })
        except Exception:
            pass
    return failures


def generate_tickets(failures: list) -> list:
    if not failures:
        return []

    failures_json = json.dumps([{
        "test_class": f["test_class"],
        "name":       f["name"],
        "groups":     f["groups"],
        "status":     f["status"],
        "message":    f["message"][:200],
        "trace":      f["trace"][:200],
    } for f in failures], ensure_ascii=False, indent=2)

    prompt = f"""Tu es un expert QA Mobile (Appium/Android). Pour chaque échec de test ci-dessous,
génère un ticket Bug Jira structuré.

Contexte du projet :
- Device : Android Emulator (UiAutomator2)
- Framework : Appium 9.2.2 + TestNG 7.10.2 (Java 17)
- App sous test : QAcart-To-Do.apk
- Locators : AppiumBy.androidUIAutomator() / AppiumBy.className()

Réponds UNIQUEMENT avec un JSON valide : liste d'objets, chacun avec :
  summary     : "[MOBILE] Résumé court du bug"
  description : "Device: Android Emulator\\nFramework: Appium 9.2.2\\nTest: <classe.méthode>\\n\\nSteps to reproduce:\\n1. Lancer l'app\\n2. ...\\n\\nExpected: ...\\nActual: ...\\n\\nError:\\n<message d'erreur>"
  priority    : "Low | Medium | High | Highest"
  labels      : ["mobile", "appium", "android", <group>]

Règles priorité mobile :
  Highest → app crash, session Appium perdue, smoke test échoué
  High    → élément non trouvé sur écran principal
  Medium  → timeout, test de régression
  Low     → false positive, test en quarantaine

Échecs à analyser :
{failures_json}"""

    raw   = llm.chat([{"role": "user", "content": prompt}])
    start = raw.find("[")
    end   = raw.rfind("]") + 1
    if start == -1:
        return []

    try:
        tickets = json.loads(raw[start:end])
    except Exception:
        return []

    seen    = set()
    deduped = []
    for t in tickets:
        key = t.get("summary","").lower().strip()
        if key not in seen:
            seen.add(key)
            deduped.append(t)
    return deduped


def run():
    print(f"\n{W}=== JIRA TICKET AGENT MOBILE [{llm.MODEL}] ==={E}")
    if DRY_RUN:
        print(f"   {Y}MODE DRY-RUN — aucun ticket ne sera créé{E}\n")

    failures = load_failures()
    print(f"  {C}{len(failures)} échec(s) trouvé(s) dans target/allure-results/{E}")
    if not failures:
        print(f"  {G}✓ Aucun échec — aucun ticket à créer.{E}")
        return

    for f in failures:
        group_str = ", ".join(f["groups"]) or "aucun"
        print(f"  {R}✗{E} [{f['test_class']}] {f['name']} ({group_str})")

    print(f"\n  {C}Génération des tickets via LLM ({ISSUE_TYPE})...{E}")
    tickets = generate_tickets(failures)
    print(f"  {G}{len(tickets)} ticket(s) généré(s){E}")

    if DRY_RUN:
        print()
        for t in tickets:
            prio = t.get("priority", "?")
            prio_color = R if prio in ("Highest","High") else Y if prio == "Medium" else G
            print(f"  [{prio_color}{prio}{E}] {t.get('summary','?')}")
            labels = t.get("labels", [])
            if labels:
                print(f"    Labels : {', '.join(labels)}")
        return

    jira     = JiraClient()
    existing = {s["fields"]["summary"].lower() for s in jira.get_stories()}

    created = 0
    for t in tickets:
        if t.get("summary","").lower() in existing:
            print(f"  {Y}⏭  Doublon ignoré : {t.get('summary','')}{E}")
            continue

        extra_labels = list(set(["mobile", "appium", "android"] + t.get("labels", [])))
        issue = jira.create_story(
            summary     = t.get("summary", "Mobile Test Failure"),
            description = t.get("description", ""),
            priority    = t.get("priority", "Medium"),
        )
        key = issue.get("key", "?")
        print(f"  {G}✓ Créé : {key} — {t.get('summary','')}{E}")
        created += 1

    print(f"\n  {G}✓ {created} ticket(s) créé(s) dans Jira.{E}")


if __name__ == "__main__":
    run()
