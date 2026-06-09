# ============================================
# Jira Agent -- Setup projet Hotel Booking API
# ============================================
# Étapes :
#   1. Crée le projet Jira "Hotel Booking -- API Automation" (clé HBA)
#   2. Récupère le board Scrum auto-créé
#   3. Crée un sprint de 3 semaines
#   4. Envoie le document de spécification complet dans Jira
#
# Usage:
#   python agents/jira-agent.py
#   python agents/jira-agent.py --dry-run
# ============================================

import sys
import os
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from jira_fetcher_agent import JiraClient

DRY_RUN      = "--dry-run" in sys.argv
PROJECT_NAME = "Hotel Booking -- API Automation"
PROJECT_KEY  = "HBA"
SPEC_FILE    = os.path.join(os.path.dirname(__file__), "../specs/restful-booker-api-spec.md")


# ── ADF helpers ───────────────────────────────────────────────────────────────

def _text(t: str) -> dict:
    return {"type": "text", "text": str(t)}

def _heading(level: int, t: str) -> dict:
    return {"type": "heading", "attrs": {"level": level},
            "content": [_text(t)]}

def _paragraph(*parts) -> dict:
    content = []
    for p in parts:
        if isinstance(p, str):
            content.append(_text(p))
        else:
            content.append(p)
    return {"type": "paragraph", "content": content}

def _bold(t: str) -> dict:
    return {"type": "text", "text": t, "marks": [{"type": "strong"}]}

def _table_cell(text: str, header: bool = False) -> dict:
    cell_type = "tableHeader" if header else "tableCell"
    return {"type": cell_type, "attrs": {},
            "content": [{"type": "paragraph", "content": [_text(text)]}]}

def _table_row(*cells: str, header: bool = False) -> dict:
    return {"type": "tableRow",
            "content": [_table_cell(c, header) for c in cells]}

def _table(*rows: dict) -> dict:
    return {"type": "table",
            "attrs": {"isNumberColumnEnabled": False, "layout": "default"},
            "content": list(rows)}

def _rule() -> dict:
    return {"type": "rule"}


def build_spec_adf() -> dict:
    """Construit le document ADF complet depuis le fichier de spec."""
    spec_text = ""
    if os.path.exists(SPEC_FILE):
        with open(SPEC_FILE, encoding="utf-8") as f:
            spec_text = f.read()

    content = [
        _heading(1, "Hotel Booking -- API Automation"),
        _heading(2, "Informations générales"),
        _table(
            _table_row("Attribut", "Valeur", header=True),
            _table_row("Version",   "1.0"),
            _table_row("Date",      "08 Juin 2026"),
            _table_row("Auteur",    "Faicel GHANEM -- Senior QA Automation Engineer"),
            _table_row("Framework", "Python Requests + Pytest + Agents IA"),
            _table_row("Base URL",  "https://restful-booker.herokuapp.com"),
            _table_row("Statut",    "APPROUVÉ"),
        ),
        _rule(),
        _heading(2, "Endpoints couverts"),
        _table(
            _table_row("Méthode", "Endpoint", "Description", "Auth", header=True),
            _table_row("POST",   "/auth",           "Générer un token",              "Non"),
            _table_row("GET",    "/booking",         "Lister les réservations",       "Non"),
            _table_row("GET",    "/booking/{id}",    "Récupérer une réservation",     "Non"),
            _table_row("POST",   "/booking",         "Créer une réservation",         "Non"),
            _table_row("PUT",    "/booking/{id}",    "Mettre à jour (complète)",      "Oui"),
            _table_row("PATCH",  "/booking/{id}",    "Mettre à jour (partielle)",     "Oui"),
            _table_row("DELETE", "/booking/{id}",    "Supprimer une réservation",     "Oui"),
            _table_row("GET",    "/ping",            "Health Check",                  "Non"),
        ),
        _rule(),
        _heading(2, "Récapitulatif des cas de test"),
        _table(
            _table_row("US ID",   "Endpoint",            "Passants", "Non-passants", "Total", header=True),
            _table_row("US-001",  "POST /auth",           "1",  "4",  "5"),
            _table_row("US-002",  "GET /booking",         "5",  "2",  "7"),
            _table_row("US-003",  "GET /booking/{id}",    "3",  "4",  "7"),
            _table_row("US-004",  "POST /booking",        "3",  "9",  "12"),
            _table_row("US-005",  "PUT /booking/{id}",    "2",  "4",  "6"),
            _table_row("US-006",  "PATCH /booking/{id}",  "3",  "4",  "7"),
            _table_row("US-007",  "DELETE /booking/{id}", "2",  "4",  "6"),
            _table_row("US-008",  "GET /ping",            "2",  "0",  "2"),
            _table_row("TOTAL",   "8 endpoints",          "21", "31", "52"),
        ),
        _rule(),
        _heading(2, "Modèle de données -- Booking"),
        _paragraph("Champs requis : firstname, lastname, totalprice, depositpaid, bookingdates (checkin + checkout)"),
        _paragraph("Champ optionnel : additionalneeds"),
        _rule(),
        _heading(2, "Credentials de test"),
        _table(
            _table_row("Paramètre", "Valeur", header=True),
            _table_row("username",   "admin"),
            _table_row("password",   "password123"),
            _table_row("Basic Auth", "admin:password123"),
            _table_row("Reset données", "Toutes les 10 minutes automatiquement"),
        ),
        _rule(),
        _paragraph("Document complet disponible dans : specs/restful-booker-api-spec.md"),
        _paragraph(f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')} par Jira Agent"),
    ]

    return {"type": "doc", "version": 1, "content": content}


# ── Étapes ────────────────────────────────────────────────────────────────────

def step_create_project(jira: JiraClient) -> str:
    """Crée le projet ou retourne la clé s'il existe déjà."""
    print(f"\n{'[DRY-RUN] ' if DRY_RUN else ''}[>] Étape 1 -- Création du projet : {PROJECT_NAME}")

    existing = jira.get_project(PROJECT_KEY)
    if existing:
        print(f"  [i]  Projet {PROJECT_KEY} existe déjà -> on continue")
        return PROJECT_KEY

    if DRY_RUN:
        print(f"  [DRY-RUN] Aurait créé le projet {PROJECT_KEY}")
        return PROJECT_KEY

    result = jira.create_project(
        name=PROJECT_NAME,
        key=PROJECT_KEY,
        description="Framework de test API automatisé -- Restful Booker Hotel Booking API. "
                    "Python Requests + Pytest + BDD + Agents IA."
    )
    print(f"  [OK] Projet créé : {result.get('key')} -- {result.get('name')}")
    print(f"  [url] {result.get('self', '')}")
    return PROJECT_KEY


def step_get_board(jira: JiraClient, project_key: str) -> int | None:
    """Récupère le board Scrum auto-créé avec le projet."""
    print(f"\n{'[DRY-RUN] ' if DRY_RUN else ''}[=] Étape 2 -- Récupération du board Scrum")

    if DRY_RUN:
        print(f"  [DRY-RUN] Aurait récupéré le board du projet {project_key}")
        return None

    # Le board peut mettre quelques secondes à apparaître après création
    for attempt in range(5):
        board = jira.get_board(project_key)
        if board:
            print(f"  [OK] Board trouvé : [{board['id']}] {board['name']}")
            return board["id"]
        print(f"  [wait] Board non disponible, nouvelle tentative ({attempt + 1}/5)...")
        time.sleep(3)

    print("  [WARN]  Board introuvable après 5 tentatives")
    return None


def step_create_sprint(jira: JiraClient, board_id: int | None):
    """Crée un sprint de 3 semaines."""
    print(f"\n{'[DRY-RUN] ' if DRY_RUN else ''}[>>] Étape 3 -- Création du sprint (3 semaines)")

    start  = datetime.now() + timedelta(days=1)
    end    = start + timedelta(weeks=3)
    s_fmt  = start.strftime("%Y-%m-%dT%H:%M:%S.000+0000")
    e_fmt  = end.strftime("%Y-%m-%dT%H:%M:%S.000+0000")
    name   = f"Sprint 1 -- {start.strftime('%d %b')} -> {end.strftime('%d %b %Y')}"

    print(f"  [date] {start.strftime('%d/%m/%Y')} -> {end.strftime('%d/%m/%Y')}")

    if DRY_RUN or board_id is None:
        print(f"  [DRY-RUN] Aurait créé : {name}")
        return

    result = jira.create_sprint(
        board_id=board_id,
        name=name,
        start_date=s_fmt,
        end_date=e_fmt,
        goal="Implémenter et valider les 52 cas de test API -- US-001 à US-008"
    )
    print(f"  [OK] Sprint créé : [{result['id']}] {result['name']}")
    print(f"  [goal] Goal : {result.get('goal', '')}")


def step_send_spec(jira: JiraClient, project_key: str):
    """Envoie le document de spécification complet dans Jira."""
    print(f"\n{'[DRY-RUN] ' if DRY_RUN else ''}[doc] Étape 4 -- Envoi de la spécification dans Jira")

    # Sauvegarde temporaire du project pour cette création
    original_project = jira.project
    jira.project = project_key

    if DRY_RUN:
        print("  [DRY-RUN] Aurait créé l'Epic de spécification")
        jira.project = original_project
        return

    adf = build_spec_adf()
    payload = {
        "fields": {
            "project":     {"key": project_key},
            "issuetype":   {"name": "Epic"},
            "summary":     "[=] Specification -- Hotel Booking API (52 cas de test)",
            "description": adf,
            "labels":      ["specification", "documentation"],
        }
    }

    try:
        result = jira._post("/issue", payload)
        key    = result.get("key", "")
        url    = f"{os.getenv('JIRA_BASE_URL')}/browse/{key}"
        print(f"  [OK] Spec créée : {key}")
        print(f"  [url] {url}")
    except Exception as e:
        print(f"  [ERR] Erreur création spec : {e}")

    jira.project = original_project


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    print(f"\n{'=' * 55}")
    print(f"  JIRA AGENT -- Hotel Booking API Automation")
    print(f"{'=' * 55}")
    if DRY_RUN:
        print("  MODE DRY-RUN -- aucune action réelle")

    jira = JiraClient()

    # Étape 1 -- Projet
    project_key = step_create_project(jira)

    # Étape 2 -- Board
    board_id = step_get_board(jira, project_key)

    # Étape 3 -- Sprint
    step_create_sprint(jira, board_id)

    # Étape 4 -- Spec
    step_send_spec(jira, project_key)

    print(f"\n{'=' * 55}")
    print(f"  [OK] Setup Jira terminé")
    if not DRY_RUN:
        base = os.getenv("JIRA_BASE_URL", "")
        print(f"  [url] {base}/jira/software/projects/{project_key}/boards")
    print(f"{'=' * 55}\n")


if __name__ == "__main__":
    run()
