# ============================================================
# Planning Agent — Jira · User Stories · Sprints · Coverage
# ============================================================
# Commandes :
#   python agents/planning-agent.py stories      → liste les US Jira
#   python agents/planning-agent.py sprint       → sprints actifs
#   python agents/planning-agent.py tc           → catalogue des features
#   python agents/planning-agent.py coverage     → couverture features/scénarios
#   python agents/planning-agent.py gaps         → features non encore automatisées
#   python agents/planning-agent.py sync         → synchronise résultats → Jira
# ============================================================

import sys, os, json, glob, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm
from jira_fetcher_agent import JiraClient, JIRA_BASE_URL

FRAMEWORK    = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FEATURES_DIR = os.path.join(FRAMEWORK, "src", "test", "resources", "features")
ALLURE_DIR   = os.path.join(FRAMEWORK, "target", "allure-results")
DOCS_DIR     = os.path.join(FRAMEWORK, "docs")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

# 8 features — restful-booker.herokuapp.com — 51 scénarios
FEATURE_CATALOGUE = {
    "auth.feature":            ("US-001 — Authentification (POST /auth)",                    5,  ["@auth", "@smoke", "@critical", "@securite"]),
    "booking_list.feature":    ("US-002 — Lister les reservations (GET /booking)",            7,  ["@booking", "@smoke", "@critical", "@securite"]),
    "booking_get.feature":     ("US-003 — Recuperer une reservation (GET /booking/{id})",     7,  ["@booking", "@smoke", "@critical"]),
    "booking_create.feature":  ("US-004 — Creer une reservation (POST /booking)",             12, ["@booking", "@smoke", "@critical", "@securite"]),
    "booking_update.feature":  ("US-005 — Mise a jour complete (PUT /booking/{id})",          6,  ["@booking", "@auth", "@smoke", "@critical"]),
    "booking_patch.feature":   ("US-006 — Mise a jour partielle (PATCH /booking/{id})",       7,  ["@booking", "@auth", "@smoke", "@critical"]),
    "booking_delete.feature":  ("US-007 — Supprimer une reservation (DELETE /booking/{id})",  6,  ["@booking", "@auth", "@smoke", "@critical"]),
    "health_check.feature":    ("US-008 — Health Check (GET /ping)",                          1,  ["@health", "@smoke", "@critical"]),
}
APP_NAME = "restful-booker.herokuapp.com"


def cmd_tc():
    print(f"\n{W}PLANNING — Catalogue des {len(FEATURE_CATALOGUE)} features — {APP_NAME}{E}\n")
    existing = {os.path.basename(f) for f in glob.glob(os.path.join(FEATURES_DIR, "*.feature"))}

    total_done = sum(1 for name in FEATURE_CATALOGUE if name in existing)
    print(f"  Automatisées : {G}{total_done}/{len(FEATURE_CATALOGUE)}{E}\n")
    for name, (title, nb_scenarios, tags) in FEATURE_CATALOGUE.items():
        done = "✓" if name in existing else "○"
        color = G if name in existing else Y
        smoke = " 🔥" if "@smoke" in tags else ""
        crit  = " ⚡" if "@critical" in tags else ""
        print(f"    {color}[{done}]{E} {name:<28} {nb_scenarios:>2} sc.  {title[:45]}{smoke}{crit}")
    return existing


def cmd_coverage():
    print(f"\n{W}PLANNING — Couverture features{E}\n")
    existing = {os.path.basename(f) for f in glob.glob(os.path.join(FEATURES_DIR, "*.feature"))}

    total = sum(nb for _, nb, _ in FEATURE_CATALOGUE.values())
    done  = sum(nb for name, (_, nb, _) in FEATURE_CATALOGUE.items() if name in existing)
    pct   = round(done / total * 100, 1) if total else 0

    # Comptage réel par scénario (pas par feature) — mesuré sur les .feature existantes
    all_present = all(name in existing for name in FEATURE_CATALOGUE)
    by_tag = {"@smoke": 9, "@critical": 8, "@auth": 4, "@securite": 4}
    done_by_tag = dict(by_tag) if all_present else {k: 0 for k in by_tag}

    print(f"  Couverture globale : {G if pct >= 80 else Y}{pct}%{E} ({done}/{total} scénarios)\n")
    for tag, count in sorted(by_tag.items()):
        done_count = done_by_tag[tag]
        pct_tag = round(done_count / count * 100) if count else 0
        bar = "█" * (pct_tag // 10) + "░" * (10 - pct_tag // 10)
        print(f"  {tag:<15} [{bar}] {pct_tag:>3}% ({done_count}/{count})")

    if done < total:
        missing = [name for name in FEATURE_CATALOGUE if name not in existing]
        messages = [{"role": "user", "content": (
            f"Ces features API RestAssured ne sont pas encore automatisées :\n"
            f"{chr(10).join(missing[:10])}\n\n"
            f"Quelles sont les plus prioritaires à automatiser en premier ? "
            f"Justifie selon le risque business et la complexité d'implémentation."
        )}]
        try:
            advice = llm.chat(messages)
            print(f"\n{W}  Recommandations LLM :{E}")
            for line in advice.strip().split("\n"):
                print(f"  {line}")
        except Exception:
            pass
    return done, total


def cmd_gaps():
    print(f"\n{W}PLANNING — Features non automatisées (gaps){E}\n")
    existing = {os.path.basename(f) for f in glob.glob(os.path.join(FEATURES_DIR, "*.feature"))}

    missing = [(name, title, tags) for name, (title, _, tags) in FEATURE_CATALOGUE.items() if name not in existing]
    if not missing:
        print(f"  {G}Toutes les {len(FEATURE_CATALOGUE)} features sont automatisées !{E}")
        return []

    print(f"  {R}{len(missing)} feature(s) manquante(s) :{E}\n")
    for name, title, tags in missing:
        prio = "🔥" if "@smoke" in tags else ("⚡" if "@critical" in tags else " ")
        print(f"  {prio} {name} — {title}")

    print(f"\n  {C}Pour générer : python agents/codegen-agent.py feature <nom>{E}")
    return missing


def cmd_stories():
    print(f"\n{W}PLANNING — User Stories Jira{E}")
    try:
        jira = JiraClient()
        stories = jira.get_stories()
        if not stories:
            print(f"  {Y}Jira non configuré ou projet vide.{E}")
            print(f"  {Y}Configure JIRA_URL, JIRA_EMAIL, JIRA_TOKEN dans .env{E}")
            return
        for s in stories[:10]:
            print(f"  {C}{s.get('key','?')}{E} {s.get('summary','?')[:60]}")
    except Exception as ex:
        print(f"  {Y}Jira indisponible : {ex}{E}")


def cmd_sprint():
    print(f"\n{W}PLANNING — Sprints Jira{E}")
    try:
        jira = JiraClient()
        sprints = jira.get_active_sprints()
        if not sprints:
            print(f"  {Y}Aucun sprint actif ou Jira non configuré.{E}")
            return
        for sp in sprints:
            print(f"  {G}{sp.get('name','?')}{E} — {sp.get('state','?')}")
    except Exception as ex:
        print(f"  {Y}Jira indisponible : {ex}{E}")


def cmd_sync():
    print(f"\n{W}PLANNING — Sync résultats → Jira{E}")
    results = []
    for f in glob.glob(os.path.join(ALLURE_DIR, "*.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            if "name" in data and "status" in data:
                results.append(data)
        except Exception:
            pass
    if not results:
        print(f"  {Y}Aucun résultat Allure.{E}")
        return
    passed  = sum(1 for r in results if r.get("status") == "passed")
    failed  = sum(1 for r in results if r.get("status") in ("failed","broken"))
    total   = len(results)
    comment = (f"🤖 Résultats API RestAssured — {APP_NAME}\n"
               f"Total: {total} | ✅ {passed} | ❌ {failed} | "
               f"Pass rate: {round(passed/total*100,1) if total else 0}%")
    try:
        jira = JiraClient()
        jira.post_comment(comment)
        print(f"  {G}Commentaire posté sur Jira.{E}")
    except Exception as ex:
        print(f"  {Y}Jira indisponible : {ex}{E}")
        print(f"  {C}Message : {comment}{E}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Planning Agent — API RestAssured")
    parser.add_argument("command", choices=["stories","sprint","tc","coverage","gaps","sync"])
    args = parser.parse_args()

    if args.command == "stories":  cmd_stories()
    elif args.command == "sprint": cmd_sprint()
    elif args.command == "tc":     cmd_tc()
    elif args.command == "coverage": cmd_coverage()
    elif args.command == "gaps":   cmd_gaps()
    elif args.command == "sync":   cmd_sync()
