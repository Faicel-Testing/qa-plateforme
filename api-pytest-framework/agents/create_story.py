"""Create spec Story in HBAPI Jira project."""
import sys, os, requests, json
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
from jira_fetcher_agent import JIRA_BASE_URL, JIRA_EMAIL, JIRA_TOKEN
from requests.auth import HTTPBasicAuth

auth    = HTTPBasicAuth(JIRA_EMAIL, JIRA_TOKEN)
headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}


def _text(t):
    return {"type": "text", "text": str(t)}


def _heading(level, t):
    return {"type": "heading", "attrs": {"level": level}, "content": [_text(t)]}


def _paragraph(*parts):
    content = []
    for p in parts:
        content.append(_text(p) if isinstance(p, str) else p)
    return {"type": "paragraph", "content": content}


def _bold(t):
    return {"type": "text", "text": t, "marks": [{"type": "strong"}]}


def _table_cell(text, header=False):
    cell_type = "tableHeader" if header else "tableCell"
    return {
        "type": cell_type,
        "attrs": {},
        "content": [{"type": "paragraph", "content": [_text(text)]}]
    }


def _table_row(*cells, header=False):
    return {"type": "tableRow", "content": [_table_cell(c, header) for c in cells]}


def _table(*rows):
    return {
        "type": "table",
        "attrs": {"isNumberColumnEnabled": False, "layout": "default"},
        "content": list(rows)
    }


def _rule():
    return {"type": "rule"}


def build_adf():
    content = [
        _heading(1, "SPEC -- Hotel Booking API Automation"),
        _paragraph(_bold("Document de specification complet -- Restful Booker API")),
        _rule(),

        _heading(2, "Informations generales"),
        _table(
            _table_row("Attribut", "Valeur", header=True),
            _table_row("Version",   "1.0"),
            _table_row("Date",      "08 Juin 2026"),
            _table_row("Auteur",    "Faicel GHANEM -- Senior QA Automation Engineer"),
            _table_row("Framework", "Python Requests + Pytest + BDD + Agents IA"),
            _table_row("Base URL",  "https://restful-booker.herokuapp.com"),
            _table_row("Statut",    "APPROUVE"),
        ),
        _rule(),

        _heading(2, "Endpoints couverts (8 au total)"),
        _table(
            _table_row("Methode", "Endpoint", "Description", "Auth", header=True),
            _table_row("POST",   "/auth",           "Generer un token Bearer",  "Non"),
            _table_row("GET",    "/booking",         "Lister les reservations",  "Non"),
            _table_row("GET",    "/booking/{id}",    "Recuperer une reservation","Non"),
            _table_row("POST",   "/booking",         "Creer une reservation",    "Non"),
            _table_row("PUT",    "/booking/{id}",    "Mise a jour complete",     "Oui -- Cookie token"),
            _table_row("PATCH",  "/booking/{id}",    "Mise a jour partielle",    "Oui -- Cookie token"),
            _table_row("DELETE", "/booking/{id}",    "Supprimer une reservation","Oui -- Cookie token"),
            _table_row("GET",    "/ping",            "Health Check",             "Non"),
        ),
        _rule(),

        _heading(2, "Recapitulatif des cas de test (52 total)"),
        _table(
            _table_row("US ID",  "Endpoint",            "Passants", "Non-passants", "Total", header=True),
            _table_row("US-001", "POST /auth",           "1",  "4",  "5"),
            _table_row("US-002", "GET /booking",         "5",  "2",  "7"),
            _table_row("US-003", "GET /booking/{id}",    "3",  "4",  "7"),
            _table_row("US-004", "POST /booking",        "3",  "9",  "12"),
            _table_row("US-005", "PUT /booking/{id}",    "2",  "4",  "6"),
            _table_row("US-006", "PATCH /booking/{id}",  "3",  "4",  "7"),
            _table_row("US-007", "DELETE /booking/{id}", "2",  "4",  "6"),
            _table_row("US-008", "GET /ping",            "2",  "0",  "2"),
            _table_row("TOTAL",  "8 endpoints",          "21", "31", "52"),
        ),
        _rule(),

        _heading(2, "US-001 -- POST /auth -- Authentification"),
        _paragraph(_bold("Objectif :"), " Generer un token d'authentification valide."),
        _table(
            _table_row("ID", "Scenario", "Resultat attendu", header=True),
            _table_row("TC-001", "Token valide admin/password123",   "200 + token non vide"),
            _table_row("TC-002", "Identifiants incorrects",          "200 + bad credentials"),
            _table_row("TC-003", "Champs manquants",                 "200 + bad credentials"),
            _table_row("TC-004", "SQL injection username",           "200 + bad credentials"),
            _table_row("TC-005", "XSS payload password",             "200 + bad credentials"),
        ),
        _rule(),

        _heading(2, "US-002 -- GET /booking -- Liste des reservations"),
        _paragraph(_bold("Objectif :"), " Recuperer la liste avec filtres optionnels."),
        _table(
            _table_row("ID", "Scenario", "Resultat attendu", header=True),
            _table_row("TC-006", "Liste complete sans filtre",    "200 + tableau non vide"),
            _table_row("TC-007", "Filtre firstname=Jim",          "200 + resultats Jim"),
            _table_row("TC-008", "Filtre lastname=Brown",         "200 + resultats Brown"),
            _table_row("TC-009", "Filtre checkin date valide",    "200 + tableau"),
            _table_row("TC-010", "Filtre checkout date valide",   "200 + tableau"),
            _table_row("TC-011", "Filtre firstname inexistant",   "200 + tableau vide"),
            _table_row("TC-012", "Filtre SQL injection",          "200 + tableau vide ou safe"),
        ),
        _rule(),

        _heading(2, "US-003 -- GET /booking/{id} -- Detail reservation"),
        _table(
            _table_row("ID", "Scenario", "Resultat attendu", header=True),
            _table_row("TC-013", "ID existant valide",         "200 + objet complet"),
            _table_row("TC-014", "Schema JSON valide",         "200 + schema conforme"),
            _table_row("TC-015", "Dates format ISO 8601",      "200 + dates valides"),
            _table_row("TC-016", "ID inexistant (9999999)",    "404 Not Found"),
            _table_row("TC-017", "ID string non numerique",    "404 Not Found"),
            _table_row("TC-018", "ID negatif",                 "404 Not Found"),
            _table_row("TC-019", "ID zero",                    "404 Not Found"),
        ),
        _rule(),

        _heading(2, "US-004 -- POST /booking -- Creation reservation"),
        _table(
            _table_row("ID", "Scenario", "Resultat attendu", header=True),
            _table_row("TC-020", "Creation avec tous les champs",    "200 + bookingid"),
            _table_row("TC-021", "Sans additionalneeds (optionnel)", "200 + bookingid"),
            _table_row("TC-022", "Dates checkin = checkout",         "200 -- limite metier"),
            _table_row("TC-023", "Champ firstname manquant",         "400 ou 500"),
            _table_row("TC-024", "Champ lastname manquant",          "400 ou 500"),
            _table_row("TC-025", "Champ totalprice manquant",        "400 ou 500"),
            _table_row("TC-026", "Champ depositpaid manquant",       "400 ou 500"),
            _table_row("TC-027", "Champ bookingdates manquant",      "400 ou 500"),
            _table_row("TC-028", "totalprice negatif",               "400 ou valeur stockee"),
            _table_row("TC-029", "checkin apres checkout",           "400 -- inversion dates"),
            _table_row("TC-030", "Body vide {}",                     "400 ou 500"),
            _table_row("TC-031", "XSS payload dans firstname",       "200 -- encode ou refuse"),
        ),
        _rule(),

        _heading(2, "US-005 -- PUT /booking/{id} -- Mise a jour complete"),
        _table(
            _table_row("ID", "Scenario", "Resultat attendu", header=True),
            _table_row("TC-032", "MAJ complete avec token valide", "200 + objet mis a jour"),
            _table_row("TC-033", "Verification persistence",       "200 + GET confirme MAJ"),
            _table_row("TC-034", "Sans token d'auth",              "403 Forbidden"),
            _table_row("TC-035", "Token invalide",                 "403 Forbidden"),
            _table_row("TC-036", "ID inexistant",                  "405 Not Allowed"),
            _table_row("TC-037", "Champ requis manquant",          "400 Bad Request"),
        ),
        _rule(),

        _heading(2, "US-006 -- PATCH /booking/{id} -- Mise a jour partielle"),
        _table(
            _table_row("ID", "Scenario", "Resultat attendu", header=True),
            _table_row("TC-038", "PATCH firstname uniquement",       "200 + firstname mis a jour"),
            _table_row("TC-039", "PATCH totalprice uniquement",      "200 + prix mis a jour"),
            _table_row("TC-040", "PATCH lastname + totalprice",      "200 + deux champs mis a jour"),
            _table_row("TC-041", "PATCH sans token",                 "403 Forbidden"),
            _table_row("TC-042", "PATCH token invalide",             "403 Forbidden"),
            _table_row("TC-043", "PATCH ID inexistant",              "405 Not Allowed"),
            _table_row("TC-044", "PATCH body vide {}",               "200 -- aucun changement"),
        ),
        _rule(),

        _heading(2, "US-007 -- DELETE /booking/{id} -- Suppression"),
        _table(
            _table_row("ID", "Scenario", "Resultat attendu", header=True),
            _table_row("TC-045", "DELETE avec token valide",      "201 Created (Restful Booker)"),
            _table_row("TC-046", "Verification suppression GET",  "404 apres suppression"),
            _table_row("TC-047", "DELETE sans token",             "403 Forbidden"),
            _table_row("TC-048", "DELETE token invalide",         "403 Forbidden"),
            _table_row("TC-049", "DELETE ID inexistant",          "405 Not Allowed"),
            _table_row("TC-050", "DELETE deux fois meme ID",      "405 deuxieme fois"),
        ),
        _rule(),

        _heading(2, "US-008 -- GET /ping -- Health Check"),
        _table(
            _table_row("ID", "Scenario", "Resultat attendu", header=True),
            _table_row("TC-051", "Health check standard",       "201 Created"),
            _table_row("TC-052", "Response time < 3 secondes",  "201 + latence OK"),
        ),
        _rule(),

        _heading(2, "Modele de donnees -- Booking"),
        _table(
            _table_row("Champ",          "Type",    "Requis", "Exemple",     header=True),
            _table_row("firstname",      "string",  "Oui",    "Jim"),
            _table_row("lastname",       "string",  "Oui",    "Brown"),
            _table_row("totalprice",     "integer", "Oui",    "111"),
            _table_row("depositpaid",    "boolean", "Oui",    "true"),
            _table_row("checkin",        "date",    "Oui",    "2018-01-01"),
            _table_row("checkout",       "date",    "Oui",    "2019-01-01"),
            _table_row("additionalneeds","string",  "Non",    "Breakfast"),
        ),
        _rule(),

        _heading(2, "Codes HTTP attendus"),
        _table(
            _table_row("Code", "Signification",      "Contexte",                       header=True),
            _table_row("200",  "OK",                 "GET, POST booking, PUT, PATCH"),
            _table_row("201",  "Created",            "DELETE (anomalie), GET /ping"),
            _table_row("400",  "Bad Request",        "Donnees invalides ou manquantes"),
            _table_row("403",  "Forbidden",          "Token absent ou invalide"),
            _table_row("404",  "Not Found",          "ID inexistant"),
            _table_row("405",  "Method Not Allowed", "PUT/PATCH/DELETE sur ID inexistant"),
            _table_row("500",  "Server Error",       "Donnees malformees"),
        ),
        _rule(),

        _heading(2, "Credentials de test"),
        _table(
            _table_row("Parametre",     "Valeur",              header=True),
            _table_row("username",      "admin"),
            _table_row("password",      "password123"),
            _table_row("Basic Auth",    "admin:password123"),
            _table_row("Reset donnees", "Toutes les 10 minutes automatiquement"),
        ),
        _rule(),

        _paragraph(_bold("Fichier source :"), " specs/restful-booker-api-spec.md"),
        _paragraph(_bold("Framework :"),      " api-pytest-framework/ -- Python + Pytest + BDD + POM + Agents IA"),
        _paragraph("Genere le 08/06/2026 par jira-agent.py"),
    ]
    return {"type": "doc", "version": 1, "content": content}


if __name__ == "__main__":
    adf = build_adf()
    payload = {
        "fields": {
            "project":     {"key": "HBAPI"},
            "issuetype":   {"id": "10006"},
            "summary":     "SPEC -- Hotel Booking API (52 cas de test | 8 endpoints | US-001 a US-008)",
            "description": adf,
            "labels":      ["specification", "documentation", "restful-booker"],
        }
    }

    r = requests.post(
        f"{JIRA_BASE_URL}/rest/api/3/issue",
        auth=auth,
        headers=headers,
        json=payload,
        verify=False
    )
    print("Status:", r.status_code)
    data = r.json()
    if r.status_code in (200, 201):
        key = data.get("key", "")
        print(f"[OK] Story creee : {key}")
        print(f"[URL] {JIRA_BASE_URL}/browse/{key}")
    else:
        print(json.dumps(data, indent=2)[:1000])
