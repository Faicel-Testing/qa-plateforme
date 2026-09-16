# ============================================================
# Planning Agent — Jira · User Stories · Sprints · Coverage
# ============================================================
# Commandes :
#   python agents/planning-agent.py stories      → liste les US Jira
#   python agents/planning-agent.py sprint       → sprints actifs
#   python agents/planning-agent.py tc           → catalogue des TCs
#   python agents/planning-agent.py coverage     → couverture features/TCs
#   python agents/planning-agent.py gaps         → TCs non encore automatisés
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

# TCs QACart Todo — 1 TC par feature file (Id01→TC01 … Id08→TC08)
TC_CATALOGUE = {
    1: ("Id01 — Signup (valid + validations)",        ["@smoke","@critical","@signup"]),
    2: ("Id02 — Login (valid credentials)",           ["@smoke","@critical","@login"]),
    3: ("Id03 — Todo Management (add + validations)", ["@smoke","@todo"]),
    4: ("Id04 — Delete Todo (delete + validations)",  ["@todo"]),
    5: ("Id05 — Login Negative (invalid/empty)",      ["@negative","@login"]),
    6: ("Id06 — Profile: Password Update",            ["@wip","@profile","@security"]),
    7: ("Id07 — Profile: Email Update",               ["@wip","@profile","@contact"]),
    8: ("Id08 — Profile: Account Deletion",           ["@wip","@profile","@security"]),
}
APP_NAME = "qacart-todo.herokuapp.com"


def cmd_tc():
    print(f"\n{W}PLANNING — Catalogue des {len(TC_CATALOGUE)} TCs — qacart-todo.herokuapp.com{E}\n")
    existing_features = glob.glob(os.path.join(FEATURES_DIR, "*.feature"))
    automated = set()
    for f in existing_features:
        m = re.search(r"Id(\d+)", os.path.basename(f))
        if m:
            automated.add(int(m.group(1)))

    by_domain = {}
    for tc_id, (title, tags) in TC_CATALOGUE.items():
        domain = tags[-1].lstrip("@") if tags else "other"
        by_domain.setdefault(domain, []).append((tc_id, title, tags))

    total_done = len(automated)
    print(f"  Automatisés : {G}{total_done}/{len(TC_CATALOGUE)}{E}\n")
    for domain, tcs in sorted(by_domain.items()):
        print(f"  {C}{domain.upper()}{E}")
        for tc_id, title, tags in tcs:
            done = "✓" if tc_id in automated else "○"
            color = G if tc_id in automated else Y
            smoke = " 🔥" if "@smoke" in tags else ""
            crit  = " ⚡" if "@critical" in tags else ""
            print(f"    {color}[{done}]{E} TC{tc_id:02d} {title[:50]}{smoke}{crit}")
    return automated


def cmd_coverage():
    print(f"\n{W}PLANNING — Couverture TCs{E}\n")
    existing_features = glob.glob(os.path.join(FEATURES_DIR, "*.feature"))
    automated = set()
    for f in existing_features:
        m = re.search(r"Id(\d+)", os.path.basename(f))
        if m:
            automated.add(int(m.group(1)))

    total = len(TC_CATALOGUE)
    done  = len(automated)
    pct   = round(done / total * 100, 1)

    by_tag = {"@smoke":0, "@critical":0, "@auth":0, "@cart":0, "@order":0, "@products":0}
    done_by_tag = {k:0 for k in by_tag}
    for tc_id, (_, tags) in TC_CATALOGUE.items():
        for tag in by_tag:
            if tag in tags:
                by_tag[tag] += 1
                if tc_id in automated:
                    done_by_tag[tag] += 1

    print(f"  Couverture globale : {G if pct >= 80 else Y}{pct}%{E} ({done}/{total})\n")
    for tag, count in sorted(by_tag.items()):
        done_count = done_by_tag[tag]
        pct_tag = round(done_count / count * 100) if count else 0
        bar = "█" * (pct_tag // 10) + "░" * (10 - pct_tag // 10)
        print(f"  {tag:<15} [{bar}] {pct_tag:>3}% ({done_count}/{count})")

    # Analyse LLM des gaps
    if done < total:
        missing = [f"TC{i}: {TC_CATALOGUE[i][0]}" for i in range(1, len(TC_CATALOGUE) + 1) if i not in automated]
        messages = [{"role": "user", "content": (
            f"Ces TCs Selenium BDD ne sont pas encore automatisés :\n"
            f"{chr(10).join(missing[:10])}\n\n"
            f"Quels sont les 5 plus prioritaires à automatiser en premier ? "
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
    print(f"\n{W}PLANNING — TCs non automatisés (gaps){E}\n")
    existing = glob.glob(os.path.join(FEATURES_DIR, "*.feature"))
    automated = set()
    for f in existing:
        m = re.search(r"Id(\d+)", os.path.basename(f))
        if m:
            automated.add(int(m.group(1)))

    missing = [(tc_id, title, tags) for tc_id, (title, tags) in TC_CATALOGUE.items()
               if tc_id not in automated]
    if not missing:
        print(f"  {G}Tous les {len(TC_CATALOGUE)} TCs sont automatisés !{E}")
        return []

    print(f"  {R}{len(missing)} TCs manquants :{E}\n")
    for tc_id, title, tags in missing:
        prio = "🔥" if "@smoke" in tags else ("⚡" if "@critical" in tags else " ")
        print(f"  {prio} TC{tc_id:02d} {title}")

    print(f"\n  {C}Pour générer : python agents/codegen-agent.py full --tc {' '.join(str(t[0]) for t in missing[:5])}{E}")
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
    comment = (f"🤖 Résultats Selenium BDD — qacart-todo.herokuapp.com\n"
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
    parser = argparse.ArgumentParser(description="Planning Agent — Selenium BDD")
    parser.add_argument("command", choices=["stories","sprint","tc","coverage","gaps","sync"])
    args = parser.parse_args()

    if args.command == "stories":  cmd_stories()
    elif args.command == "sprint": cmd_sprint()
    elif args.command == "tc":     cmd_tc()
    elif args.command == "coverage": cmd_coverage()
    elif args.command == "gaps":   cmd_gaps()
    elif args.command == "sync":   cmd_sync()
