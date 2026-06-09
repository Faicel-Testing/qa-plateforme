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


def print_help():
    print(f"""
{C.bold('Sprint Agent -- Gestion des sprints Jira')}

{C.bold('Usage :')}
  python agents/sprint-agent.py list
  python agents/sprint-agent.py create "Nom Sprint" YYYY-MM-DD YYYY-MM-DD [objectif]
  python agents/sprint-agent.py start  <sprintId>
  python agents/sprint-agent.py close  <sprintId>
  python agents/sprint-agent.py issues <sprintId>
  python agents/sprint-agent.py add    <sprintId> KEY1 KEY2 ...

{C.bold('Exemples :')}
  python agents/sprint-agent.py list
  python agents/sprint-agent.py create "Sprint 2 - Auth" 2026-07-01 2026-07-21 "Couvrir US-001 a US-003"
  python agents/sprint-agent.py start 38
  python agents/sprint-agent.py issues 38
  python agents/sprint-agent.py add 38 HBAPI-3 HBAPI-4 HBAPI-5
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

        else:
            print(C.err(f"[ERR] Commande inconnue : {cmd}"))
            print_help()
            sys.exit(1)

    except Exception as e:
        print(C.err(f"\n[ERR] {str(e).splitlines()[0]}"))
        sys.exit(1)


if __name__ == "__main__":
    main()
