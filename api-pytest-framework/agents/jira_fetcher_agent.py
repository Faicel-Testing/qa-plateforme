# ============================================
# Jira Fetcher — Client Jira REST API partagé
# ============================================
# Module réutilisable importé par jira-agent, jira-ticket-agent, spec-agent.
# Fournit : get_stories, get_issue, create_story, create_epic, link_to_epic,
#           add_comment.
#
# Usage:
#   from agents.jira_fetcher_agent import JiraClient
#   jira = JiraClient()
#   stories = jira.get_stories()
# ============================================

import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "")
JIRA_EMAIL    = os.getenv("JIRA_EMAIL", "")
JIRA_TOKEN    = os.getenv("JIRA_TOKEN", "")
JIRA_PROJECT  = os.getenv("JIRA_PROJECT", "SCRUM")


class JiraClient:
    def __init__(self):
        self.base = f"{JIRA_BASE_URL}/rest/api/3"
        self.auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_TOKEN)
        self.headers = {"Accept": "application/json", "Content-Type": "application/json"}
        self.project = JIRA_PROJECT

    def _get(self, path: str) -> dict:
        resp = requests.get(f"{self.base}{path}", auth=self.auth,
                            headers=self.headers, verify=False)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, payload: dict) -> dict:
        resp = requests.post(f"{self.base}{path}", json=payload, auth=self.auth,
                             headers=self.headers, verify=False)
        resp.raise_for_status()
        return resp.json()

    def _put(self, path: str, payload: dict) -> dict:
        resp = requests.put(f"{self.base}{path}", json=payload, auth=self.auth,
                            headers=self.headers, verify=False)
        resp.raise_for_status()
        return resp.json()

    def assert_jira(self):
        self._get(f"/project/{self.project}")
        print(f"✅ Jira connecté : {JIRA_BASE_URL} / {self.project}")

    def get_stories(self, max_results: int = 50) -> list[dict]:
        jql = f"project = {self.project} AND issuetype = Story ORDER BY created DESC"
        data = self._get(f"/search/jql?jql={requests.utils.quote(jql)}&maxResults={max_results}"
                         "&fields=summary,status,description,assignee")
        return data.get("issues", [])

    def get_issue(self, key: str) -> dict:
        return self._get(f"/issue/{key}")

    def create_story(self, summary: str, description: str = "", priority: str = "Medium") -> dict:
        payload = {
            "fields": {
                "project":     {"key": self.project},
                "issuetype":   {"name": "Story"},
                "summary":     summary,
                "priority":    {"name": priority},
                "description": {
                    "type":    "doc",
                    "version": 1,
                    "content": [{"type": "paragraph",
                                 "content": [{"type": "text", "text": description}]}]
                }
            }
        }
        return self._post("/issue", payload)

    def create_epic(self, summary: str, description: str = "") -> dict:
        payload = {
            "fields": {
                "project":   {"key": self.project},
                "issuetype": {"name": "Epic"},
                "summary":   summary,
                "description": {
                    "type": "doc", "version": 1,
                    "content": [{"type": "paragraph",
                                 "content": [{"type": "text", "text": description}]}]
                }
            }
        }
        return self._post("/issue", payload)

    def link_to_epic(self, epic_key: str, story_keys: list[str]):
        for key in story_keys:
            self._put(f"/issue/{key}", {"fields": {"parent": {"key": epic_key}}})

    def add_comment(self, issue_key: str, text: str):
        payload = {
            "body": {
                "type": "doc", "version": 1,
                "content": [{"type": "paragraph",
                             "content": [{"type": "text", "text": text}]}]
            }
        }
        self._post(f"/issue/{issue_key}/comment", payload)

    # ── Project ───────────────────────────────────────────────────────────────

    def get_myself(self) -> dict:
        return self._get("/myself")

    def create_project(self, name: str, key: str, description: str = "") -> dict:
        account_id = self.get_myself()["accountId"]
        payload = {
            "key":             key,
            "name":            name,
            "description":     description,
            "projectTypeKey":  "software",
            "projectTemplateKey": "com.pyxis.greenhopper.jira:gh-scrum-template",
            "leadAccountId":   account_id,
        }
        return self._post("/project", payload)

    def get_project(self, key: str) -> dict | None:
        try:
            return self._get(f"/project/{key}")
        except Exception:
            return None

    # ── Board & Sprint (Agile API) ────────────────────────────────────────────

    def _agile(self, method: str, path: str, **kwargs):
        url = f"{JIRA_BASE_URL}/rest/agile/1.0{path}"
        resp = getattr(requests, method)(url, auth=self.auth,
                                         headers=self.headers, verify=False, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def get_board(self, project_key: str) -> dict | None:
        data = self._agile("get", "/board", params={"projectKeyOrId": project_key})
        values = data.get("values", [])
        return values[0] if values else None

    def create_sprint(self, board_id: int, name: str,
                      start_date: str, end_date: str, goal: str = "") -> dict:
        payload = {
            "name":          name,
            "originBoardId": board_id,
            "startDate":     start_date,
            "endDate":       end_date,
            "goal":          goal,
        }
        return self._agile("post", "/sprint", json=payload)
