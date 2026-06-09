# ============================================================
# User Stories Agent -- Création des 8 US dans Jira HBAPI
# ============================================================
# Crée US-001 à US-008 dans le backlog du projet HBAPI.
# Chaque story contient : user story, critères d'acceptance,
# tableau des cas de test, info endpoint et priorité.
#
# Usage:
#   python agents/user-stories-agent.py
#   python agents/user-stories-agent.py --dry-run
# ============================================================

import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))

from jira_fetcher_agent import JiraClient

DRY_RUN      = "--dry-run" in sys.argv
PROJECT_KEY  = "HBAPI"


# ── ADF helpers ───────────────────────────────────────────────────────────────

def t(text):
    return {"type": "text", "text": str(text)}

def bold(text):
    return {"type": "text", "text": str(text), "marks": [{"type": "strong"}]}

def italic(text):
    return {"type": "text", "text": str(text), "marks": [{"type": "em"}]}

def code_inline(text):
    return {"type": "text", "text": str(text), "marks": [{"type": "code"}]}

def heading(level, text):
    return {"type": "heading", "attrs": {"level": level}, "content": [t(text)]}

def para(*parts):
    content = [t(p) if isinstance(p, str) else p for p in parts]
    return {"type": "paragraph", "content": content}

def rule():
    return {"type": "rule"}

def bullet_list(*items):
    return {
        "type": "bulletList",
        "content": [
            {"type": "listItem", "content": [
                {"type": "paragraph", "content": [t(item)]}
            ]}
            for item in items
        ]
    }

def ordered_list(*items):
    return {
        "type": "orderedList",
        "content": [
            {"type": "listItem", "content": [
                {"type": "paragraph", "content": [
                    t(item) if isinstance(item, str) else item
                ]}
            ]}
            for item in items
        ]
    }

def tc(text, header=False):
    cell_type = "tableHeader" if header else "tableCell"
    return {
        "type": cell_type,
        "attrs": {},
        "content": [{"type": "paragraph", "content": [t(text)]}]
    }

def tr(*cells, header=False):
    return {"type": "tableRow", "content": [tc(c, header) for c in cells]}

def table(*rows):
    return {
        "type": "table",
        "attrs": {"isNumberColumnEnabled": False, "layout": "default"},
        "content": list(rows)
    }


# ── Définition des 8 User Stories ────────────────────────────────────────────

USER_STORIES = [
    {
        "id":       "US-001",
        "summary":  "US-001 -- Authentification (POST /auth)",
        "priority": "High",
        "labels":   ["US-001", "auth", "regression"],
        "endpoint": "POST /auth",
        "auth":     "Non requise",
        "tc_range": "TC-001 a TC-005",
        "passants": 1,
        "non_passants": 4,
        "total": 5,
        "user_story": "En tant que client API, je veux generer un token d'authentification afin d'effectuer des operations securisees sur les reservations.",
        "acceptance_criteria": [
            "POST /auth avec username=admin et password=password123 retourne HTTP 200 et un token non vide (longueur > 10 chars)",
            "POST /auth avec credentials incorrects retourne HTTP 200 avec body {\"reason\": \"Bad credentials\"}",
            "POST /auth sans le champ username retourne une erreur d'authentification",
            "POST /auth sans le champ password retourne une erreur d'authentification",
            "POST /auth avec injection SQL dans username ne compromet pas le systeme",
        ],
        "test_cases": [
            ("TC-001", "Token valide avec admin/password123",   "200 + token non vide"),
            ("TC-002", "Credentials incorrects wrong/wrong",    "200 + bad credentials"),
            ("TC-003", "Champs username et password manquants", "200 + bad credentials"),
            ("TC-004", "SQL injection dans username",           "200 + bad credentials"),
            ("TC-005", "XSS payload dans password",             "200 + bad credentials"),
        ],
    },
    {
        "id":       "US-002",
        "summary":  "US-002 -- Lister les reservations (GET /booking)",
        "priority": "High",
        "labels":   ["US-002", "booking", "regression"],
        "endpoint": "GET /booking",
        "auth":     "Non requise",
        "tc_range": "TC-006 a TC-012",
        "passants": 5,
        "non_passants": 2,
        "total": 7,
        "user_story": "En tant que client API, je veux recuperer la liste de toutes les reservations afin de consulter les IDs disponibles et filtrer par criteres.",
        "acceptance_criteria": [
            "GET /booking sans filtre retourne HTTP 200 et une liste d'objets {bookingid: N} non vide",
            "GET /booking?firstname=Jim filtre les reservations par prenom",
            "GET /booking?lastname=Brown filtre les reservations par nom",
            "GET /booking?checkin=YYYY-MM-DD filtre par date d'arrivee",
            "GET /booking?checkout=YYYY-MM-DD filtre par date de depart",
            "GET /booking?firstname=INEXISTANT retourne HTTP 200 avec liste vide []",
            "Les parametres de filtre avec injection SQL ne compromettent pas le systeme",
        ],
        "test_cases": [
            ("TC-006", "Liste complete sans filtre",            "200 + tableau non vide"),
            ("TC-007", "Filtre ?firstname=Jim",                 "200 + resultats Jim"),
            ("TC-008", "Filtre ?lastname=Brown",                "200 + resultats Brown"),
            ("TC-009", "Filtre ?checkin=2018-01-01",            "200 + tableau"),
            ("TC-010", "Filtre ?checkout=2019-01-01",           "200 + tableau"),
            ("TC-011", "Filtre firstname inexistant (XYZ)",     "200 + tableau vide"),
            ("TC-012", "Filtre SQL injection dans firstname",   "200 + tableau vide ou safe"),
        ],
    },
    {
        "id":       "US-003",
        "summary":  "US-003 -- Recuperer une reservation (GET /booking/{id})",
        "priority": "High",
        "labels":   ["US-003", "booking", "regression"],
        "endpoint": "GET /booking/{id}",
        "auth":     "Non requise",
        "tc_range": "TC-013 a TC-019",
        "passants": 3,
        "non_passants": 4,
        "total": 7,
        "user_story": "En tant que client API, je veux recuperer le detail d'une reservation par son ID afin de consulter ses informations completes.",
        "acceptance_criteria": [
            "GET /booking/{id} avec ID existant retourne HTTP 200 et l'objet complet (firstname, lastname, totalprice, depositpaid, bookingdates)",
            "La reponse JSON est conforme au schema defini (jsonschema validation)",
            "Les dates checkin et checkout sont au format ISO 8601 (YYYY-MM-DD)",
            "GET /booking/9999999 (ID inexistant) retourne HTTP 404",
            "GET /booking/-1 (ID negatif) retourne HTTP 404",
            "GET /booking/abc (ID non numerique) retourne HTTP 404",
            "GET /booking/0 retourne HTTP 404",
        ],
        "test_cases": [
            ("TC-013", "ID existant valide",                    "200 + objet complet"),
            ("TC-014", "Validation schema JSON",                "200 + schema conforme"),
            ("TC-015", "Dates format ISO 8601 valides",         "200 + dates valides"),
            ("TC-016", "ID inexistant (9999999)",               "404 Not Found"),
            ("TC-017", "ID string non numerique (abc)",         "404 Not Found"),
            ("TC-018", "ID negatif (-1)",                       "404 Not Found"),
            ("TC-019", "ID zero (0)",                           "404 Not Found"),
        ],
    },
    {
        "id":       "US-004",
        "summary":  "US-004 -- Creer une reservation (POST /booking)",
        "priority": "High",
        "labels":   ["US-004", "booking", "regression"],
        "endpoint": "POST /booking",
        "auth":     "Non requise",
        "tc_range": "TC-020 a TC-031",
        "passants": 3,
        "non_passants": 9,
        "total": 12,
        "user_story": "En tant que client API, je veux creer une nouvelle reservation afin d'enregistrer un sejour hotelier dans le systeme.",
        "acceptance_criteria": [
            "POST /booking avec tous les champs requis retourne HTTP 200/201 et un bookingid entier > 0",
            "La reponse contient l'objet booking cree avec toutes ses donnees",
            "Le champ additionalneeds est optionnel -- la creation reussit sans lui",
            "POST /booking sans firstname retourne HTTP 400 ou 500",
            "POST /booking sans lastname retourne HTTP 400 ou 500",
            "POST /booking sans totalprice retourne HTTP 400 ou 500",
            "POST /booking sans depositpaid retourne HTTP 400 ou 500",
            "POST /booking sans bookingdates retourne HTTP 400 ou 500",
            "totalprice negatif est rejete (400 ou 500)",
            "checkin posterieur a checkout est rejete (400 ou 500)",
            "Body vide {} est rejete (400 ou 500)",
            "Payload XSS dans firstname est encode ou refuse",
        ],
        "test_cases": [
            ("TC-020", "Creation avec tous les champs valides",  "200/201 + bookingid"),
            ("TC-021", "Creation sans additionalneeds",          "200/201 + bookingid"),
            ("TC-022", "Dates checkin = checkout",               "200/201 -- limite metier"),
            ("TC-023", "Champ firstname manquant",               "400 ou 500"),
            ("TC-024", "Champ lastname manquant",                "400 ou 500"),
            ("TC-025", "Champ totalprice manquant",              "400 ou 500"),
            ("TC-026", "Champ depositpaid manquant",             "400 ou 500"),
            ("TC-027", "Champ bookingdates manquant",            "400 ou 500"),
            ("TC-028", "totalprice negatif (-100)",              "400 ou 500"),
            ("TC-029", "checkin apres checkout",                 "400 -- inversion dates"),
            ("TC-030", "Body vide {}",                           "400 ou 500"),
            ("TC-031", "XSS payload dans firstname",             "400 ou encode"),
        ],
    },
    {
        "id":       "US-005",
        "summary":  "US-005 -- Mise a jour complete (PUT /booking/{id})",
        "priority": "Medium",
        "labels":   ["US-005", "booking", "regression", "auth"],
        "endpoint": "PUT /booking/{id}",
        "auth":     "Oui -- Cookie token ou Basic Auth",
        "tc_range": "TC-032 a TC-037",
        "passants": 2,
        "non_passants": 4,
        "total": 6,
        "user_story": "En tant que client API authentifie, je veux mettre a jour entierement une reservation afin de modifier toutes ses informations en une seule requete.",
        "acceptance_criteria": [
            "PUT /booking/{id} avec token valide (Cookie) et tous les champs retourne HTTP 200",
            "La reponse contient l'objet reservation completement mis a jour",
            "Un GET /booking/{id} subsequant confirme la persistence des modifications",
            "PUT /booking/{id} sans authentification retourne HTTP 403",
            "PUT /booking/{id} avec token invalide retourne HTTP 403",
            "PUT /booking/9999999 (ID inexistant) retourne HTTP 404 ou 405",
            "PUT /booking/{id} avec un champ requis manquant retourne HTTP 400",
        ],
        "test_cases": [
            ("TC-032", "MAJ complete avec token valide (Cookie)",  "200 + objet mis a jour"),
            ("TC-033", "Verification persistence (GET apres PUT)", "200 + GET confirme MAJ"),
            ("TC-034", "PUT sans token d'auth",                    "403 Forbidden"),
            ("TC-035", "PUT avec token invalide",                  "403 Forbidden"),
            ("TC-036", "PUT sur ID inexistant (9999999)",          "404 ou 405"),
            ("TC-037", "PUT sans champ requis (firstname)",        "400 Bad Request"),
        ],
    },
    {
        "id":       "US-006",
        "summary":  "US-006 -- Mise a jour partielle (PATCH /booking/{id})",
        "priority": "Medium",
        "labels":   ["US-006", "booking", "regression", "auth"],
        "endpoint": "PATCH /booking/{id}",
        "auth":     "Oui -- Cookie token ou Basic Auth",
        "tc_range": "TC-038 a TC-044",
        "passants": 3,
        "non_passants": 4,
        "total": 7,
        "user_story": "En tant que client API authentifie, je veux mettre a jour partiellement une reservation afin de modifier uniquement les champs necessaires sans impacter les autres.",
        "acceptance_criteria": [
            "PATCH /booking/{id} avec {\"firstname\": \"X\"} met a jour uniquement firstname (HTTP 200)",
            "Les autres champs non inclus dans le body restent inchanges",
            "PATCH /booking/{id} avec {\"totalprice\": 999} retourne HTTP 200 et totalprice = 999",
            "PATCH /booking/{id} sans authentification retourne HTTP 403",
            "PATCH /booking/{id} avec token invalide retourne HTTP 403",
            "PATCH /booking/9999999 retourne HTTP 404 ou 405",
            "PATCH avec body vide {} retourne HTTP 200 et laisse la reservation inchangee",
        ],
        "test_cases": [
            ("TC-038", "PATCH firstname uniquement",             "200 + firstname mis a jour"),
            ("TC-039", "PATCH totalprice uniquement",            "200 + prix mis a jour"),
            ("TC-040", "PATCH lastname + totalprice",            "200 + deux champs mis a jour"),
            ("TC-041", "PATCH sans token",                       "403 Forbidden"),
            ("TC-042", "PATCH token invalide",                   "403 Forbidden"),
            ("TC-043", "PATCH ID inexistant",                    "404 ou 405"),
            ("TC-044", "PATCH body vide {}",                     "200 -- reservation inchangee"),
        ],
    },
    {
        "id":       "US-007",
        "summary":  "US-007 -- Supprimer une reservation (DELETE /booking/{id})",
        "priority": "Medium",
        "labels":   ["US-007", "booking", "regression", "auth"],
        "endpoint": "DELETE /booking/{id}",
        "auth":     "Oui -- Cookie token ou Basic Auth",
        "tc_range": "TC-045 a TC-050",
        "passants": 2,
        "non_passants": 4,
        "total": 6,
        "user_story": "En tant que client API authentifie, je veux supprimer une reservation afin de l'effacer definitivement du systeme.",
        "acceptance_criteria": [
            "DELETE /booking/{id} avec token valide retourne HTTP 201 (comportement Restful Booker)",
            "Apres suppression, GET /booking/{id} retourne HTTP 404 (suppression confirmee)",
            "DELETE /booking/{id} sans authentification retourne HTTP 403",
            "DELETE /booking/{id} avec token invalide retourne HTTP 403",
            "DELETE /booking/9999999 (ID inexistant) retourne HTTP 404 ou 405",
            "Un double DELETE sur le meme ID retourne HTTP 404 ou 405 au deuxieme appel",
        ],
        "test_cases": [
            ("TC-045", "DELETE avec token valide (Cookie)",      "201 Created"),
            ("TC-046", "GET apres DELETE confirme suppression",  "404 Not Found"),
            ("TC-047", "DELETE sans token",                      "403 Forbidden"),
            ("TC-048", "DELETE token invalide",                  "403 Forbidden"),
            ("TC-049", "DELETE ID inexistant (9999999)",         "404 ou 405"),
            ("TC-050", "Double DELETE meme ID",                  "405 deuxieme appel"),
        ],
    },
    {
        "id":       "US-008",
        "summary":  "US-008 -- Health Check (GET /ping)",
        "priority": "Low",
        "labels":   ["US-008", "health-check", "smoke"],
        "endpoint": "GET /ping",
        "auth":     "Non requise",
        "tc_range": "TC-051 a TC-052",
        "passants": 2,
        "non_passants": 0,
        "total": 2,
        "user_story": "En tant que client API, je veux verifier la disponibilite de l'API afin de m'assurer qu'elle est operationnelle avant de lancer les suites de tests.",
        "acceptance_criteria": [
            "GET /ping retourne HTTP 201 (comportement specifique Restful Booker)",
            "Le temps de reponse est inferieur a 3000ms",
            "Le health check sert de pre-condition pour les autres tests (smoke test)",
        ],
        "test_cases": [
            ("TC-051", "Health check standard",                  "201 Created"),
            ("TC-052", "Response time < 3000ms",                 "201 + latence OK"),
        ],
    },
]


# ── Construction ADF par story ────────────────────────────────────────────────

def build_story_adf(us):
    content = [
        # Titre et user story
        heading(2, us["id"] + " -- " + us["endpoint"]),
        para(italic(us["user_story"])),
        rule(),

        # Infos technique
        heading(3, "Informations techniques"),
        table(
            tr("Attribut",  "Valeur",           header=True),
            tr("Endpoint",  us["endpoint"]),
            tr("Auth",      us["auth"]),
            tr("Cas de test", us["tc_range"]),
            tr("Passants",  str(us["passants"])),
            tr("Non-passants", str(us["non_passants"])),
            tr("Total",     str(us["total"])),
        ),
        rule(),

        # Critères d'acceptance
        heading(3, "Criteres d'acceptance"),
        ordered_list(*us["acceptance_criteria"]),
        rule(),

        # Tableau des cas de test
        heading(3, "Cas de test"),
        table(
            tr("ID", "Scenario", "Resultat attendu", header=True),
            *[tr(tc_id, scenario, expected) for tc_id, scenario, expected in us["test_cases"]]
        ),
        rule(),

        # Footer
        para(bold("Projet :"), " HBAPI -- Hotel Booking API Automation"),
        para(bold("Framework :"), " api-pytest-framework/ -- Python + Pytest + BDD + POM"),
    ]

    return {"type": "doc", "version": 1, "content": content}


# ── Création dans Jira ────────────────────────────────────────────────────────

def create_story(jira, us):
    adf = build_story_adf(us)

    if DRY_RUN:
        print(f"  [DRY-RUN] Aurait cree : {us['summary']}")
        return None

    payload = {
        "fields": {
            "project":     {"key": PROJECT_KEY},
            "issuetype":   {"id": "10006"},
            "summary":     us["summary"],
            "description": adf,
            "priority":    {"name": us["priority"]},
            "labels":      us["labels"],
        }
    }
    return jira._post("/issue", payload)


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    print(f"\n{'=' * 60}")
    print(f"  USER STORIES AGENT -- {PROJECT_KEY}")
    print(f"  Creation de {len(USER_STORIES)} User Stories dans le backlog")
    print(f"{'=' * 60}")
    if DRY_RUN:
        print("  MODE DRY-RUN -- aucune action reelle\n")

    jira = JiraClient()
    jira.project = PROJECT_KEY

    created_keys = []
    errors       = []

    for i, us in enumerate(USER_STORIES, 1):
        print(f"\n[{i}/{len(USER_STORIES)}] {us['id']} -- {us['endpoint']}")
        try:
            result = create_story(jira, us)
            if result:
                key = result.get("key", "")
                url = f"{os.getenv('JIRA_BASE_URL', '')}/browse/{key}"
                print(f"  [OK] {key} -- {us['summary'][:50]}")
                print(f"       {url}")
                created_keys.append(key)
            # Pause entre créations pour éviter le rate-limiting
            if not DRY_RUN and i < len(USER_STORIES):
                time.sleep(0.5)
        except Exception as e:
            msg = str(e).split("\n")[0]
            print(f"  [ERR] {msg}")
            errors.append((us["id"], msg))

    # Bilan
    print(f"\n{'=' * 60}")
    print(f"  BILAN")
    print(f"{'=' * 60}")
    print(f"  Stories creees  : {len(created_keys)}")
    if created_keys:
        print(f"  Cles Jira       : {', '.join(created_keys)}")
    if errors:
        print(f"  Erreurs         : {len(errors)}")
        for us_id, msg in errors:
            print(f"    {us_id}: {msg}")

    base = os.getenv("JIRA_BASE_URL", "")
    if base and not DRY_RUN and created_keys:
        print(f"\n  Backlog : {base}/jira/software/projects/{PROJECT_KEY}/boards")
    print(f"{'=' * 60}\n")

    return created_keys


if __name__ == "__main__":
    run()
