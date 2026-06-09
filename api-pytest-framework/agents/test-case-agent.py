# ============================================================
# Test Case Agent -- Création / gestion des cas de test Jira
# ============================================================
# Usage:
#   python agents/test-case-agent.py                       # Crée les TCs (sous-tâches)
#   python agents/test-case-agent.py --dry-run             # Simulation
#   python agents/test-case-agent.py --us=US-001           # Seulement US-001
#   python agents/test-case-agent.py --link-only           # Tache + lien Relates
#   python agents/test-case-agent.py delete --type=securite # Supprime par type
#   python agents/test-case-agent.py gherkin               # Génère features/ depuis Jira
#   python agents/test-case-agent.py gherkin --us=US-001   # Un seul US
# ============================================================

import sys
import os
import re
import time

sys.path.insert(0, os.path.dirname(__file__))

from jira_fetcher_agent import JiraClient, JIRA_BASE_URL

PROJECT    = "HBAPI"
DRY_RUN    = "--dry-run"    in sys.argv
LINK_ONLY  = "--link-only"  in sys.argv
US_FILTER  = next((a.split("=")[1] for a in sys.argv if a.startswith("--us=")), None)

# Mapping US -> clé Jira (les Stories créées par user-stories-agent.py)
US_JIRA = {
    "US-001": "HBAPI-3",
    "US-002": "HBAPI-4",
    "US-003": "HBAPI-5",
    "US-004": "HBAPI-6",
    "US-005": "HBAPI-7",
    "US-006": "HBAPI-8",
    "US-007": "HBAPI-9",
    "US-008": "HBAPI-10",
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


# ── Définition des 52 cas de test ─────────────────────────────────────────────
# Format : (tc_id, us_id, type, summary, scenario, expected, priority)
#   type : Positif | Negatif | Securite | Performance | Limite

TEST_CASES = [
    # ── US-001 -- POST /auth (5 TCs) ─────────────────────────────────────────
    ("TC-001", "US-001", "Positif",
     "TC-001 -- Token valide (POST /auth)",
     "Envoyer POST /auth avec username=admin et password=password123",
     "HTTP 200 + champ token present et longueur > 10 caracteres",
     "High"),
    ("TC-002", "US-001", "Negatif",
     "TC-002 -- Credentials incorrects (POST /auth)",
     "Envoyer POST /auth avec username=wrong et password=wrong",
     "HTTP 200 + body contient {\"reason\": \"Bad credentials\"}",
     "High"),
    ("TC-003", "US-001", "Negatif",
     "TC-003 -- Champs username et password manquants (POST /auth)",
     "Envoyer POST /auth avec body vide {}",
     "HTTP 200 + body contient {\"reason\": \"Bad credentials\"}",
     "Medium"),
    ("TC-004", "US-001", "Securite",
     "TC-004 -- SQL injection dans username (POST /auth)",
     "Envoyer POST /auth avec username=\"' OR '1'='1\" et password=test",
     "HTTP 200 + bad credentials -- le systeme n'est pas compromis",
     "High"),
    ("TC-005", "US-001", "Securite",
     "TC-005 -- XSS payload dans password (POST /auth)",
     "Envoyer POST /auth avec password=\"<script>alert('xss')</script>\"",
     "HTTP 200 + bad credentials -- payload non execute",
     "High"),

    # ── US-002 -- GET /booking (7 TCs) ───────────────────────────────────────
    ("TC-006", "US-002", "Positif",
     "TC-006 -- Liste complete sans filtre (GET /booking)",
     "Envoyer GET /booking sans parametre",
     "HTTP 200 + tableau JSON avec au moins 1 objet {bookingid: N}",
     "High"),
    ("TC-007", "US-002", "Positif",
     "TC-007 -- Filtre par firstname (GET /booking?firstname=Jim)",
     "Envoyer GET /booking?firstname=Jim",
     "HTTP 200 + tableau filtre contenant les reservations de Jim",
     "Medium"),
    ("TC-008", "US-002", "Positif",
     "TC-008 -- Filtre par lastname (GET /booking?lastname=Brown)",
     "Envoyer GET /booking?lastname=Brown",
     "HTTP 200 + tableau filtre contenant les reservations de Brown",
     "Medium"),
    ("TC-009", "US-002", "Positif",
     "TC-009 -- Filtre par checkin (GET /booking?checkin=2018-01-01)",
     "Envoyer GET /booking?checkin=2018-01-01",
     "HTTP 200 + tableau de reservations avec checkin >= 2018-01-01",
     "Medium"),
    ("TC-010", "US-002", "Positif",
     "TC-010 -- Filtre par checkout (GET /booking?checkout=2019-01-01)",
     "Envoyer GET /booking?checkout=2019-01-01",
     "HTTP 200 + tableau de reservations avec checkout <= 2019-01-01",
     "Medium"),
    ("TC-011", "US-002", "Negatif",
     "TC-011 -- Filtre firstname inexistant (GET /booking?firstname=XYZ)",
     "Envoyer GET /booking?firstname=XYZ_INEXISTANT",
     "HTTP 200 + tableau vide []",
     "Low"),
    ("TC-012", "US-002", "Securite",
     "TC-012 -- SQL injection dans filtre firstname (GET /booking)",
     "Envoyer GET /booking?firstname=' OR '1'='1",
     "HTTP 200 + tableau vide ou reponse safe -- aucune donnee non autorisee",
     "High"),

    # ── US-003 -- GET /booking/{id} (7 TCs) ──────────────────────────────────
    ("TC-013", "US-003", "Positif",
     "TC-013 -- Reservation existante valide (GET /booking/{id})",
     "Creer une reservation, recuperer son ID, puis envoyer GET /booking/{id}",
     "HTTP 200 + objet complet avec firstname, lastname, totalprice, depositpaid, bookingdates",
     "High"),
    ("TC-014", "US-003", "Positif",
     "TC-014 -- Validation schema JSON (GET /booking/{id})",
     "Envoyer GET /booking/{id} et valider la reponse contre le schema JSON defini",
     "HTTP 200 + tous les champs conformes au schema (types et champs requis)",
     "High"),
    ("TC-015", "US-003", "Positif",
     "TC-015 -- Dates au format ISO 8601 (GET /booking/{id})",
     "Envoyer GET /booking/{id} et verifier le format des dates checkin et checkout",
     "HTTP 200 + checkin et checkout au format YYYY-MM-DD (ISO 8601)",
     "Medium"),
    ("TC-016", "US-003", "Negatif",
     "TC-016 -- ID inexistant (GET /booking/9999999)",
     "Envoyer GET /booking/9999999",
     "HTTP 404 Not Found",
     "High"),
    ("TC-017", "US-003", "Negatif",
     "TC-017 -- ID non numerique (GET /booking/abc)",
     "Envoyer GET /booking/abc",
     "HTTP 404 Not Found",
     "Medium"),
    ("TC-018", "US-003", "Negatif",
     "TC-018 -- ID negatif (GET /booking/-1)",
     "Envoyer GET /booking/-1",
     "HTTP 404 Not Found",
     "Medium"),
    ("TC-019", "US-003", "Negatif",
     "TC-019 -- ID zero (GET /booking/0)",
     "Envoyer GET /booking/0",
     "HTTP 404 Not Found",
     "Low"),

    # ── US-004 -- POST /booking (12 TCs) ─────────────────────────────────────
    ("TC-020", "US-004", "Positif",
     "TC-020 -- Creation avec tous les champs valides (POST /booking)",
     "Envoyer POST /booking avec firstname, lastname, totalprice, depositpaid, bookingdates et additionalneeds",
     "HTTP 200/201 + champ bookingid entier > 0 + objet booking cree",
     "High"),
    ("TC-021", "US-004", "Positif",
     "TC-021 -- Creation sans champ optionnel additionalneeds (POST /booking)",
     "Envoyer POST /booking sans le champ additionalneeds",
     "HTTP 200/201 + bookingid present -- le champ optionnel n'est pas requis",
     "High"),
    ("TC-022", "US-004", "Limite",
     "TC-022 -- Dates checkin egale checkout (POST /booking)",
     "Envoyer POST /booking avec checkin = checkout = 2026-07-01",
     "HTTP 200/201 -- cas limite accepte par l'API (sejour d'une journee)",
     "Medium"),
    ("TC-023", "US-004", "Negatif",
     "TC-023 -- Champ firstname manquant (POST /booking)",
     "Envoyer POST /booking sans le champ firstname",
     "HTTP 400 ou 500 -- champ requis absent",
     "High"),
    ("TC-024", "US-004", "Negatif",
     "TC-024 -- Champ lastname manquant (POST /booking)",
     "Envoyer POST /booking sans le champ lastname",
     "HTTP 400 ou 500 -- champ requis absent",
     "High"),
    ("TC-025", "US-004", "Negatif",
     "TC-025 -- Champ totalprice manquant (POST /booking)",
     "Envoyer POST /booking sans le champ totalprice",
     "HTTP 400 ou 500 -- champ requis absent",
     "High"),
    ("TC-026", "US-004", "Negatif",
     "TC-026 -- Champ depositpaid manquant (POST /booking)",
     "Envoyer POST /booking sans le champ depositpaid",
     "HTTP 400 ou 500 -- champ requis absent",
     "Medium"),
    ("TC-027", "US-004", "Negatif",
     "TC-027 -- Champ bookingdates manquant (POST /booking)",
     "Envoyer POST /booking sans le champ bookingdates",
     "HTTP 400 ou 500 -- champ requis absent",
     "High"),
    ("TC-028", "US-004", "Negatif",
     "TC-028 -- totalprice negatif (POST /booking)",
     "Envoyer POST /booking avec totalprice = -100",
     "HTTP 400 ou 500 -- valeur numerique negative invalide",
     "Medium"),
    ("TC-029", "US-004", "Negatif",
     "TC-029 -- checkin posterieur a checkout (POST /booking)",
     "Envoyer POST /booking avec checkin=2026-12-31 et checkout=2026-01-01",
     "HTTP 400 -- inversion des dates incoherente",
     "High"),
    ("TC-030", "US-004", "Negatif",
     "TC-030 -- Body vide (POST /booking)",
     "Envoyer POST /booking avec body vide {}",
     "HTTP 400 ou 500 -- aucun champ requis fourni",
     "Medium"),
    ("TC-031", "US-004", "Securite",
     "TC-031 -- XSS payload dans firstname (POST /booking)",
     "Envoyer POST /booking avec firstname=\"<script>alert('xss')</script>\"",
     "HTTP 400 ou 200 avec valeur sanitisee -- payload non stocke ni execute",
     "High"),

    # ── US-005 -- PUT /booking/{id} (6 TCs) ──────────────────────────────────
    ("TC-032", "US-005", "Positif",
     "TC-032 -- Mise a jour complete avec token valide (PUT /booking/{id})",
     "Creer une reservation, puis envoyer PUT /booking/{id} avec tous les champs et Cookie token valide",
     "HTTP 200 + objet booking completement mis a jour dans la reponse",
     "High"),
    ("TC-033", "US-005", "Positif",
     "TC-033 -- Persistence apres PUT (GET /booking/{id})",
     "Effectuer PUT /booking/{id}, puis GET /booking/{id} pour verifier les modifications",
     "HTTP 200 sur GET + les donnees correspondent a celles du PUT",
     "High"),
    ("TC-034", "US-005", "Negatif",
     "TC-034 -- PUT sans authentification (PUT /booking/{id})",
     "Envoyer PUT /booking/{id} sans header Cookie ni Authorization",
     "HTTP 403 Forbidden",
     "High"),
    ("TC-035", "US-005", "Negatif",
     "TC-035 -- PUT avec token invalide (PUT /booking/{id})",
     "Envoyer PUT /booking/{id} avec Cookie: token=INVALID_TOKEN",
     "HTTP 403 Forbidden",
     "High"),
    ("TC-036", "US-005", "Negatif",
     "TC-036 -- PUT sur ID inexistant (PUT /booking/9999999)",
     "Envoyer PUT /booking/9999999 avec token valide",
     "HTTP 404 ou 405 -- ID inexistant",
     "Medium"),
    ("TC-037", "US-005", "Negatif",
     "TC-037 -- PUT sans champ requis firstname (PUT /booking/{id})",
     "Envoyer PUT /booking/{id} avec token valide mais sans champ firstname",
     "HTTP 400 Bad Request -- champ requis manquant",
     "Medium"),

    # ── US-006 -- PATCH /booking/{id} (7 TCs) ────────────────────────────────
    ("TC-038", "US-006", "Positif",
     "TC-038 -- PATCH firstname uniquement (PATCH /booking/{id})",
     "Envoyer PATCH /booking/{id} avec body {\"firstname\": \"UpdatedName\"} et token valide",
     "HTTP 200 + firstname = UpdatedName + autres champs inchanges",
     "High"),
    ("TC-039", "US-006", "Positif",
     "TC-039 -- PATCH totalprice uniquement (PATCH /booking/{id})",
     "Envoyer PATCH /booking/{id} avec body {\"totalprice\": 999} et token valide",
     "HTTP 200 + totalprice = 999 dans la reponse",
     "High"),
    ("TC-040", "US-006", "Positif",
     "TC-040 -- PATCH lastname et totalprice (PATCH /booking/{id})",
     "Envoyer PATCH /booking/{id} avec {\"lastname\": \"Updated\", \"totalprice\": 500} et token valide",
     "HTTP 200 + lastname et totalprice mis a jour + autres champs inchanges",
     "Medium"),
    ("TC-041", "US-006", "Negatif",
     "TC-041 -- PATCH sans token (PATCH /booking/{id})",
     "Envoyer PATCH /booking/{id} sans header d'authentification",
     "HTTP 403 Forbidden",
     "High"),
    ("TC-042", "US-006", "Negatif",
     "TC-042 -- PATCH avec token invalide (PATCH /booking/{id})",
     "Envoyer PATCH /booking/{id} avec Cookie: token=FAKE_TOKEN",
     "HTTP 403 Forbidden",
     "High"),
    ("TC-043", "US-006", "Negatif",
     "TC-043 -- PATCH sur ID inexistant (PATCH /booking/9999999)",
     "Envoyer PATCH /booking/9999999 avec token valide",
     "HTTP 404 ou 405 -- ID inexistant",
     "Medium"),
    ("TC-044", "US-006", "Limite",
     "TC-044 -- PATCH avec body vide (PATCH /booking/{id})",
     "Envoyer PATCH /booking/{id} avec body {} et token valide",
     "HTTP 200 + reservation inchangee -- aucun champ modifie",
     "Low"),

    # ── US-007 -- DELETE /booking/{id} (6 TCs) ───────────────────────────────
    ("TC-045", "US-007", "Positif",
     "TC-045 -- DELETE avec token valide (DELETE /booking/{id})",
     "Creer une reservation, recuperer son ID, envoyer DELETE /booking/{id} avec Cookie token valide",
     "HTTP 201 Created (comportement specifique Restful Booker)",
     "High"),
    ("TC-046", "US-007", "Positif",
     "TC-046 -- Verification suppression par GET apres DELETE",
     "Apres DELETE /booking/{id} reussi, envoyer GET /booking/{id}",
     "HTTP 404 Not Found -- la reservation n'existe plus",
     "High"),
    ("TC-047", "US-007", "Negatif",
     "TC-047 -- DELETE sans token (DELETE /booking/{id})",
     "Envoyer DELETE /booking/{id} sans header d'authentification",
     "HTTP 403 Forbidden",
     "High"),
    ("TC-048", "US-007", "Negatif",
     "TC-048 -- DELETE avec token invalide (DELETE /booking/{id})",
     "Envoyer DELETE /booking/{id} avec Cookie: token=FAKE_TOKEN",
     "HTTP 403 Forbidden",
     "High"),
    ("TC-049", "US-007", "Negatif",
     "TC-049 -- DELETE sur ID inexistant (DELETE /booking/9999999)",
     "Envoyer DELETE /booking/9999999 avec token valide",
     "HTTP 404 ou 405 -- ID inexistant",
     "Medium"),
    ("TC-050", "US-007", "Negatif",
     "TC-050 -- Double DELETE sur le meme ID",
     "Effectuer DELETE /booking/{id}, puis DELETE /booking/{id} une seconde fois",
     "HTTP 404 ou 405 au deuxieme appel -- ressource deja supprimee",
     "Medium"),

    # ── US-008 -- GET /ping (2 TCs) ───────────────────────────────────────────
    ("TC-051", "US-008", "Positif",
     "TC-051 -- Health check standard (GET /ping)",
     "Envoyer GET /ping sans parametre ni authentification",
     "HTTP 201 Created (comportement specifique Restful Booker)",
     "High"),
    ("TC-052", "US-008", "Performance",
     "TC-052 -- Temps de reponse < 3000ms (GET /ping)",
     "Envoyer GET /ping et mesurer le temps de reponse",
     "HTTP 201 + response time < 3000 millisecondes",
     "Medium"),
]


# ── ADF helpers ───────────────────────────────────────────────────────────────

def _t(text):
    return {"type": "text", "text": str(text)}

def _bold(text):
    return {"type": "text", "text": str(text), "marks": [{"type": "strong"}]}

def _heading(level, text):
    return {"type": "heading", "attrs": {"level": level}, "content": [_t(text)]}

def _para(*parts):
    return {"type": "paragraph", "content": [_t(p) if isinstance(p, str) else p for p in parts]}

def _rule():
    return {"type": "rule"}

def _tc_cell(text, header=False):
    return {
        "type": "tableHeader" if header else "tableCell",
        "attrs": {},
        "content": [{"type": "paragraph", "content": [_t(text)]}]
    }

def _tc_row(*cells, header=False):
    return {"type": "tableRow", "content": [_tc_cell(c, header) for c in cells]}

def _table(*rows):
    return {
        "type": "table",
        "attrs": {"isNumberColumnEnabled": False, "layout": "default"},
        "content": list(rows)
    }


def build_tc_adf(tc_id, us_id, tc_type, scenario, expected, priority):
    us_jira_key = US_JIRA.get(us_id, "")
    return {
        "type": "doc",
        "version": 1,
        "content": [
            _heading(2, tc_id),
            _para(_bold("User Story : "), f"{us_id} ({us_jira_key})"),
            _rule(),
            _heading(3, "Informations"),
            _table(
                _tc_row("Attribut",  "Valeur",    header=True),
                _tc_row("ID",        tc_id),
                _tc_row("Type",      tc_type),
                _tc_row("Priorite",  priority),
                _tc_row("US parent", f"{us_id} -- {us_jira_key}"),
            ),
            _rule(),
            _heading(3, "Scenario"),
            _para(scenario),
            _heading(3, "Resultat attendu"),
            _para(expected),
            _rule(),
            _para(_bold("Projet :"), " HBAPI -- Hotel Booking API Automation"),
            _para(_bold("Framework :"), " api-pytest-framework/ -- Python + Pytest + BDD"),
        ]
    }


# ── Création dans Jira ────────────────────────────────────────────────────────

def create_tc_as_subtask(jira, tc_id, us_id, tc_type, summary, scenario, expected, priority):
    parent_key = US_JIRA.get(us_id)
    if not parent_key:
        return None, f"Cle Jira inconnue pour {us_id}"

    adf = build_tc_adf(tc_id, us_id, tc_type, scenario, expected, priority)

    payload = {
        "fields": {
            "project":     {"key": PROJECT},
            "parent":      {"key": parent_key},
            "issuetype":   {"id": "10040"},       # Sous-tâche
            "summary":     summary,
            "description": adf,
            "priority":    {"name": priority},
            "labels":      [tc_id, us_id, tc_type.lower(), "test-case"],
        }
    }
    result = jira._post("/issue", payload)
    return result.get("key"), None


def create_tc_as_task_with_link(jira, tc_id, us_id, tc_type, summary, scenario, expected, priority):
    parent_key = US_JIRA.get(us_id)
    if not parent_key:
        return None, f"Cle Jira inconnue pour {us_id}"

    adf = build_tc_adf(tc_id, us_id, tc_type, scenario, expected, priority)

    payload = {
        "fields": {
            "project":     {"key": PROJECT},
            "issuetype":   {"id": "10039"},       # Tâche
            "summary":     summary,
            "description": adf,
            "priority":    {"name": priority},
            "labels":      [tc_id, us_id, tc_type.lower(), "test-case"],
        }
    }
    result = jira._post("/issue", payload)
    tc_key = result.get("key")

    # Créer le lien "relates to" vers la Story parente
    # /issueLink retourne 201 avec body vide — on appelle requests directement
    import requests as _req
    link_payload = {
        "type":          {"name": "Relates"},
        "inwardIssue":   {"key": parent_key},
        "outwardIssue":  {"key": tc_key},
    }
    r = _req.post(
        f"{JIRA_BASE_URL}/rest/api/3/issueLink",
        json=link_payload,
        auth=jira.auth,
        headers=jira.headers,
        verify=False,
    )
    r.raise_for_status()

    return tc_key, None


# ── Rapport final ──────────────────────────────────────────────────────────────

def print_summary(created, errors, skipped):
    print(f"\n{'=' * 60}")
    print(f"  BILAN")
    print(f"{'=' * 60}")
    print(C.ok(f"  Crees   : {len(created)}"))
    if skipped:
        print(C.dim(f"  Ignores : {len(skipped)}  (--us filtre actif)"))
    if errors:
        print(C.err(f"  Erreurs : {len(errors)}"))
        for tc_id, msg in errors:
            print(C.err(f"    {tc_id}: {msg}"))

    if created:
        # Grouper par US pour affichage
        by_us = {}
        for tc_id, key, us_id in created:
            by_us.setdefault(us_id, []).append((tc_id, key))
        print(f"\n  Sous-taches creees par Story :")
        for us_id, items in by_us.items():
            parent = US_JIRA.get(us_id, "?")
            print(f"    {C.bold(parent)} ({us_id}) -- {len(items)} TC")
            for tc_id, key in items:
                print(f"      {C.ok(key)}  {tc_id}")

    base = os.getenv("JIRA_BASE_URL", "")
    if base and created:
        print(f"\n  Backlog : {base}/jira/software/projects/{PROJECT}/boards")
    print(f"{'=' * 60}\n")


# ── Commande delete ───────────────────────────────────────────────────────────

def cmd_delete(tc_type_filter=None):
    """Recherche et supprime les TCs par type (label) dans Jira."""
    import requests as _req

    label   = tc_type_filter.lower() if tc_type_filter else None
    jql_label = f" AND labels = \"{label}\"" if label else " AND labels = \"test-case\""
    jql     = f"project = {PROJECT}{jql_label} ORDER BY created ASC"

    print(f"\n{'=' * 60}")
    print(f"  TEST CASE AGENT -- DELETE")
    print(f"  Filtre type : {tc_type_filter or 'tous les test-case'}")
    print(f"  JQL         : {jql}")
    if DRY_RUN:
        print(C.warn("  [DRY-RUN] -- aucune suppression reelle"))
    print(f"{'=' * 60}\n")

    jira = JiraClient()
    jira.project = PROJECT

    # Rechercher les issues correspondantes
    encoded_jql = _req.utils.quote(jql)
    data   = jira._get(f"/search/jql?jql={encoded_jql}&maxResults=200&fields=summary,labels,issuetype,status")
    issues = data.get("issues", [])

    if not issues:
        print(C.warn(f"  Aucune issue trouvee avec le filtre : {tc_type_filter or 'test-case'}"))
        return

    print(C.bold(f"  {len(issues)} issue(s) trouvee(s) :\n"))
    for i in issues:
        itype  = i["fields"]["issuetype"]["name"]
        status = i["fields"]["status"]["name"]
        print(f"  {C.bold(i['key'])}  [{itype}]  {i['fields']['summary'][:60]}")
        print(f"          Statut: {C.dim(status)}  Labels: {C.dim(str(i['fields'].get('labels', [])))}")

    if DRY_RUN:
        print(C.warn(f"\n  [DRY-RUN] {len(issues)} issue(s) auraient ete supprimees."))
        return

    print()
    deleted = []
    failed  = []

    for i in issues:
        key = i["key"]
        r   = _req.delete(
            f"{JIRA_BASE_URL}/rest/api/3/issue/{key}",
            auth=jira.auth,
            headers={"Accept": "application/json"},
            verify=False,
        )
        if r.status_code == 204:
            print(C.ok(f"  [OK] {key} supprime"))
            deleted.append(key)
        elif r.status_code == 403:
            print(C.err(f"  [403] {key} -- permission refusee (droits admin requis)"))
            failed.append(key)
        else:
            print(C.err(f"  [ERR] {key} -- HTTP {r.status_code}"))
            failed.append(key)
        time.sleep(0.2)

    print(f"\n{'=' * 60}")
    print(f"  BILAN DELETE")
    print(f"{'=' * 60}")
    print(C.ok(f"  Supprimes : {len(deleted)}"))
    if failed:
        print(C.err(f"  Echecs    : {len(failed)}"))
        print(C.warn(f"\n  [!] Les issues suivantes necessite des droits admin pour etre supprimees :"))
        for k in failed:
            base = os.getenv("JIRA_BASE_URL", "")
            print(f"      {base}/browse/{k}")
        print(C.dim("\n  Pour supprimer en masse depuis Jira :"))
        print(C.dim("  Backlog > selectionner les issues > ... > Supprimer en masse"))
    print(f"{'=' * 60}\n")


# ── Commande gherkin ──────────────────────────────────────────────────────────

# Métadonnées par US : feature name, user story, tags, fichier de sortie
US_META = {
    "US-001": {
        "file":     "auth.feature",
        "feature":  "US-001 -- Authentification (POST /auth)",
        "story":    "En tant que client API, je veux generer un token d'authentification\n"
                    "  afin d'effectuer des operations securisees sur les reservations.",
        "tags":     "@auth @us-001",
        "background": ["Given l'API est disponible"],
        "endpoint": "POST /auth",
    },
    "US-002": {
        "file":     "booking_list.feature",
        "feature":  "US-002 -- Lister les reservations (GET /booking)",
        "story":    "En tant que client API, je veux recuperer la liste de toutes les reservations\n"
                    "  afin de consulter les IDs disponibles et filtrer par criteres.",
        "tags":     "@booking @us-002",
        "background": ["Given l'API est disponible"],
        "endpoint": "GET /booking",
    },
    "US-003": {
        "file":     "booking_get.feature",
        "feature":  "US-003 -- Recuperer une reservation (GET /booking/{id})",
        "story":    "En tant que client API, je veux recuperer le detail d'une reservation par son ID\n"
                    "  afin de consulter ses informations completes.",
        "tags":     "@booking @us-003",
        "background": ["Given l'API est disponible", "And une reservation existe avec un ID valide"],
        "endpoint": "GET /booking/{id}",
    },
    "US-004": {
        "file":     "booking_create.feature",
        "feature":  "US-004 -- Creer une reservation (POST /booking)",
        "story":    "En tant que client API, je veux creer une nouvelle reservation\n"
                    "  afin d'enregistrer un sejour hotelier dans le systeme.",
        "tags":     "@booking @us-004",
        "background": ["Given l'API est disponible"],
        "endpoint": "POST /booking",
    },
    "US-005": {
        "file":     "booking_update.feature",
        "feature":  "US-005 -- Mise a jour complete (PUT /booking/{id})",
        "story":    "En tant que client API authentifie, je veux mettre a jour entierement une reservation\n"
                    "  afin de modifier toutes ses informations en une seule requete.",
        "tags":     "@booking @us-005 @auth",
        "background": ["Given l'API est disponible",
                       "And j'ai un token d'authentification valide",
                       "And une reservation existe avec son ID"],
        "endpoint": "PUT /booking/{id}",
    },
    "US-006": {
        "file":     "booking_patch.feature",
        "feature":  "US-006 -- Mise a jour partielle (PATCH /booking/{id})",
        "story":    "En tant que client API authentifie, je veux mettre a jour partiellement une reservation\n"
                    "  afin de modifier uniquement les champs necessaires.",
        "tags":     "@booking @us-006 @auth",
        "background": ["Given l'API est disponible",
                       "And j'ai un token d'authentification valide",
                       "And une reservation existe avec son ID"],
        "endpoint": "PATCH /booking/{id}",
    },
    "US-007": {
        "file":     "booking_delete.feature",
        "feature":  "US-007 -- Supprimer une reservation (DELETE /booking/{id})",
        "story":    "En tant que client API authentifie, je veux supprimer une reservation\n"
                    "  afin de l'effacer definitivement du systeme.",
        "tags":     "@booking @us-007 @auth",
        "background": ["Given l'API est disponible",
                       "And j'ai un token d'authentification valide"],
        "endpoint": "DELETE /booking/{id}",
    },
    "US-008": {
        "file":     "health_check.feature",
        "feature":  "US-008 -- Health Check (GET /ping)",
        "story":    "En tant que client API, je veux verifier la disponibilite de l'API\n"
                    "  afin de m'assurer qu'elle est operationnelle avant de lancer les tests.",
        "tags":     "@health @us-008 @smoke",
        "background": ["Given l'API est disponible"],
        "endpoint": "GET /ping",
    },
}

# Icônes type → tag Gherkin
TYPE_TAG = {
    "Positif":     "@positif",
    "Negatif":     "@negatif",
    "Securite":    "@securite",
    "Limite":      "@limite",
    "Performance": "@performance",
}


def _extract_http_code(expected):
    """Extrait le(s) code(s) HTTP depuis le texte expected."""
    codes = re.findall(r'\b(200|201|400|401|403|404|405|500)\b', expected)
    return codes


def _build_given(us_id, scenario, meta):
    """Construit les Given spécifiques au scénario (en plus du Background)."""
    givens = []
    s = scenario.lower()

    # Nécessite un booking créé et son ID récupéré
    if "creer une reservation, recuperer son id" in s:
        givens.append("Given j'ai cree une reservation et recupere son ID")
    # Vérification après delete
    elif "apres delete" in s or "delete /booking/{id} reussi" in s:
        givens.append("Given j'ai supprime la reservation avec succes")
    # Double DELETE
    elif "j'ai supprime la reservation {id}" in s or "supprime la reservation" in s:
        givens.append("Given j'ai supprime la reservation {id}")

    return givens


def _build_when(tc_id, us_id, scenario):
    """Construit le step When depuis le texte du scénario."""
    s = scenario

    # Patterns d'envoi HTTP
    patterns = [
        (r"Envoyer POST /auth avec username=admin et password=password123",
         'When j\'envoie POST /auth avec username "admin" et password "password123"'),
        (r"Envoyer POST /auth avec username=wrong et password=wrong",
         'When j\'envoie POST /auth avec username "wrong" et password "wrong"'),
        (r"Envoyer POST /auth avec body vide",
         "When j'envoie POST /auth avec un body vide {}"),
        (r"Envoyer POST /auth sans le champ username",
         "When j'envoie POST /auth sans le champ username"),
        (r"Envoyer POST /auth avec username=\"' OR",
         "When j'envoie POST /auth avec une injection SQL dans username"),
        (r'Envoyer POST /auth avec password=.*script',
         "When j'envoie POST /auth avec un payload XSS dans password"),
        (r"Envoyer GET /booking sans param",
         "When j'envoie GET /booking"),
        (r"Envoyer GET /booking\?firstname=Jim",
         "When j'envoie GET /booking avec le filtre ?firstname=Jim"),
        (r"Envoyer GET /booking\?lastname=Brown",
         "When j'envoie GET /booking avec le filtre ?lastname=Brown"),
        (r"Envoyer GET /booking\?checkin=2018-01-01",
         "When j'envoie GET /booking avec le filtre ?checkin=2018-01-01"),
        (r"Envoyer GET /booking\?checkout=2019-01-01",
         "When j'envoie GET /booking avec le filtre ?checkout=2019-01-01"),
        (r"Envoyer GET /booking\?firstname=XYZ",
         "When j'envoie GET /booking avec ?firstname=XYZ_INEXISTANT"),
        (r"Envoyer GET /booking\?firstname=.*injection|Envoyer GET /booking\?firstname=' OR",
         "When j'envoie GET /booking avec une injection SQL dans le filtre firstname"),
        (r"Creer une reservation, recuperer son ID, puis envoyer GET /booking/\{id\}|GET /booking/\{id\}",
         "When j'envoie GET /booking/{id}"),
        (r"Envoyer GET /booking/9999999",
         "When j'envoie GET /booking/9999999"),
        (r"Envoyer GET /booking/-1",
         "When j'envoie GET /booking/-1"),
        (r"Envoyer GET /booking/abc",
         "When j'envoie GET /booking/abc"),
        (r"Envoyer GET /booking/0",
         "When j'envoie GET /booking/0"),
        (r"valider la reponse contre le schema JSON",
         "When j'envoie GET /booking/{id} et je valide le schema JSON de la reponse"),
        (r"verifier le format des dates",
         "When j'envoie GET /booking/{id} et je verifie le format des dates"),
        (r"Envoyer POST /booking avec.*tous les champs",
         "When j'envoie POST /booking avec tous les champs requis et additionalneeds"),
        (r"Envoyer POST /booking sans le champ additionalneeds",
         "When j'envoie POST /booking sans le champ optionnel additionalneeds"),
        (r"Envoyer POST /booking avec checkin = checkout",
         "When j'envoie POST /booking avec checkin = checkout = 2026-07-01"),
        (r"Envoyer POST /booking sans le champ firstname",
         "When j'envoie POST /booking sans le champ requis firstname"),
        (r"Envoyer POST /booking sans le champ lastname",
         "When j'envoie POST /booking sans le champ requis lastname"),
        (r"Envoyer POST /booking sans le champ totalprice",
         "When j'envoie POST /booking sans le champ requis totalprice"),
        (r"Envoyer POST /booking sans le champ depositpaid",
         "When j'envoie POST /booking sans le champ requis depositpaid"),
        (r"Envoyer POST /booking sans le champ bookingdates",
         "When j'envoie POST /booking sans le champ requis bookingdates"),
        (r"Envoyer POST /booking avec totalprice = -100",
         "When j'envoie POST /booking avec totalprice = -100"),
        (r"Envoyer POST /booking avec checkin=2026-12-31 et checkout=2026-01-01",
         "When j'envoie POST /booking avec checkin posterieur a checkout"),
        (r"Envoyer POST /booking avec body vide",
         "When j'envoie POST /booking avec un body vide {}"),
        (r'Envoyer POST /booking avec firstname=.*script',
         "When j'envoie POST /booking avec un payload XSS dans firstname"),
        (r"PUT /booking/\{id\}.*tous les champs.*Cookie token valide",
         "When j'envoie PUT /booking/{id} avec tous les champs et mon token (Cookie)"),
        (r"PUT /booking/\{id\}.*puis GET",
         "When j'envoie GET /booking/{id} pour verifier la persistence apres PUT"),
        (r"PUT /booking/\{id\} sans header",
         "When j'envoie PUT /booking/{id} sans header d'authentification"),
        (r"PUT /booking/\{id\} avec Cookie.*INVALID",
         "When j'envoie PUT /booking/{id} avec un token invalide"),
        (r"PUT /booking/9999999",
         "When j'envoie PUT /booking/9999999 avec mon token"),
        (r"PUT /booking/\{id\}.*sans.*firstname",
         "When j'envoie PUT /booking/{id} sans le champ requis firstname"),
        (r'PATCH /booking/\{id\}.*\"firstname\".*UpdatedName',
         'When j\'envoie PATCH /booking/{id} avec {"firstname": "UpdatedName"}'),
        (r'PATCH /booking/\{id\}.*\"totalprice\": 999',
         'When j\'envoie PATCH /booking/{id} avec {"totalprice": 999}'),
        (r'PATCH /booking/\{id\}.*lastname.*totalprice',
         'When j\'envoie PATCH /booking/{id} avec {"lastname": "Updated", "totalprice": 500}'),
        (r"PATCH /booking/\{id\} sans header",
         "When j'envoie PATCH /booking/{id} sans header d'authentification"),
        (r"PATCH /booking/\{id\}.*FAKE_TOKEN",
         "When j'envoie PATCH /booking/{id} avec un token invalide"),
        (r"PATCH /booking/9999999",
         "When j'envoie PATCH /booking/9999999 avec mon token"),
        (r"PATCH /booking/\{id\}.*body \{\}",
         "When j'envoie PATCH /booking/{id} avec un body vide {}"),
        (r"DELETE /booking/\{id\}.*Cookie token valide",
         "When j'envoie DELETE /booking/{id} avec mon token (Cookie)"),
        (r"GET /booking/\{id\}.*404.*apres",
         "When j'envoie GET /booking/{id} apres la suppression"),
        (r"DELETE /booking/\{id\} sans header",
         "When j'envoie DELETE /booking/{id} sans header d'authentification"),
        (r"DELETE /booking/\{id\}.*FAKE_TOKEN",
         "When j'envoie DELETE /booking/{id} avec un token invalide"),
        (r"DELETE /booking/9999999",
         "When j'envoie DELETE /booking/9999999 avec mon token"),
        (r"DELETE /booking/\{id\}.*deuxieme fois|DELETE /booking/\{id\} a nouveau",
         "When j'envoie DELETE /booking/{id} une seconde fois"),
        (r"Envoyer GET /ping",
         "When j'envoie GET /ping"),
        (r"mesurer le temps de reponse",
         "When j'envoie GET /ping et je mesure le temps de reponse"),
    ]

    for pattern, when_step in patterns:
        if re.search(pattern, s, re.IGNORECASE):
            return when_step

    # Fallback : extraire METHOD + endpoint du texte
    m = re.search(r'(GET|POST|PUT|PATCH|DELETE)\s+(/\S+)', s)
    if m:
        return f"When j'envoie {m.group(1)} {m.group(2)}"

    return f"When j'execute le scenario : {s[:60]}"


def _build_then(expected):
    """Construit les steps Then/And depuis le texte expected."""
    thens = []
    codes = _extract_http_code(expected)

    # Status code principal
    if codes:
        if len(codes) == 1:
            thens.append(f"Then le status code est {codes[0]}")
        else:
            thens.append(f"Then le status code est {codes[0]} ou {codes[1]}")
    else:
        thens.append("Then la reponse indique une erreur")

    # Assertions additionnelles
    e = expected.lower()
    if "token non vide" in e or "token present" in e:
        thens.append("And la reponse contient un champ \"token\" non vide")
        thens.append("And la longueur du token est superieure a 10 caracteres")
    if "bad credentials" in e:
        thens.append("And la reponse contient {\"reason\": \"Bad credentials\"}")
    if "bookingid" in e:
        thens.append("And la reponse contient un champ \"bookingid\" entier > 0")
    if "objet complet" in e or "objet booking" in e:
        thens.append("And la reponse contient les champs firstname, lastname, totalprice, depositpaid, bookingdates")
    if "schema conforme" in e:
        thens.append("And le schema JSON de la reponse est conforme au modele Booking")
    if "dates valides" in e or "iso 8601" in e:
        thens.append("And les dates checkin et checkout sont au format YYYY-MM-DD")
    if "tableau non vide" in e:
        thens.append("And la reponse est une liste contenant au moins 1 objet {bookingid}")
    if "tableau vide" in e:
        thens.append("And la reponse est une liste vide []")
    if "resultats jim" in e:
        thens.append("And tous les resultats ont firstname = \"Jim\"")
    if "resultats brown" in e:
        thens.append("And tous les resultats ont lastname = \"Brown\"")
    if "tableau" in e and "jim" not in e and "brown" not in e and "vide" not in e and "non vide" not in e:
        thens.append("And la reponse est une liste de reservations")
    if "mis a jour" in e and "confirm" not in e:
        thens.append("And la reponse contient les donnees mises a jour")
    if "get confirme" in e or "persistence" in e.lower():
        thens.append("And un GET /booking/{id} confirme que les modifications sont persistees")
    if "firstname mis a jour" in e:
        thens.append("And la reponse contient le nouveau firstname")
    if "prix mis a jour" in e:
        thens.append("And la reponse contient totalprice = 999")
    if "deux champs mis a jour" in e:
        thens.append("And la reponse contient le nouveau lastname et totalprice")
    if "reservation inchangee" in e or "aucun changement" in e:
        thens.append("And la reservation n'a pas ete modifiee")
    if "201 created" in e:
        thens.append("And le body de la reponse contient \"Created\"")
    if "not found" in e:
        thens.append("And la reponse est 404 Not Found")
    if "latence" in e or "< 3" in e:
        thens.append("And le temps de reponse est inferieur a 3000 millisecondes")
    if "safe" in e or "non execute" in e or "encode" in e or "sanitise" in e:
        thens.append("And le payload est encode ou refuse -- aucune execution")
    if "limite metier" in e:
        thens.append("And la reservation est creee (cas limite accepte par l'API)")

    return thens


def _build_scenario(tc_id, us_id, tc_type, summary, scenario, expected, jira_key, meta):
    """Génère un bloc Scenario Gherkin complet pour un TC."""
    # Titre propre (retirer le préfixe TC-XXX -- )
    title = re.sub(r'^TC-\d{3}\s*--\s*', '', summary).strip()
    tag   = TYPE_TAG.get(tc_type, "@autre")
    tc_tag = f"@tc-{tc_id[-3:]}"

    # Givens spécifiques (en plus du Background)
    extra_givens = _build_given(us_id, scenario, meta)
    when         = _build_when(tc_id, us_id, scenario)
    thens        = _build_then(expected)

    lines = [f"  {tag} {tc_tag}  # {jira_key}"]
    lines.append(f"  Scenario: {tc_id} -- {title}")

    for g in extra_givens:
        lines.append(f"    {g}")

    lines.append(f"    {when}")

    for i, t in enumerate(thens):
        lines.append(f"    {t}")

    return "\n".join(lines)


def _build_feature_content(us_id, tc_rows, meta):
    """Génère le contenu complet d'un fichier .feature pour un US."""
    lines = []

    # En-tête
    lines.append(meta["tags"])
    lines.append(f"Feature: {meta['feature']}")
    lines.append(f"  {meta['story']}")
    lines.append("")

    # Background
    lines.append("  Background:")
    for step in meta["background"]:
        lines.append(f"    {step}")
    lines.append("")

    # Scénarios
    for tc_id, us_id_, tc_type, summary, scenario, expected, priority, jira_key in tc_rows:
        block = _build_scenario(tc_id, us_id_, tc_type, summary, scenario, expected, jira_key, meta)
        lines.append(block)
        lines.append("")

    return "\n".join(lines)


def cmd_gherkin():
    """Fetch TCs depuis Jira et génère les fichiers .feature dans features/."""
    import requests as _req

    us_filter = US_FILTER  # réutilise le flag --us= global

    print(f"\n{'=' * 60}")
    print(f"  TEST CASE AGENT -- GHERKIN")
    print(f"  Source      : Jira HBAPI (labels=test-case)")
    print(f"  Destination : features/")
    print(f"  Filtre US   : {us_filter or 'tous'}")
    if DRY_RUN:
        print(C.warn("  [DRY-RUN] -- affichage sans ecriture"))
    print(f"{'=' * 60}\n")

    jira = JiraClient()
    jira.project = PROJECT

    # 1. Fetch TCs depuis Jira (pagination curseur : /search/jql → nextPageToken)
    jql       = f'project = {PROJECT} AND labels = "test-case" ORDER BY summary ASC'
    encoded   = _req.utils.quote(jql)
    issues    = []
    page_size = 100
    next_token = None
    while True:
        url = (
            f"/search/jql?jql={encoded}&maxResults={page_size}"
            f"&fields=summary,labels,status"
        )
        if next_token:
            url += f"&nextPageToken={next_token}"
        data       = jira._get(url)
        page       = data.get("issues", [])
        issues.extend(page)
        next_token = data.get("nextPageToken")
        if not page or not next_token:
            break

    print(C.ok(f"  {len(issues)} TCs trouves dans Jira\n"))

    # Construire lookup tc_id -> jira_key
    tc_jira = {}
    for i in issues:
        for lbl in i["fields"]["labels"]:
            if re.match(r"TC-\d{3}", lbl):
                tc_jira[lbl] = i["key"]

    # 2. Grouper les TCs par US (source = TEST_CASES)
    by_us = {}
    for tc_id, us_id, tc_type, summary, scenario, expected, priority in TEST_CASES:
        if us_filter and us_id != us_filter:
            continue
        if tc_id not in tc_jira:
            print(C.warn(f"  [!] {tc_id} introuvable dans Jira -- ignore"))
            continue
        jira_key = tc_jira[tc_id]
        by_us.setdefault(us_id, []).append(
            (tc_id, us_id, tc_type, summary, scenario, expected, priority, jira_key)
        )

    if not by_us:
        print(C.err("  Aucun TC a convertir."))
        return

    # 3. Générer les fichiers .feature
    features_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "features"))
    os.makedirs(features_dir, exist_ok=True)

    generated = []
    for us_id, tc_rows in sorted(by_us.items()):
        meta    = US_META.get(us_id)
        if not meta:
            continue

        content  = _build_feature_content(us_id, tc_rows, meta)
        out_path = os.path.join(features_dir, meta["file"])

        print(C.bold(f"\n[{us_id}] -> {meta['file']}  ({len(tc_rows)} scenarios)"))
        for tc_id, *_ in tc_rows:
            jk = tc_jira.get(tc_id, "?")
            print(f"  {C.ok(jk)}  {tc_id}")

        if DRY_RUN:
            print(C.dim(f"\n  [DRY-RUN] contenu prevu :\n"))
            print(C.dim(content[:400] + "..."))
            continue

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)

        print(C.ok(f"  [OK] {out_path}"))
        generated.append(out_path)

    print(f"\n{'=' * 60}")
    print(f"  BILAN GHERKIN")
    print(f"{'=' * 60}")
    print(C.ok(f"  Fichiers generes : {len(generated)}"))
    for p in generated:
        print(f"    {p}")
    print(f"{'=' * 60}\n")


# ── Commande map-gherkin ──────────────────────────────────────────────────────

def _parse_feature_file(filepath):
    """
    Parse un .feature et retourne une liste de tuples :
    (jira_key, tc_id, tags_str, scenario_block, background_block, feature_name, filename)
    """
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    filename    = os.path.basename(filepath)
    feat_m      = re.search(r"^Feature:\s*(.+)$", content, re.MULTILINE)
    feature_name = feat_m.group(1).strip() if feat_m else filename

    # Background complet (avec ses étapes)
    bg_m        = re.search(r"(Background:.*?)(?=\n[ \t]*@|\n[ \t]*Scenario:|\Z)", content, re.DOTALL)
    background  = bg_m.group(1).strip() if bg_m else ""

    # Chaque bloc : tag_line + Scenario
    pattern = r"((?:@\S+\s+)+@tc-\d{3})\s*#\s*(HBAPI-\d+)\s*\n([ \t]+Scenario:.*?)(?=\n[ \t]*@\S|\Z)"
    results = []
    for m in re.finditer(pattern, content, re.DOTALL):
        tags_str      = m.group(1).strip()
        jira_key      = m.group(2).strip()
        scenario_raw  = m.group(3)
        # Dedent (enlève l'indentation commune)
        lines         = scenario_raw.splitlines()
        indent        = len(lines[0]) - len(lines[0].lstrip())
        scenario_block = "\n".join(l[indent:] if len(l) > indent else l for l in lines).strip()

        tc_m = re.search(r"TC-\d{3}", tags_str)
        tc_id = tc_m.group(0) if tc_m else ""
        results.append((jira_key, tc_id, tags_str, scenario_block, background, feature_name, filename))

    return results


def _build_gherkin_adf(tc_id, tags_str, scenario_block, background, feature_name, filename, jira_key):
    """Construit le document ADF à envoyer comme description du TC Jira."""

    # Texte Gherkin brut pour le bloc code
    gherkin_lines = []
    if background:
        gherkin_lines.append(f"# Background commun ({filename})")
        gherkin_lines.append(background)
        gherkin_lines.append("")
    gherkin_lines.append(f"# {tags_str}")
    gherkin_lines.append(scenario_block)
    gherkin_text = "\n".join(gherkin_lines)

    def _txt(t, **marks):
        node = {"type": "text", "text": str(t)}
        if marks:
            node["marks"] = [{"type": k} for k in marks if marks[k]]
        return node

    def _bold(t):
        return {"type": "text", "text": str(t), "marks": [{"type": "strong"}]}

    return {
        "type": "doc",
        "version": 1,
        "content": [
            # Titre
            {
                "type": "heading",
                "attrs": {"level": 3},
                "content": [_txt(f"Scenario Gherkin -- {tc_id}")]
            },
            # Bloc code Gherkin
            {
                "type": "codeBlock",
                "attrs": {"language": "yaml"},   # "gherkin" non supporté par Jira ADF
                "content": [_txt(gherkin_text)]
            },
            # Métadonnées
            {
                "type": "paragraph",
                "content": [
                    _bold("Feature : "), _txt(feature_name),
                ]
            },
            {
                "type": "paragraph",
                "content": [
                    _bold("Fichier  : "), _txt(f"features/{filename}"),
                ]
            },
            {
                "type": "paragraph",
                "content": [
                    _bold("Tags     : "), _txt(tags_str),
                ]
            },
            {
                "type": "paragraph",
                "content": [
                    _bold("Jira TC  : "), _txt(jira_key),
                ]
            },
        ]
    }


def cmd_map_gherkin():
    """
    Lit les .feature dans features/ et met à jour la description de chaque TC Jira
    avec le scénario Gherkin correspondant (traçabilité bidirectionnelle).
    """
    import requests as _req

    features_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "features"))
    feature_files = sorted(f for f in os.listdir(features_dir) if f.endswith(".feature"))

    print(f"\n{'=' * 60}")
    print(f"  TEST CASE AGENT -- MAP-GHERKIN")
    print(f"  Source      : features/ ({len(feature_files)} fichiers)")
    print(f"  Destination : Jira HBAPI (description des TCs)")
    if DRY_RUN:
        print(C.warn("  [DRY-RUN] -- lecture sans ecriture Jira"))
    if US_FILTER:
        print(f"  Filtre US   : {US_FILTER}")
    print(f"{'=' * 60}\n")

    jira = JiraClient()
    jira.project = PROJECT

    # Collecter toutes les tuples (jira_key, ...) de tous les fichiers
    all_entries = []
    for fname in feature_files:
        fpath    = os.path.join(features_dir, fname)
        entries  = _parse_feature_file(fpath)
        all_entries.extend(entries)
        print(C.dim(f"  {fname} : {len(entries)} scenarios"))

    print(f"\n  Total : {len(all_entries)} scenarios a synchroniser\n")

    updated = []
    errors  = []

    for jira_key, tc_id, tags_str, scenario_block, background, feature_name, filename in all_entries:

        # Filtre --us=
        us_in_tags = re.search(r"@us-\d{3}", tags_str)
        if US_FILTER and us_in_tags:
            us_tag = us_in_tags.group(0).replace("@", "").upper().replace("-", "-")  # us-001 → US-001
            if us_tag.upper() != US_FILTER.upper():
                continue

        if DRY_RUN:
            print(f"  [DRY] {C.ok(jira_key)}  {tc_id}  ({tags_str[:40]})")
            updated.append(jira_key)
            continue

        try:
            adf     = _build_gherkin_adf(tc_id, tags_str, scenario_block, background, feature_name, filename, jira_key)
            payload = {"fields": {"description": adf}}

            r = _req.put(
                f"{JIRA_BASE_URL}/rest/api/3/issue/{jira_key}",
                json=payload, auth=jira.auth, headers=jira.headers, verify=False,
            )
            if r.status_code == 204:
                print(f"  {C.ok('[OK]')} {C.bold(jira_key)}  {tc_id}")
                updated.append(jira_key)
            else:
                msg = f"HTTP {r.status_code}"
                try:
                    detail = r.json()
                    if "errorMessages" in detail:
                        msg += " -- " + "; ".join(detail["errorMessages"])
                    elif "errors" in detail:
                        msg += " -- " + str(detail["errors"])
                except Exception:
                    pass
                print(C.err(f"  [ERR] {jira_key}  {tc_id}  {msg}"))
                errors.append((jira_key, msg))

            import time as _time
            _time.sleep(0.2)

        except Exception as e:
            msg = str(e).splitlines()[0]
            print(C.err(f"  [ERR] {jira_key}  {tc_id}  {msg}"))
            errors.append((jira_key, msg))

    print(f"\n{'=' * 60}")
    print(f"  BILAN MAP-GHERKIN")
    print(f"{'=' * 60}")
    print(C.ok(f"  Mis a jour : {len(updated)}"))
    if errors:
        print(C.err(f"  Erreurs    : {len(errors)}"))
        for k, m in errors:
            print(C.err(f"    {k} -- {m}"))
    print(f"{'=' * 60}\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # ── Commande gherkin ──────────────────────────────────────────────────────
    if len(sys.argv) > 1 and sys.argv[1] == "gherkin":
        cmd_gherkin()
        return

    # ── Commande map-gherkin ──────────────────────────────────────────────────
    if len(sys.argv) > 1 and sys.argv[1] == "map-gherkin":
        cmd_map_gherkin()
        return

    # ── Commande delete ───────────────────────────────────────────────────────
    if len(sys.argv) > 1 and sys.argv[1] == "delete":
        tc_type = next((a.split("=")[1] for a in sys.argv if a.startswith("--type=")), None)
        cmd_delete(tc_type)
        return

    mode = "Sous-tâche" if not LINK_ONLY else "Tache + lien Relates"

    print(f"\n{'=' * 60}")
    print(f"  TEST CASE AGENT -- {PROJECT}")
    print(f"  Mode      : {mode}")
    print(f"  Filtre US : {US_FILTER or 'tous (US-001 -> US-008)'}")
    print(f"  TCs total : {len(TEST_CASES)}")
    if DRY_RUN:
        print(C.warn("  [DRY-RUN] -- aucune action reelle"))
    print(f"{'=' * 60}\n")

    jira = JiraClient()
    jira.project = PROJECT

    created = []
    errors  = []
    skipped = []

    # Grouper par US pour affichage
    current_us = None

    for tc_id, us_id, tc_type, summary, scenario, expected, priority in TEST_CASES:

        # Filtre --us=
        if US_FILTER and us_id != US_FILTER:
            skipped.append(tc_id)
            continue

        # Afficher l'en-tête de groupe
        if us_id != current_us:
            current_us = us_id
            parent_key = US_JIRA.get(us_id, "?")
            count_in_us = sum(1 for tc in TEST_CASES if tc[1] == us_id)
            print(C.bold(f"\n[{us_id}] {parent_key}  ({count_in_us} TCs)"))

        icon = {"Positif": "[+]", "Negatif": "[-]", "Securite": "[S]",
                "Performance": "[P]", "Limite": "[L]"}.get(tc_type, "[?]")

        if DRY_RUN:
            print(f"  {icon} {tc_id}  {C.dim(summary[:55])}")
            created.append((tc_id, "DRY-RUN", us_id))
            continue

        try:
            if LINK_ONLY:
                key, err = create_tc_as_task_with_link(
                    jira, tc_id, us_id, tc_type, summary, scenario, expected, priority)
            else:
                key, err = create_tc_as_subtask(
                    jira, tc_id, us_id, tc_type, summary, scenario, expected, priority)

            if err:
                print(C.err(f"  {icon} {tc_id}  [ERR] {err}"))
                errors.append((tc_id, err))
            else:
                url = f"{os.getenv('JIRA_BASE_URL', '')}/browse/{key}"
                print(f"  {icon} {C.ok(key)}  {tc_id}  {C.dim(url)}")
                created.append((tc_id, key, us_id))

            # Pause anti-rate-limit
            time.sleep(0.3)

        except Exception as e:
            msg = str(e).splitlines()[0]
            # Si sous-tâche échoue, tenter avec Tâche + lien
            if not LINK_ONLY and "subtask" in msg.lower():
                print(C.warn(f"  {icon} {tc_id}  [!] Sous-tache impossible, tentative Tache+lien..."))
                try:
                    key, err2 = create_tc_as_task_with_link(
                        jira, tc_id, us_id, tc_type, summary, scenario, expected, priority)
                    if key:
                        url = f"{os.getenv('JIRA_BASE_URL', '')}/browse/{key}"
                        print(f"      {C.ok(key)}  {C.dim('(Tache + lien Relates)')}")
                        created.append((tc_id, key, us_id))
                    else:
                        errors.append((tc_id, str(err2)))
                    time.sleep(0.3)
                except Exception as e2:
                    errors.append((tc_id, str(e2).splitlines()[0]))
            else:
                print(C.err(f"  {icon} {tc_id}  [ERR] {msg}"))
                errors.append((tc_id, msg))

    print_summary(created, errors, skipped)


if __name__ == "__main__":
    main()
