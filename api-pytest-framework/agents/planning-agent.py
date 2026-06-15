# ============================================================
# Planning Agent — Jira · Stories · Sprint · Test Cases
# ============================================================
# Absorbe : user-stories-agent · sprint-agent · jira-agent ·
#           jira-ticket-agent · test-case-agent · status-agent · create_story
#
# Commandes :
#   python agents/planning-agent.py setup            → configure le projet Jira (HBAPI)
#   python agents/planning-agent.py stories          → crée les 8 US dans Jira
#   python agents/planning-agent.py sprint list      → liste les sprints
#   python agents/planning-agent.py sprint create "Sprint 2" 2026-07-01 2026-07-21
#   python agents/planning-agent.py sprint start <id>
#   python agents/planning-agent.py sprint close <id>
#   python agents/planning-agent.py tc               → crée les TCs (sous-tâches Jira)
#   python agents/planning-agent.py tickets          → crée des bugs Jira depuis les échecs Allure
#   python agents/planning-agent.py sync             → synchronise Allure → Jira (statuts)
# ============================================================

import sys, os, json, glob, re, time, requests
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm
from jira_fetcher_agent import JiraClient, JIRA_BASE_URL

FRAMEWORK   = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS_DIR = os.path.join(FRAMEWORK, "allure-results")
DOCS_DIR    = os.path.join(FRAMEWORK, "docs")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

PROJECT_KEY = "HBAPI"
BOARD_NAME  = "Hotel Booking — API Automation"

# Mapping Allure → Jira transitions
STATUS_MAP = {
    "passed":  "Done",
    "failed":  "In Progress",
    "broken":  "In Progress",
    "skipped": "To Do",
}

# 8 User Stories de la plateforme Hotel Booking API
US_DEFINITIONS = [
    {"id": "US-001", "endpoint": "POST /auth",          "summary": "Token d'authentification",        "priority": "Highest"},
    {"id": "US-002", "endpoint": "GET /booking",        "summary": "Liste des réservations",          "priority": "High"},
    {"id": "US-003", "endpoint": "GET /booking/{id}",   "summary": "Détail d'une réservation",        "priority": "High"},
    {"id": "US-004", "endpoint": "POST /booking",       "summary": "Création d'une réservation",      "priority": "High"},
    {"id": "US-005", "endpoint": "PUT /booking/{id}",   "summary": "Mise à jour complète",            "priority": "Medium"},
    {"id": "US-006", "endpoint": "PATCH /booking/{id}", "summary": "Mise à jour partielle",           "priority": "Medium"},
    {"id": "US-007", "endpoint": "DELETE /booking/{id}","summary": "Suppression d'une réservation",   "priority": "Medium"},
    {"id": "US-008", "endpoint": "GET /ping",           "summary": "Health check de l'API",           "priority": "Low"},
]


# ── Helpers ────────────────────────────────────────────────────────────────

def jira_post(path: str, payload: dict, jira: JiraClient) -> dict:
    resp = requests.post(
        f"{JIRA_BASE_URL}{path}",
        json=payload, auth=jira.auth, headers=jira.headers, verify=False
    )
    return resp.json() if resp.status_code in (200, 201) else {"error": resp.text[:200], "status": resp.status_code}


def jira_get(path: str, jira: JiraClient) -> dict:
    resp = requests.get(
        f"{JIRA_BASE_URL}{path}",
        auth=jira.auth, headers=jira.headers, verify=False
    )
    return resp.json() if resp.status_code == 200 else {}


def load_allure_results() -> list:
    results = []
    for f in glob.glob(os.path.join(RESULTS_DIR, "*-result.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
            tags  = [lb["value"] for lb in d.get("labels", []) if lb["name"] == "tag"]
            tc    = next((t for t in tags if re.match(r"tc-\d+", t)), None)
            us    = next((t for t in tags if re.match(r"us-\d+", t)), None)
            results.append({
                "name":   d.get("name", "?"),
                "status": d.get("status", "unknown"),
                "tc":     tc, "us": us,
                "message": (d.get("statusDetails") or {}).get("message", "")[:200],
            })
        except Exception:
            pass
    return results


# ── Setup — Configuration Jira ─────────────────────────────────────────────

def cmd_setup():
    print(f"\n{W}PLANNING AGENT — Setup Jira{E}\n")
    jira = JiraClient()

    # Vérifier la connexion
    myself = jira_get("/rest/api/3/myself", jira)
    if "accountId" not in myself:
        print(f"{R}  [ERR] Jira inaccessible. Verifiez JIRA_URL / JIRA_EMAIL / JIRA_TOKEN dans .env{E}")
        return

    print(f"  {G}Connecte en tant que : {myself.get('displayName','?')}{E}")

    # Créer le projet si absent
    projects = jira_get("/rest/api/3/project/search?query=HBAPI", jira)
    existing = [p for p in projects.get("values", []) if p.get("key") == PROJECT_KEY]

    if existing:
        print(f"  {Y}Projet {PROJECT_KEY} existe deja.{E}")
    else:
        print(f"  Creation du projet {PROJECT_KEY}...")
        payload = {
            "key":          PROJECT_KEY,
            "name":         BOARD_NAME,
            "projectTypeKey": "software",
            "template":     "com.pyxis.greenhopper.jira:gh-scrum-template",
        }
        result = jira_post("/rest/api/3/project", payload, jira)
        if "key" in result:
            print(f"  {G}Projet cree : {result['key']}{E}")
        else:
            print(f"  {Y}Erreur creation : {result}{E}")


# ── Stories — Création des User Stories ────────────────────────────────────

def create_user_story(us: dict, jira: JiraClient) -> str:
    # Générer la description via LLM
    messages = [{"role": "user", "content": (
        f"Génère une user story Jira pour cet endpoint API :\n\n"
        f"ID       : {us['id']}\n"
        f"Endpoint : {us['endpoint']}\n"
        f"Résumé   : {us['summary']}\n\n"
        f"Format : 'En tant que... je veux... afin de...' + critères d'acceptation (3 points).\n"
        f"Max 300 caractères. En français."
    )}]
    description_text = llm.chat(messages)

    payload = {
        "fields": {
            "project":     {"key": PROJECT_KEY},
            "summary":     f"[{us['id']}] {us['endpoint']} — {us['summary']}",
            "description": {
                "type": "doc", "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": description_text}]}]
            },
            "issuetype": {"name": "Story"},
            "priority":  {"name": us["priority"]},
            "labels":    [us["id"].lower().replace("-", ""), "api-automation"],
        }
    }
    result = jira_post("/rest/api/3/issue", payload, jira)
    return result.get("key", "")


def cmd_stories(dry_run: bool = False):
    print(f"\n{W}PLANNING AGENT — User Stories ({len(US_DEFINITIONS)} US){E}\n")
    jira = JiraClient()
    created = []

    for us in US_DEFINITIONS:
        print(f"  {C}[{us['id']}]{E} {us['endpoint']:<25}  {us['summary']}...", end=" ", flush=True)
        if dry_run:
            print(f"{Y}[DRY-RUN]{E}")
            continue
        key = create_user_story(us, jira)
        if key:
            created.append(key)
            print(f"{G}{key}{E}")
        else:
            print(f"{R}Erreur{E}")
        time.sleep(0.5)  # Rate limiting

    print(f"\n  {G}{len(created)} US creees.{E}")
    return created


# ── Sprint — Gestion des sprints ───────────────────────────────────────────

def get_board_id(jira: JiraClient) -> str:
    boards = jira_get(f"/rest/agile/1.0/board?projectKeyOrId={PROJECT_KEY}", jira)
    values = boards.get("values", [])
    return str(values[0]["id"]) if values else ""


def cmd_sprint(sub: str = "list", name: str = None, start: str = None, end: str = None, goal: str = None, sprint_id: str = None):
    print(f"\n{W}PLANNING AGENT — Sprint [{sub}]{E}\n")
    jira = JiraClient()

    if sub == "list":
        board_id = get_board_id(jira)
        if not board_id:
            print(f"{R}  Board non trouve pour {PROJECT_KEY}.{E}")
            return
        sprints = jira_get(f"/rest/agile/1.0/board/{board_id}/sprint?state=active,future,closed&maxResults=10", jira)
        for s in sprints.get("values", []):
            state = s.get("state", "?")
            color = G if state == "active" else Y if state == "future" else C
            print(f"  #{s['id']}  {color}{state:<8}{E}  {s.get('name','?'):<30}  {s.get('startDate','?')[:10]} → {s.get('endDate','?')[:10]}")

    elif sub == "create" and name:
        board_id = get_board_id(jira)
        payload = {
            "name":      name,
            "startDate": f"{start}T00:00:00.000Z" if start else "",
            "endDate":   f"{end}T23:59:59.000Z" if end else "",
            "goal":      goal or f"Objectif du {name}",
            "originBoardId": int(board_id),
        }
        result = jira_post("/rest/agile/1.0/sprint", payload, jira)
        if "id" in result:
            print(f"  {G}Sprint cree : #{result['id']} — {name}{E}")
        else:
            print(f"  {R}Erreur : {result}{E}")

    elif sub in ("start", "close") and sprint_id:
        state_map = {"start": "active", "close": "closed"}
        payload   = {"state": state_map[sub]}
        resp = requests.post(
            f"{JIRA_BASE_URL}/rest/agile/1.0/sprint/{sprint_id}",
            json=payload, auth=jira.auth, headers=jira.headers, verify=False
        )
        if resp.status_code in (200, 204):
            print(f"  {G}Sprint #{sprint_id} -> {state_map[sub]}{E}")
        else:
            print(f"  {R}Erreur {resp.status_code}: {resp.text[:100]}{E}")


# ── TC — Test Cases Jira ───────────────────────────────────────────────────

def cmd_tc(us_filter: str = None, dry_run: bool = False):
    print(f"\n{W}PLANNING AGENT — Test Cases{E}\n")
    jira   = JiraClient()
    us_list = [us for us in US_DEFINITIONS if not us_filter or us["id"] == us_filter.upper()]

    for us in us_list:
        us_key = us["id"].lower().replace("-", "")
        print(f"\n  {C}[{us['id']}]{E} {us['endpoint']} — {us['summary']}")

        # Générer les TCs via LLM
        messages = [{"role": "user", "content": (
            f"Génère 3 cas de test pour cet endpoint API :\n\n"
            f"Endpoint : {us['endpoint']}\n"
            f"Résumé   : {us['summary']}\n\n"
            f"Format JSON : {{\"test_cases\": [{{\"title\": \"...\", \"type\": \"positif|negatif|securite\", \"steps\": [\"...\"], \"expected\": \"...\"}}]}}"
        )}]
        try:
            schema = {
                "type": "object",
                "properties": {"test_cases": {"type": "array", "items": {"type": "object",
                    "properties": {"title": {"type": "string"}, "type": {"type": "string"},
                                   "steps": {"type": "array", "items": {"type": "string"}}, "expected": {"type": "string"}},
                    "required": ["title", "type", "expected"]}}},
                "required": ["test_cases"]
            }
            result = llm.chat_structured(messages, schema)
            test_cases = result.get("test_cases", [])
        except Exception:
            test_cases = []

        for tc in test_cases:
            title = f"[{us['id']}][{tc.get('type','?').upper()}] {tc.get('title','?')}"
            print(f"    {Y}TC{E}  {title[:70]}", end=" ", flush=True)
            if dry_run:
                print(f"{Y}[DRY-RUN]{E}")
                continue

            # Chercher l'issue US parente
            jql_result = jira_get(
                f"/rest/api/3/issue/picker?query=[{us['id']}]&currentJQL=project={PROJECT_KEY}", jira
            )
            parent_key = ""

            payload = {
                "fields": {
                    "project":     {"key": PROJECT_KEY},
                    "summary":     title,
                    "issuetype":   {"name": "Subtask" if parent_key else "Task"},
                    "labels":      [us_key, "tc", tc.get("type", "")],
                }
            }
            if parent_key:
                payload["fields"]["parent"] = {"key": parent_key}

            tc_result = jira_post("/rest/api/3/issue", payload, jira)
            if "key" in tc_result:
                print(f"{G}{tc_result['key']}{E}")
            else:
                print(f"{R}Erreur{E}")
            time.sleep(0.3)


# ── Tickets — Bugs depuis les échecs Allure ────────────────────────────────

def cmd_tickets(dry_run: bool = False):
    print(f"\n{W}PLANNING AGENT — Bug Tickets depuis Allure{E}\n")
    jira    = JiraClient()
    results = load_allure_results()
    failures = [r for r in results if r["status"] in ("failed", "broken")]

    if not failures:
        print(f"{G}  Aucun echec Allure — aucun ticket a creer.{E}")
        return

    print(f"  {len(failures)} echec(s) -> tickets Jira\n")
    created = []

    for f in failures:
        # Générer le titre du bug via LLM
        messages = [{"role": "user", "content": (
            f"Génère un titre de bug Jira clair et concis (max 80 chars, en français).\n\n"
            f"Test en echec : {f['name']}\n"
            f"TC           : {f['tc'] or 'N/A'}\n"
            f"Erreur       : {f['message'] or 'aucun message'}\n\n"
            f"Format : [TC-XXX] Description courte du bug"
        )}]
        summary = llm.chat(messages).strip()[:120]

        print(f"  {R}x{E} {f['tc'] or '?':>8}  {summary[:60]}", end=" ", flush=True)
        if dry_run:
            print(f"{Y}[DRY-RUN]{E}")
            continue

        payload = {
            "fields": {
                "project":     {"key": PROJECT_KEY},
                "summary":     summary,
                "description": {
                    "type": "doc", "version": 1,
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": (
                        f"Test: {f['name']}\n"
                        f"TC: {f['tc'] or 'N/A'} | US: {f['us'] or 'N/A'}\n"
                        f"Statut: {f['status']}\n\n"
                        f"Erreur:\n{f['message'] or 'Aucun message'}"
                    )}]}]
                },
                "issuetype": {"name": "Bug"},
                "priority":  {"name": "High"},
                "labels":    ["automated-failure", f['tc'] or "no-tc"],
            }
        }
        result = jira_post("/rest/api/3/issue", payload, jira)
        if "key" in result:
            created.append(result["key"])
            print(f"{G}{result['key']}{E}")
        else:
            print(f"{R}Erreur{E}")
        time.sleep(0.5)

    print(f"\n  {G}{len(created)} ticket(s) Bug crees.{E}")
    return created


# ── Sync — Allure → Jira statuts ──────────────────────────────────────────

def cmd_sync():
    print(f"\n{W}PLANNING AGENT — Sync Allure → Jira{E}\n")
    jira    = JiraClient()
    results = load_allure_results()

    synced = 0
    for r in results:
        tc  = r.get("tc")
        if not tc:
            continue

        allure_status = r.get("status", "unknown")
        jira_status   = STATUS_MAP.get(allure_status)
        if not jira_status:
            continue

        # Chercher le TC dans Jira par label
        search = jira_get(f"/rest/api/3/issue/picker?query={tc}&currentJQL=project={PROJECT_KEY}+AND+labels={tc}", jira)
        issues = search.get("sections", [{}])[0].get("issues", []) if search else []

        for issue in issues[:1]:
            issue_key = issue.get("key")
            if not issue_key:
                continue
            transitions = jira_get(f"/rest/api/3/issue/{issue_key}/transitions", jira)
            target = next(
                (t for t in transitions.get("transitions", []) if jira_status.lower() in t.get("name","").lower()),
                None
            )
            if target:
                resp = requests.post(
                    f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/transitions",
                    json={"transition": {"id": target["id"]}},
                    auth=jira.auth, headers=jira.headers, verify=False
                )
                if resp.status_code in (200, 204):
                    print(f"  {G}{tc}{E} {issue_key} -> {jira_status}")
                    synced += 1

    print(f"\n  {G}{synced} issue(s) synchronisee(s).{E}")


# ── Main ───────────────────────────────────────────────────────────────────

def print_help():
    print(f"""
{W}PLANNING AGENT — Jira · User Stories · Sprint · Test Cases{E}

  python agents/planning-agent.py setup                  Configure le projet Jira (HBAPI)
  python agents/planning-agent.py stories                Crée les 8 US dans Jira
  python agents/planning-agent.py stories --dry-run      Simulation
  python agents/planning-agent.py sprint list            Liste les sprints
  python agents/planning-agent.py sprint create "S2" 2026-07-01 2026-07-21
  python agents/planning-agent.py sprint start <id>     Démarre un sprint
  python agents/planning-agent.py sprint close <id>     Clôture un sprint
  python agents/planning-agent.py tc                     Crée tous les TCs dans Jira
  python agents/planning-agent.py tc US-001             TCs d'une seule US
  python agents/planning-agent.py tickets                Crée les bugs Jira depuis Allure
  python agents/planning-agent.py tickets --dry-run      Simulation
  python agents/planning-agent.py sync                   Synchronise statuts Allure → Jira

{W}Modules absorbes :{E} user-stories-agent · sprint-agent · jira-agent · jira-ticket-agent · test-case-agent · status-agent · create_story
""")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    sub = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("-") else None
    arg = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith("-") else None
    arg2 = sys.argv[4] if len(sys.argv) > 4 else None
    arg3 = sys.argv[5] if len(sys.argv) > 5 else None

    if cmd == "setup":
        cmd_setup()
    elif cmd == "stories":
        cmd_stories(dry_run=dry)
    elif cmd == "sprint":
        cmd_sprint(sub or "list", name=sub if sub != "list" else arg,
                   start=arg, end=arg2, goal=arg3, sprint_id=arg)
    elif cmd == "tc":
        cmd_tc(us_filter=sub, dry_run=dry)
    elif cmd == "tickets":
        cmd_tickets(dry_run=dry)
    elif cmd == "sync":
        cmd_sync()
    else:
        print_help()
