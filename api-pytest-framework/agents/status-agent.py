# ============================================================
# Status Agent -- Synchronisation Allure results -> Jira
# ============================================================
# Lit allure-results/*.json, mappe les statuts des tests vers
# les transitions Jira, et met a jour les issues.
#
# Correspondance statut Allure -> Jira :
#   passed  -> Done
#   failed  -> In Progress  + commentaire avec details d'echec
#   broken  -> In Progress  + commentaire erreur infrastructure
#   skipped -> To Do
#
# Detection de l'issue Jira :
#   1. Label allure @allure.label("jira", "HBAPI-XX")
#   2. Prefixe "TC-XXX" dans le nom du test -> TC_MAP
#
# Usage:
#   python agents/status-agent.py report
#   python agents/status-agent.py sync
#   python agents/status-agent.py sync --dry-run
# ============================================================

import sys
import os
import json
import glob
import time
import requests as _requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from jira_fetcher_agent import JiraClient, JIRA_BASE_URL

PROJECT    = os.getenv("JIRA_PROJECT", "HBAPI")
ALLURE_DIR = os.path.join(os.path.dirname(__file__), "..", "allure-results")
DRY_RUN    = "--dry-run" in sys.argv

# ── Mapping TC-XXX -> Issue Jira ─────────────────────────────────────────────
# Adapter selon votre backlog. Chaque TC pointe vers sa Story HBAPI-XX.
# Mapping granulaire : 1 TC = 1 issue Jira individuelle
# Extrait automatiquement depuis features/*.feature (@tc-XXX  # HBAPI-YY)
TC_MAP = {
    "TC-001": "HBAPI-11", "TC-002": "HBAPI-12", "TC-003": "HBAPI-13",
    "TC-004": "HBAPI-14", "TC-005": "HBAPI-15",
    "TC-006": "HBAPI-16", "TC-007": "HBAPI-17", "TC-008": "HBAPI-18",
    "TC-009": "HBAPI-19", "TC-010": "HBAPI-20", "TC-011": "HBAPI-21",
    "TC-012": "HBAPI-22",
    "TC-013": "HBAPI-23", "TC-014": "HBAPI-24", "TC-015": "HBAPI-25",
    "TC-016": "HBAPI-26", "TC-017": "HBAPI-27", "TC-018": "HBAPI-28",
    "TC-019": "HBAPI-29",
    "TC-020": "HBAPI-30", "TC-021": "HBAPI-31", "TC-022": "HBAPI-32",
    "TC-023": "HBAPI-33", "TC-024": "HBAPI-34", "TC-025": "HBAPI-35",
    "TC-026": "HBAPI-36", "TC-027": "HBAPI-37", "TC-028": "HBAPI-38",
    "TC-029": "HBAPI-39", "TC-030": "HBAPI-40", "TC-031": "HBAPI-41",
    "TC-032": "HBAPI-42", "TC-033": "HBAPI-43", "TC-034": "HBAPI-44",
    "TC-035": "HBAPI-45", "TC-036": "HBAPI-46", "TC-037": "HBAPI-47",
    "TC-038": "HBAPI-48", "TC-039": "HBAPI-49", "TC-040": "HBAPI-50",
    "TC-041": "HBAPI-51", "TC-042": "HBAPI-52", "TC-043": "HBAPI-53",
    "TC-044": "HBAPI-54",
    "TC-045": "HBAPI-55", "TC-046": "HBAPI-56", "TC-047": "HBAPI-57",
    "TC-048": "HBAPI-58", "TC-049": "HBAPI-59", "TC-050": "HBAPI-60",
    "TC-051": "HBAPI-61",
}

STATUS_TARGET = {
    "passed":  "Terminé",    # transition name : "Terminé"
    "failed":  "En cours",
    "broken":  "En cours",
    "skipped": "A faire",
}

STATUS_ICON = {
    "passed":  "\033[32m[PASS]\033[0m",
    "failed":  "\033[31m[FAIL]\033[0m",
    "broken":  "\033[33m[BROKE]\033[0m",
    "skipped": "\033[2m[SKIP]\033[0m",
}

# ── Couleurs ANSI ─────────────────────────────────────────────────────────────

class C:
    @staticmethod
    def ok(s):   return f"\033[32m{s}\033[0m"
    @staticmethod
    def err(s):  return f"\033[31m{s}\033[0m"
    @staticmethod
    def warn(s): return f"\033[33m{s}\033[0m"
    @staticmethod
    def info(s): return f"\033[36m{s}\033[0m"
    @staticmethod
    def bold(s): return f"\033[1m{s}\033[0m"
    @staticmethod
    def dim(s):  return f"\033[2m{s}\033[0m"


# ── Lecture des résultats Allure ──────────────────────────────────────────────

def read_allure_results():
    allure_path = os.path.normpath(ALLURE_DIR)
    if not os.path.isdir(allure_path):
        raise FileNotFoundError(f"Dossier allure-results introuvable : {allure_path}")

    pattern = os.path.join(allure_path, "*-result.json")
    files   = glob.glob(pattern)
    results = []

    for filepath in files:
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
            if not data.get("status") or not data.get("name"):
                continue
            results.append({
                "name":       data["name"],
                "status":     data["status"],
                "duration":   (data.get("stop", 0) - data.get("start", 0)),
                "message":    (data.get("statusDetails") or {}).get("message", ""),
                "trace":      (data.get("statusDetails") or {}).get("trace", ""),
                "labels":     data.get("labels", []),
                "file":       os.path.basename(filepath),
            })
        except Exception:
            pass

    return results


# ── Extraction clé Jira ───────────────────────────────────────────────────────

def extract_jira_key(result):
    import re

    # Priorité 1 : label @allure.label("jira", "HBAPI-XX")
    for label in result["labels"]:
        if label.get("name") in ("jira", "issue") and label.get("value"):
            return label["value"]

    # Priorité 2 : tag label "tc-XXX" (injecté par pytest-bdd depuis les markers @tc-XXX)
    for label in result["labels"]:
        if label.get("name") == "tag":
            m = re.match(r"tc-?(\d+)", label.get("value", ""), re.IGNORECASE)
            if m:
                tc_id = f"TC-{int(m.group(1)):03d}"
                if tc_id in TC_MAP:
                    return TC_MAP[tc_id]

    # Priorité 3 : nom du test pytest-bdd format test_tcXXX__...
    match = re.search(r"_tc(\d{3})_", result["name"], re.IGNORECASE)
    if match:
        tc_id = f"TC-{match.group(1)}"
        if tc_id in TC_MAP:
            return TC_MAP[tc_id]

    return None


# ── Agrégation par issue ──────────────────────────────────────────────────────

def aggregate_by_issue(results):
    issues = {}
    for r in results:
        key = extract_jira_key(r)
        if not key:
            continue
        if key not in issues:
            issues[key] = {"passed": [], "failed": [], "broken": [], "skipped": []}
        bucket = issues[key].get(r["status"])
        if bucket is not None:
            bucket.append(r)
    return issues


def resolve_target_status(group):
    if group["broken"]:  return "En cours"
    if group["failed"]:  return "En cours"
    if group["passed"] and not group["failed"] and not group["broken"]:
        return "Terminé"
    if group["skipped"]: return "A faire"
    return None


# ── Commentaire ADF ───────────────────────────────────────────────────────────

def build_comment_adf(issue_key, group):
    total = sum(len(v) for v in group.values())
    p = len(group["passed"])
    f = len(group["failed"])
    b = len(group["broken"])
    s = len(group["skipped"])
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    lines = [
        f"[STATUS-AGENT] Resultats Allure -- {now}",
        f"Issue : {issue_key} | Total : {total} | PASS: {p} | FAIL: {f} | BROKEN: {b} | SKIP: {s}",
    ]

    if f > 0:
        lines.append("--- ECHECS ---")
        for r in group["failed"]:
            lines.append(f"[FAIL] {r['name']}")
            if r["message"]:
                lines.append(f"       {r['message'][:200]}")

    if b > 0:
        lines.append("--- CASSES (erreur infrastructure) ---")
        for r in group["broken"]:
            lines.append(f"[BROKEN] {r['name']}")
            if r["message"]:
                lines.append(f"         {r['message'][:200]}")

    if s > 0:
        lines.append("--- IGNORES ---")
        for r in group["skipped"]:
            lines.append(f"[SKIP] {r['name']}")

    lines.append("Source : allure-results/ | Framework : api-pytest-framework")

    return {
        "body": {
            "type":    "doc",
            "version": 1,
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": line}]}
                for line in lines
            ],
        }
    }


# ── Transitions Jira (cache) ──────────────────────────────────────────────────

_transition_cache = {}

def get_transition_id(jira, issue_key, target_status_name):
    if issue_key not in _transition_cache:
        data = jira._get(f"/issue/{issue_key}/transitions")
        _transition_cache[issue_key] = data.get("transitions", [])

    target_lower = target_status_name.lower().strip()
    for tr in _transition_cache[issue_key]:
        tr_name = tr.get("name", "").lower().strip()
        to_name  = tr.get("to", {}).get("name", "").lower().strip()
        # Matcher sur le nom de la transition OU le nom du statut destination
        if tr_name == target_lower or to_name == target_lower:
            return tr["id"]
        # Fallback partiel (ex: "terminé" dans "terminé(e)")
        if target_lower in to_name or target_lower in tr_name:
            return tr["id"]
    return None


# ── Commande : report ─────────────────────────────────────────────────────────

def cmd_report(results, issues):
    mapped   = [r for r in results if extract_jira_key(r)]
    unmapped = [r for r in results if not extract_jira_key(r)]

    counts = {"passed": 0, "failed": 0, "broken": 0, "skipped": 0}
    for r in results:
        if r["status"] in counts:
            counts[r["status"]] += 1

    print(f"\n{C.bold('--- Resultats Allure ---')}")
    print(f"  Total fichiers    : {len(results)}")
    print(f"  Avec cle Jira     : {len(mapped)}")
    print(f"  Sans cle Jira     : {len(unmapped)}")
    print(f"\n  {C.ok('PASS')}    : {counts['passed']}")
    print(f"  {C.err('FAIL')}    : {counts['failed']}")
    print(f"  {C.warn('BROKEN')} : {counts['broken']}")
    print(f"  {C.dim('SKIP')}    : {counts['skipped']}")

    print(f"\n{C.bold('--- Par issue Jira ---')}")
    for key, group in issues.items():
        target = resolve_target_status(group)
        total  = sum(len(v) for v in group.values())
        print(f"\n  {C.bold(key)}  ->  {C.info(target or '?')}  ({total} tests)")
        for status, items in group.items():
            if items:
                print(f"    {STATUS_ICON[status]} {len(items)}x")
                for r in items[:3]:
                    print(f"        {C.dim(r['name'][:70])}")
                if len(items) > 3:
                    print(f"        {C.dim(f'... et {len(items) - 3} autres')}")

    if unmapped:
        print(f"\n{C.warn(f'[!] {len(unmapped)} test(s) sans cle Jira detectee :')}")
        for r in unmapped[:10]:
            print(f"  {STATUS_ICON.get(r['status'], r['status'])} {r['name'][:80]}")
        if len(unmapped) > 10:
            print(f"  {C.dim(f'... et {len(unmapped) - 10} autres')}")
        print(f"\n  {C.dim('Astuce : ajoutez @allure.label(\"jira\", \"HBAPI-XX\") a vos tests')}")
        print(f"  {C.dim('         ou \"TC-XXX\" dans le nom du test.')}")
    print()


# ── Commande : sync ───────────────────────────────────────────────────────────

def cmd_sync(jira, issues):
    synced = 0
    errors = 0

    print(f"\n{C.bold('--- Synchronisation Allure -> Jira ---')}")
    if DRY_RUN:
        print(C.warn("  MODE DRY-RUN -- aucune mise a jour Jira"))

    for issue_key, group in issues.items():
        target_status = resolve_target_status(group)
        if not target_status:
            print(f"  {C.dim(issue_key)} : statut indetermine -- ignore")
            continue

        total = sum(len(v) for v in group.values())
        p = len(group["passed"])
        f = len(group["failed"])
        b = len(group["broken"])

        print(f"\n  {C.bold(issue_key)}  {C.dim(f'{total} tests | P:{p} F:{f} B:{b}')}")
        print(f"    Statut cible : {C.info(target_status)}")

        if DRY_RUN:
            print(f"    {C.dim('[DRY-RUN] Aurait mis a jour le statut et ajoute un commentaire')}")
            synced += 1
            continue

        try:
            # 1. Statut actuel
            issue          = jira._get(f"/issue/{issue_key}?fields=status")
            current_status = issue["fields"]["status"]["name"]

            if current_status.lower() == target_status.lower():
                print(f"    {C.dim(f'Statut deja correct : {current_status}')}")
            else:
                transition_id = get_transition_id(jira, issue_key, target_status)
                if transition_id:
                    # POST /transitions retourne 204 No Content -- ne pas appeler .json()
                    resp = _requests.post(
                        f"{jira.base}/issue/{issue_key}/transitions",
                        json={"transition": {"id": transition_id}},
                        auth=jira.auth,
                        headers=jira.headers,
                        verify=False,
                    )
                    resp.raise_for_status()
                    print(C.ok(f"    [OK] Transition : {current_status} -> {target_status}"))
                else:
                    print(C.warn(f"    [!] Transition vers \"{target_status}\" non disponible (actuel : {current_status})"))

            # 2. Commentaire avec résultat du test
            comment_payload = build_comment_adf(issue_key, group)
            jira._post(f"/issue/{issue_key}/comment", comment_payload)
            print(C.ok("    [OK] Commentaire ajoute"))
            synced += 1

            time.sleep(0.3)  # éviter le rate-limiting Jira

        except Exception as e:
            print(C.err(f"    [ERR] {str(e).splitlines()[0]}"))
            errors += 1

    print(f"\n{C.bold('--- Bilan ---')}")
    print(C.ok(f"  Issues syncees  : {synced}"))
    if errors:
        print(C.err(f"  Erreurs         : {errors}"))
    print()


def print_help():
    print(f"""
{C.bold('Status Agent -- Synchronisation Allure -> Jira')}

{C.bold('Usage :')}
  python agents/status-agent.py report          # Rapport sans mise a jour Jira
  python agents/status-agent.py sync            # Synchronise les statuts Jira
  python agents/status-agent.py sync --dry-run  # Simulation sans ecriture

{C.bold('Detection automatique de l\'issue Jira :')}
  1. Label  : @allure.label("jira", "HBAPI-XX") dans le test
  2. Prefixe: "TC-001 ..." mappe via TC_MAP en haut du fichier
  3. Feature: label feature=booking -> HBAPI-4 (fallback)

{C.bold('Correspondance statuts :')}
  passed  -> Done
  failed  -> In Progress  + commentaire
  broken  -> In Progress  + commentaire
  skipped -> To Do
""")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "report"

    print(f"{C.bold('===================================================')} ")
    print(f"{C.bold(f'  STATUS AGENT -- {PROJECT}')}")
    if DRY_RUN:
        print(C.warn("  [DRY-RUN]"))
    print(f"{C.bold('===================================================')} ")

    if cmd in ("-h", "--help", "help"):
        print_help()
        return

    try:
        print(f"\n{C.info('[>] Lecture de allure-results/ ...')}")
        results = read_allure_results()

        if not results:
            print(C.warn(f"\n  Aucun resultat trouve dans {os.path.normpath(ALLURE_DIR)}"))
            print(C.dim("  Lancez d'abord : python -m pytest tests/ --alluredir=allure-results\n"))
            return

        print(C.ok(f"  {len(results)} resultat(s) charge(s)"))

        issues = aggregate_by_issue(results)
        if not issues:
            print(C.warn("\n  Aucune issue Jira detectee dans les resultats."))
            print(C.dim('  Ajoutez @allure.label("jira", "HBAPI-XX") a vos tests.\n'))
            cmd_report(results, {})
            return

        print(C.ok(f"  {len(issues)} issue(s) Jira identifiee(s)\n"))

        jira = JiraClient()
        jira.project = PROJECT

        cmd_report(results, issues)

        if cmd == "sync":
            cmd_sync(jira, issues)

    except FileNotFoundError as e:
        print(C.err(f"\n[ERR] {e}"))
        sys.exit(1)
    except Exception as e:
        print(C.err(f"\n[ERR] {str(e).splitlines()[0]}"))
        sys.exit(1)


if __name__ == "__main__":
    main()
