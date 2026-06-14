# ============================================================
# Jira Project Agent — SauceLabs My Demo App
# ============================================================
# Crée un projet Jira "My Demo App" (MDA), crée un sprint,
# et importe toutes les user stories en tant que Stories Jira.
#
# Usage:
#   python agents/jira-project-agent.py create-project   → crée le projet Jira MDA
#   python agents/jira-project-agent.py push-stories     → pousse les US vers le backlog
#   python agents/jira-project-agent.py create-sprint    → crée un sprint avec les US High priority
#   python agents/jira-project-agent.py all              → enchaîne les 3 étapes
#   python agents/jira-project-agent.py status           → vérifie l'état du projet
# ============================================================

import sys, os, json, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "")
JIRA_EMAIL    = os.getenv("JIRA_EMAIL", "")
JIRA_TOKEN    = os.getenv("JIRA_TOKEN", "")

FRAMEWORK = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_DIR  = os.path.join(FRAMEWORK, "docs")

PROJECT_KEY  = "MDA"
PROJECT_NAME = "My Demo App"
SPRINT_NAME  = "Sprint 1 — Core Features"

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"


class JiraProjectClient:
    def __init__(self):
        self.base    = f"{JIRA_BASE_URL}/rest/api/3"
        self.agile   = f"{JIRA_BASE_URL}/rest/agile/1.0"
        self.auth    = HTTPBasicAuth(JIRA_EMAIL, JIRA_TOKEN)
        self.headers = {"Accept": "application/json", "Content-Type": "application/json"}

    def _get(self, url: str) -> dict:
        r = requests.get(url, auth=self.auth, headers=self.headers, verify=False)
        r.raise_for_status()
        return r.json()

    def _post(self, url: str, payload: dict) -> dict:
        r = requests.post(url, json=payload, auth=self.auth, headers=self.headers, verify=False)
        if not r.ok:
            raise RuntimeError(f"POST {url} → {r.status_code}: {r.text[:300]}")
        return r.json()

    def get_my_account_id(self) -> str:
        data = self._get(f"{self.base}/myself")
        return data["accountId"]

    def project_exists(self, key: str) -> bool:
        try:
            self._get(f"{self.base}/project/{key}")
            return True
        except Exception:
            return False

    def create_project(self, account_id: str) -> dict:
        payload = {
            "key":            PROJECT_KEY,
            "name":           PROJECT_NAME,
            "projectTypeKey": "software",
            "projectTemplateKey": "com.pyxis.greenhopper.jira:gh-scrum-template",
            "description":    "SauceLabs My Demo App — Mobile Test Automation (Appium/Android)",
            "leadAccountId":  account_id,
            "assigneeType":   "PROJECT_LEAD",
        }
        return self._post(f"{self.base}/project", payload)

    def get_project_id(self, key: str) -> str:
        data = self._get(f"{self.base}/project/{key}")
        return str(data["id"])

    def get_board_id(self, project_key: str) -> int:
        data = self._get(f"{self.agile}/board?projectKeyOrId={project_key}")
        boards = data.get("values", [])
        if not boards:
            raise RuntimeError(f"Aucun board trouvé pour le projet {project_key}")
        return boards[0]["id"]

    def create_sprint(self, board_id: int, name: str) -> dict:
        payload = {
            "name":          name,
            "originBoardId": board_id,
            "goal":          "Implémenter et tester les fonctionnalités core : Login, Catalog, Cart, Checkout"
        }
        return self._post(f"{self.agile}/sprint", payload)

    def create_story(self, project_key: str, story: dict) -> dict:
        description_text = (
            f"As a {story.get('as_a', 'user')}, "
            f"I want {story.get('i_want', '')}, "
            f"so that {story.get('so_that', '')}.\n\n"
            f"Gherkin:\n{story.get('gherkin', '')}\n\n"
            f"Acceptance Criteria:\n" +
            "\n".join(f"• {ac}" for ac in story.get("acceptance_criteria", []))
        )

        priority_map = {"High": "High", "Medium": "Medium", "Low": "Low"}

        payload = {
            "fields": {
                "project":     {"key": project_key},
                "issuetype":   {"name": "Story"},
                "summary":     story.get("title", "User Story"),
                "priority":    {"name": priority_map.get(story.get("priority", "Medium"), "Medium")},
                "labels":      story.get("labels", ["mobile", "android", "appium"]),
                "description": {
                    "type": "doc", "version": 1,
                    "content": [{
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description_text}]
                    }]
                }
            }
        }

        # story_points maps to customfield_10016 in most Jira instances
        story_points = story.get("story_points")
        if story_points:
            payload["fields"]["customfield_10016"] = float(story_points)

        return self._post(f"{self.base}/issue", payload)

    def add_issue_to_sprint(self, sprint_id: int, issue_keys: list):
        payload = {"issues": issue_keys}
        r = requests.post(
            f"{self.agile}/sprint/{sprint_id}/issue",
            json=payload, auth=self.auth, headers=self.headers, verify=False
        )
        if not r.ok:
            raise RuntimeError(f"Add to sprint → {r.status_code}: {r.text[:200]}")


def load_stories() -> list:
    path = os.path.join(DOCS_DIR, "user-stories-mydemoapp.json")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"user-stories-mydemoapp.json introuvable. "
            f"Lance d'abord : python agents/userstory-generator-agent.py generate"
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def cmd_create_project():
    print(f"\n{W}JIRA PROJECT AGENT — Création du projet{E}\n")
    client = JiraProjectClient()

    if client.project_exists(PROJECT_KEY):
        print(f"  {Y}Projet {PROJECT_KEY} existe déjà — skip création.{E}")
        return PROJECT_KEY

    print(f"  Récupération de l'account ID...", end=" ", flush=True)
    account_id = client.get_my_account_id()
    print(f"{G}{account_id[:20]}...{E}")

    print(f"  Création du projet '{PROJECT_NAME}' (clé: {PROJECT_KEY})...", end=" ", flush=True)
    result = client.create_project(account_id)
    print(f"{G}✅ Créé (ID: {result.get('id', '?')}){E}")

    print(f"\n  {G}Projet Jira créé :{E}")
    print(f"  URL : {JIRA_BASE_URL}/jira/software/projects/{PROJECT_KEY}/boards")

    return PROJECT_KEY


def cmd_push_stories():
    print(f"\n{W}JIRA PROJECT AGENT — Import des user stories{E}\n")
    client  = JiraProjectClient()
    stories = load_stories()

    if not client.project_exists(PROJECT_KEY):
        print(f"{R}Projet {PROJECT_KEY} non trouvé — lance d'abord create-project{E}")
        return []

    print(f"  {len(stories)} user stories à importer...\n")
    created_keys = []
    errors       = []

    for i, story in enumerate(stories, 1):
        title = story.get("title", "?")[:50]
        print(f"  [{i:2}/{len(stories)}] {story.get('id','?'):<8} {title}...", end=" ", flush=True)
        try:
            result = client.create_story(PROJECT_KEY, story)
            key    = result.get("key", "?")
            created_keys.append(key)
            story["jira_key"] = key
            prio_color = R if story.get("priority") == "High" else Y if story.get("priority") == "Medium" else G
            print(f"{prio_color}{key}{E} {G}✓{E}")
            time.sleep(0.3)
        except Exception as ex:
            errors.append({"story": story.get("id"), "error": str(ex)})
            print(f"{R}✗ {str(ex)[:60]}{E}")

    with open(os.path.join(DOCS_DIR, "user-stories-mydemoapp.json"), "w", encoding="utf-8") as f:
        json.dump(stories, f, ensure_ascii=False, indent=2)

    print(f"\n{G}✅ {len(created_keys)}/{len(stories)} stories importées{E}")
    if errors:
        print(f"{R}  {len(errors)} erreur(s) :{E}")
        for err in errors:
            print(f"    {err['story']} : {err['error'][:80]}")

    return created_keys


def cmd_create_sprint(story_keys: list = None):
    print(f"\n{W}JIRA PROJECT AGENT — Création du sprint{E}\n")
    client = JiraProjectClient()

    print(f"  Récupération du board ID pour {PROJECT_KEY}...", end=" ", flush=True)
    board_id = client.get_board_id(PROJECT_KEY)
    print(f"{G}board #{board_id}{E}")

    print(f"  Création du sprint '{SPRINT_NAME}'...", end=" ", flush=True)
    sprint = client.create_sprint(board_id, SPRINT_NAME)
    sprint_id = sprint.get("id")
    print(f"{G}✅ Sprint #{sprint_id}{E}")

    if story_keys is None:
        stories = load_stories()
        story_keys = [s.get("jira_key") for s in stories
                      if s.get("jira_key") and s.get("priority") == "High"]

    if story_keys:
        print(f"  Ajout de {len(story_keys)} stories High priority au sprint...", end=" ", flush=True)
        client.add_issue_to_sprint(sprint_id, story_keys)
        print(f"{G}✅{E}")
        print(f"  Stories : {', '.join(story_keys[:10])}", end="")
        if len(story_keys) > 10:
            print(f"... (+{len(story_keys)-10})")
        else:
            print()

    print(f"\n{G}✅ Sprint créé :{E} {JIRA_BASE_URL}/jira/software/projects/{PROJECT_KEY}/boards")


def cmd_all():
    print(f"\n{W}{'='*58}{E}")
    print(f"{W}  JIRA PROJECT AGENT — Pipeline complet{E}")
    print(f"{W}{'='*58}{E}")

    cmd_create_project()
    story_keys = cmd_push_stories()
    high_priority_keys = [k for k, s in zip(story_keys, load_stories())
                          if s.get("priority") == "High"] if story_keys else []
    cmd_create_sprint(high_priority_keys or story_keys[:5])

    print(f"\n{G}{'='*58}{E}")
    print(f"{G}  Pipeline terminé avec succès !{E}")
    print(f"{G}{'='*58}{E}")
    print(f"  Projet  : {JIRA_BASE_URL}/jira/software/projects/{PROJECT_KEY}/boards")


def cmd_status():
    client = JiraProjectClient()
    print(f"\n{W}JIRA PROJECT AGENT — Status{E}\n")

    if client.project_exists(PROJECT_KEY):
        data = client._get(f"{client.base}/project/{PROJECT_KEY}")
        print(f"  {G}✅ Projet {PROJECT_KEY} trouvé{E}")
        print(f"  Nom  : {data.get('name','?')}")
        print(f"  Type : {data.get('projectTypeKey','?')}")
    else:
        print(f"  {R}✗ Projet {PROJECT_KEY} non trouvé{E}")

    stories_path = os.path.join(DOCS_DIR, "user-stories-mydemoapp.json")
    if os.path.exists(stories_path):
        with open(stories_path, encoding="utf-8") as f:
            stories = json.load(f)
        pushed = [s for s in stories if s.get("jira_key")]
        print(f"\n  User stories : {len(stories)} total, {len(pushed)} importées dans Jira")
    else:
        print(f"\n  {Y}User stories non générées encore{E}")


def print_help():
    print(f"""
{W}JIRA PROJECT AGENT — SauceLabs My Demo App{E}

  python agents/jira-project-agent.py create-project   Crée le projet Jira MDA
  python agents/jira-project-agent.py push-stories     Importe les US vers le backlog
  python agents/jira-project-agent.py create-sprint    Crée Sprint 1 avec les stories High
  python agents/jira-project-agent.py all              Pipeline complet (3 étapes)
  python agents/jira-project-agent.py status           Vérifie l'état du projet

{Y}Prérequis :{E}
  1. Générer les user stories d'abord :
     python agents/userstory-generator-agent.py generate
  2. Avoir le .env configuré avec les credentials Jira
""")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "create-project":
        cmd_create_project()
    elif cmd == "push-stories":
        cmd_push_stories()
    elif cmd == "create-sprint":
        cmd_create_sprint()
    elif cmd == "all":
        cmd_all()
    elif cmd == "status":
        cmd_status()
    else:
        print_help()
