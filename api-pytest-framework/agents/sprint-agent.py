# ============================================================
# Sprint Agent -- Gestion du cycle de vie des sprints Jira
# ============================================================
# Usage:
#   python agents/sprint-agent.py list
#   python agents/sprint-agent.py create "Sprint 2" 2026-07-01 2026-07-21 "Objectif"
#   python agents/sprint-agent.py start  <sprintId>
#   python agents/sprint-agent.py close  <sprintId>
#   python agents/sprint-agent.py issues <sprintId>
#   python agents/sprint-agent.py add    <sprintId> HBAPI-3 HBAPI-4
#   python agents/sprint-agent.py backlog                       → issues hors sprint (backlog)
#   python agents/sprint-agent.py move HBAPI-11 "En cours"     → transition manuelle
#   python agents/sprint-agent.py board                         → tableau Kanban du sprint actif
# ============================================================

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(__file__))

from jira_fetcher_agent import JiraClient, JIRA_BASE_URL

PROJECT = os.getenv("JIRA_PROJECT", "HBAPI")

# ── Couleurs ANSI ─────────────────────────────────────────────────────────────

class C:
    OK   = "\033[32m"
    ERR  = "\033[31m"
    WARN = "\033[33m"
    INFO = "\033[36m"
    BOLD = "\033[1m"
    DIM  = "\033[2m"
    RST  = "\033[0m"

    @staticmethod
    def ok(s):   return f"{C.OK}{s}{C.RST}"
    @staticmethod
    def err(s):  return f"{C.ERR}{s}{C.RST}"
    @staticmethod
    def warn(s): return f"{C.WARN}{s}{C.RST}"
    @staticmethod
    def info(s): return f"{C.INFO}{s}{C.RST}"
    @staticmethod
    def bold(s): return f"{C.BOLD}{s}{C.RST}"
    @staticmethod
    def dim(s):  return f"{C.DIM}{s}{C.RST}"


def fmt_date(iso_str):
    if not iso_str:
        return "-"
    return iso_str[:10]


def state_label(state):
    labels = {
        "active":  C.ok("[ACTIF]"),
        "closed":  C.dim("[CLOS]"),
        "future":  C.info("[A VENIR]"),
    }
    return labels.get(state, state)


def to_iso_date(date_str):
    """Convertit YYYY-MM-DD en format Jira: YYYY-MM-DDTHH:MM:SS.000Z"""
    if len(date_str) == 10:
        return f"{date_str}T00:00:00.000Z"
    return date_str


# ── Récupération du board ─────────────────────────────────────────────────────

def get_board_id(jira):
    board = jira.get_board(PROJECT)
    if not board:
        print(C.err(f"  [ERR] Aucun board trouve pour le projet {PROJECT}"))
        sys.exit(1)
    print(C.dim(f"  Board : [{board['id']}] {board['name']}"))
    return board["id"]


# ── Commandes ─────────────────────────────────────────────────────────────────

def cmd_list(jira):
    print(C.bold(f"\n[>] Sprints du projet {PROJECT}"))
    board_id = get_board_id(jira)

    data    = jira._agile("get", f"/board/{board_id}/sprint", params={"maxResults": 50})
    sprints = data.get("values", [])

    if not sprints:
        print(C.warn("  Aucun sprint trouve."))
        return

    print()
    for s in sprints:
        start = fmt_date(s.get("startDate"))
        end   = fmt_date(s.get("endDate"))
        sid   = s["id"]
        line  = f"  {state_label(s['state'])} {C.bold(f'[{sid}]')} {s['name']}  {C.dim(f'{start} -> {end}')}"
        print(line)
        if s.get("goal"):
            print(f"       {C.dim('Objectif : ' + s['goal'])}")
    print()


def cmd_create(jira, name, start_date, end_date, goal=""):
    if len(name) > 30:
        print(C.err(f"[ERR] Nom trop long ({len(name)} chars, max 30) : \"{name}\""))
        sys.exit(1)

    print(C.bold(f'\n[>] Creation du sprint "{name}"'))
    board_id = get_board_id(jira)

    sprint = jira.create_sprint(
        board_id=board_id,
        name=name,
        start_date=to_iso_date(start_date),
        end_date=to_iso_date(end_date),
        goal=goal,
    )

    print(C.ok(f"  [OK] Sprint cree : [{sprint['id']}] {sprint['name']}"))
    print(f"       Periode : {fmt_date(sprint.get('startDate'))} -> {fmt_date(sprint.get('endDate'))}")
    if sprint.get("goal"):
        print(f"       Objectif : {sprint['goal']}")
    print()


def cmd_start(jira, sprint_id):
    print(C.bold(f"\n[>] Demarrage du sprint {sprint_id}"))
    jira._agile("post", f"/sprint/{sprint_id}", json={"state": "active"})

    sprint = jira._agile("get", f"/sprint/{sprint_id}")
    print(C.ok(f"  [OK] Sprint demarre : [{sprint['id']}] {sprint['name']}"))
    print(f"       Periode : {fmt_date(sprint.get('startDate'))} -> {fmt_date(sprint.get('endDate'))}")
    print()


def cmd_close(jira, sprint_id):
    print(C.bold(f"\n[>] Cloture du sprint {sprint_id}"))

    data   = jira._agile("get", f"/sprint/{sprint_id}/issue", params={"maxResults": 50})
    issues = data.get("issues", [])
    open_  = [i for i in issues if i["fields"]["status"]["statusCategory"]["key"] != "done"]

    if open_:
        print(C.warn(f"  [!] {len(open_)} issue(s) non terminees dans ce sprint :"))
        for i in open_:
            print(f"      - {i['key']} : {i['fields']['summary']} [{i['fields']['status']['name']}]")
        print()

    jira._agile("post", f"/sprint/{sprint_id}", json={"state": "closed"})

    sprint = jira._agile("get", f"/sprint/{sprint_id}")
    print(C.ok(f"  [OK] Sprint clos : [{sprint['id']}] {sprint['name']}"))
    print()


def cmd_issues(jira, sprint_id):
    print(C.bold(f"\n[>] Issues du sprint {sprint_id}"))

    data   = jira._agile(
        "get", f"/sprint/{sprint_id}/issue",
        params={"maxResults": 100, "fields": "summary,status,assignee,priority,issuetype"}
    )
    issues = data.get("issues", [])

    if not issues:
        print(C.warn("  Aucune issue dans ce sprint."))
        return

    # Grouper par statut
    groups = {}
    for i in issues:
        status = i["fields"]["status"]["name"]
        groups.setdefault(status, []).append(i)

    for status, items in groups.items():
        print(f"\n  {C.info(status)} ({len(items)})")
        for i in items:
            issue_type = (i["fields"].get("issuetype") or {}).get("name", "")
            priority   = (i["fields"].get("priority")  or {}).get("name", "")
            assignee   = ((i["fields"].get("assignee") or {}).get("displayName") or "Non assigne")
            print(f"    {C.bold(i['key'])}  {i['fields']['summary']}")
            print(f"         {C.dim(f'{issue_type} | {priority} | {assignee}')}")

    done  = sum(1 for i in issues if i["fields"]["status"]["statusCategory"]["key"] == "done")
    print(f"\n  Total : {done}/{len(issues)} terminees\n")


def cmd_add(jira, sprint_id, issue_keys):
    print(C.bold(f"\n[>] Ajout de {len(issue_keys)} issue(s) au sprint {sprint_id}"))
    jira._agile("post", f"/sprint/{sprint_id}/issue", json={"issues": issue_keys})
    print(C.ok(f"  [OK] Issues ajoutees : {', '.join(issue_keys)}"))
    print()


# ── Backlog ───────────────────────────────────────────────────────────────────

def cmd_backlog(jira):
    print(C.bold(f"\n[>] Backlog du projet {PROJECT}"))
    board_id = get_board_id(jira)

    data   = jira._agile(
        "get", f"/board/{board_id}/backlog",
        params={
            "maxResults": 100,
            "fields":     "summary,status,assignee,priority,issuetype,labels",
        }
    )
    issues = data.get("issues", [])

    if not issues:
        print(C.ok("  Backlog vide -- toutes les issues sont dans un sprint."))
        return

    # Grouper par type d'issue
    groups = {}
    for i in issues:
        itype = (i["fields"].get("issuetype") or {}).get("name", "?")
        groups.setdefault(itype, []).append(i)

    total = len(issues)
    print(f"  {total} issue(s) dans le backlog\n")

    for itype, items in sorted(groups.items()):
        print(f"  {C.info(itype.upper())} ({len(items)})")
        print(f"  {'─' * 70}")
        for i in items:
            status   = i["fields"]["status"]["name"]
            priority = (i["fields"].get("priority") or {}).get("name", "-")
            assignee = ((i["fields"].get("assignee") or {}).get("displayName") or "libre")
            labels   = " ".join(f"[{l}]" for l in (i["fields"].get("labels") or []))
            status_c = _status_color(status)
            print(f"  {C.bold(i['key']):<14} {status_c:<22} {C.dim(priority):<10} "
                  f"{i['fields']['summary'][:42]}  {C.dim(assignee)}")
            if labels:
                print(f"  {' ' * 12}  {C.dim(labels)}")
        print()


# ── Move (transition manuelle) ────────────────────────────────────────────────

def _status_color(name: str) -> str:
    n = name.lower()
    if "faire" in n or "todo" in n or "open" in n:
        return C.dim(f"[ ] {name}")
    if "cours" in n or "progress" in n or "doing" in n:
        return C.info(f"[~] {name}")
    if "termin" in n or "done" in n or "closed" in n:
        return C.ok(f"[v] {name}")
    return f"    {name}"


def cmd_move(jira, issue_key: str, target: str):
    print(C.bold(f"\n[>] Transition : {issue_key} -> \"{target}\""))

    # Statut actuel
    issue          = jira._get(f"/issue/{issue_key}?fields=status,summary")
    current_status = issue["fields"]["status"]["name"]
    summary        = issue["fields"]["summary"][:60]

    print(f"  Issue   : {C.bold(issue_key)}  {C.dim(summary)}")
    print(f"  Actuel  : {_status_color(current_status)}")

    if current_status.lower().strip() == target.lower().strip():
        print(C.ok(f"  [OK] Statut deja correct : {current_status}"))
        return

    # Recuperer les transitions disponibles
    tr_data      = jira._get(f"/issue/{issue_key}/transitions")
    transitions  = tr_data.get("transitions", [])

    # Recherche par nom de transition OU nom du statut destination (partiel, insensible casse)
    target_lower = target.lower().strip()
    matched_id   = None
    matched_name = None

    for tr in transitions:
        tr_name = tr.get("name", "").lower().strip()
        to_name = tr.get("to", {}).get("name", "").lower().strip()
        if target_lower in to_name or target_lower in tr_name or to_name in target_lower:
            matched_id   = tr["id"]
            matched_name = tr.get("to", {}).get("name", tr.get("name"))
            break

    if not matched_id:
        print(C.err(f"  [ERR] Transition vers \"{target}\" introuvable."))
        print(f"  Transitions disponibles :")
        for tr in transitions:
            print(f"    ID={tr['id']}  \"{tr['name']}\"  ->  \"{tr['to']['name']}\"")
        return

    # Appliquer la transition (POST renvoie 204 No Content)
    import requests as _req
    resp = _req.post(
        f"{jira.base}/issue/{issue_key}/transitions",
        json={"transition": {"id": matched_id}},
        auth=jira.auth,
        headers=jira.headers,
        verify=False,
    )
    resp.raise_for_status()

    print(C.ok(f"  [OK] {issue_key} : {current_status}  -->  {matched_name}"))
    print()


# ── Board (tableau Kanban du sprint actif) ────────────────────────────────────

def cmd_board(jira):
    print(C.bold(f"\n[>] Tableau Kanban -- sprint actif ({PROJECT})"))
    board_id = get_board_id(jira)

    # Trouver le sprint actif
    data    = jira._agile("get", f"/board/{board_id}/sprint", params={"state": "active"})
    sprints = data.get("values", [])

    if not sprints:
        print(C.warn("  Aucun sprint actif. Utilisez 'sprint-agent.py start <id>'."))
        return

    sprint = sprints[0]
    print(f"  Sprint  : {C.bold(sprint['name'])}  [{sprint['id']}]")
    print(f"  Periode : {fmt_date(sprint.get('startDate'))} -> {fmt_date(sprint.get('endDate'))}")
    if sprint.get("goal"):
        print(f"  Objectif: {C.dim(sprint['goal'])}")

    # Recuperer les issues du sprint actif
    issues_data = jira._agile(
        "get", f"/sprint/{sprint['id']}/issue",
        params={
            "maxResults": 100,
            "fields":     "summary,status,assignee,priority,issuetype,labels",
        }
    )
    issues = issues_data.get("issues", [])

    if not issues:
        print(C.warn("\n  Aucune issue dans ce sprint."))
        return

    # Grouper par colonne (categorie de statut)
    COLUMNS = {
        "new":        ("A FAIRE",   []),
        "indeterminate": ("EN COURS",  []),
        "done":       ("TERMINE",   []),
    }
    for i in issues:
        cat = i["fields"]["status"]["statusCategory"]["key"]
        if cat in COLUMNS:
            COLUMNS[cat][1].append(i)
        else:
            COLUMNS.setdefault(cat, (cat.upper(), []))[1].append(i)

    total = len(issues)
    done  = len(COLUMNS.get("done", ("", []))[1])
    pct   = round(done / total * 100) if total else 0

    # Barre de progression du sprint
    bar_ok  = C.ok("█" * (pct // 5))
    bar_ko  = "░" * (20 - pct // 5)
    print(f"\n  [{bar_ok}{bar_ko}] {pct}%  ({done}/{total} terminees)")

    # Afficher les colonnes
    col_renderers = {
        "new":           lambda s: C.dim(f"[ ] {s}"),
        "indeterminate": lambda s: C.info(f"[~] {s}"),
        "done":          lambda s: C.ok(f"[v] {s}"),
    }

    for cat_key, (col_name, col_issues) in COLUMNS.items():
        if not col_issues:
            continue
        renderer = col_renderers.get(cat_key, lambda s: f"    {s}")
        header   = f"  ── {col_name} ({len(col_issues)}) "
        print(f"\n{C.bold(header)}{'─' * (60 - len(header))}")

        for i in col_issues:
            status   = i["fields"]["status"]["name"]
            priority = (i["fields"].get("priority") or {}).get("name", "-")
            assignee = ((i["fields"].get("assignee") or {}).get("displayName") or "libre")[:18]
            labels   = " ".join(f"[{l}]" for l in (i["fields"].get("labels") or [])[:3])
            itype    = (i["fields"].get("issuetype") or {}).get("name", "")[:8]
            print(f"  {renderer(i['key']):<22} {i['fields']['summary'][:42]:<43} "
                  f"{C.dim(assignee):<20} {C.dim(priority)}")
            if labels:
                print(f"  {'':22} {C.dim(labels)}")

    print()


def print_help():
    print(f"""
{C.bold('Sprint Agent -- Gestion complete des sprints et du backlog Jira')}

{C.bold('Cycle de vie du sprint :')}
  python agents/sprint-agent.py list
  python agents/sprint-agent.py create "Nom Sprint" YYYY-MM-DD YYYY-MM-DD [objectif]
  python agents/sprint-agent.py start  <sprintId>
  python agents/sprint-agent.py close  <sprintId>
  python agents/sprint-agent.py issues <sprintId>
  python agents/sprint-agent.py add    <sprintId> KEY1 KEY2 ...

{C.bold('Backlog et board :')}
  python agents/sprint-agent.py backlog                      Issues hors sprint (backlog produit)
  python agents/sprint-agent.py board                        Tableau Kanban du sprint actif
  python agents/sprint-agent.py move <KEY> "<statut>"        Transition manuelle d'une issue

{C.bold('Statuts disponibles pour move :')}
  "A faire"    |  "En cours"    |  "Termine"
  (matching partiel insensible a la casse)

{C.bold('Exemples :')}
  python agents/sprint-agent.py list
  python agents/sprint-agent.py create "Sprint 2" 2026-07-01 2026-07-21 "US-001 a US-003"
  python agents/sprint-agent.py start 38
  python agents/sprint-agent.py board
  python agents/sprint-agent.py move HBAPI-11 "En cours"
  python agents/sprint-agent.py move HBAPI-11 "Termine"
  python agents/sprint-agent.py backlog
  python agents/sprint-agent.py add 38 HBAPI-3 HBAPI-4 HBAPI-5
  python agents/sprint-agent.py issues 38
  python agents/sprint-agent.py close 38
""")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"{C.bold('===================================================')} ")
    print(f"{C.bold(f'  SPRINT AGENT -- {PROJECT}')}")
    print(f"{C.bold('===================================================')} ")

    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print_help()
        return

    cmd = sys.argv[1]
    args = sys.argv[2:]

    jira = JiraClient()
    jira.project = PROJECT

    try:
        if cmd == "list":
            cmd_list(jira)

        elif cmd == "create":
            if len(args) < 3:
                print(C.err('[ERR] Usage : create "Nom" YYYY-MM-DD YYYY-MM-DD [objectif]'))
                sys.exit(1)
            goal = " ".join(args[3:]) if len(args) > 3 else ""
            cmd_create(jira, args[0], args[1], args[2], goal)

        elif cmd == "start":
            if not args:
                print(C.err("[ERR] Usage : start <sprintId>"))
                sys.exit(1)
            cmd_start(jira, args[0])

        elif cmd == "close":
            if not args:
                print(C.err("[ERR] Usage : close <sprintId>"))
                sys.exit(1)
            cmd_close(jira, args[0])

        elif cmd == "issues":
            if not args:
                print(C.err("[ERR] Usage : issues <sprintId>"))
                sys.exit(1)
            cmd_issues(jira, args[0])

        elif cmd == "add":
            if len(args) < 2:
                print(C.err("[ERR] Usage : add <sprintId> KEY1 KEY2 ..."))
                sys.exit(1)
            cmd_add(jira, args[0], args[1:])

        elif cmd == "backlog":
            cmd_backlog(jira)

        elif cmd == "board":
            cmd_board(jira)

        elif cmd == "move":
            if len(args) < 2:
                print(C.err('[ERR] Usage : move <KEY> "<statut>"'))
                print(C.dim('  Ex : move HBAPI-11 "En cours"'))
                sys.exit(1)
            cmd_move(jira, args[0], " ".join(args[1:]))

        else:
            print(C.err(f"[ERR] Commande inconnue : {cmd}"))
            print_help()
            sys.exit(1)

    except Exception as e:
        print(C.err(f"\n[ERR] {str(e).splitlines()[0]}"))
        sys.exit(1)


if __name__ == "__main__":
    main()
