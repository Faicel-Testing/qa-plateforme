# ============================================
# Jira Fetcher — Client Jira REST API partagé (Mobile Framework)
# ============================================
# Module réutilisable importé par jira-ticket-agent.
# Identique au module api-pytest-framework.
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
        self.base    = f"{JIRA_BASE_URL}/rest/api/3"
        self.auth    = HTTPBasicAuth(JIRA_EMAIL, JIRA_TOKEN)
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

    def get_stories(self, max_results: int = 50) -> list:
        jql  = f"project = {self.project} AND issuetype = Bug ORDER BY created DESC"
        data = self._get(
            f"/search/jql?jql={requests.utils.quote(jql)}"
            f"&maxResults={max_results}&fields=summary,status,description"
        )
        return data.get("issues", [])

    def get_issue(self, key: str) -> dict:
        return self._get(f"/issue/{key}")

    def create_story(self, summary: str, description: str = "", priority: str = "Medium") -> dict:
        payload = {
            "fields": {
                "project":     {"key": self.project},
                "issuetype":   {"name": "Bug"},
                "summary":     summary,
                "priority":    {"name": priority},
                "labels":      ["mobile", "appium", "automated"],
                "description": {
                    "type": "doc", "version": 1,
                    "content": [{"type": "paragraph",
                                 "content": [{"type": "text", "text": description}]}]
                }
            }
        }
        return self._post("/issue", payload)

    def add_comment(self, issue_key: str, text: str):
        payload = {
            "body": {
                "type": "doc", "version": 1,
                "content": [{"type": "paragraph",
                             "content": [{"type": "text", "text": text}]}]
            }
        }
        self._post(f"/issue/{issue_key}/comment", payload)
