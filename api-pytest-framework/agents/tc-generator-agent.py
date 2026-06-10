# ============================================================
# TC Generator Agent — Génération de cas de test (Structured Output)
# ============================================================
# Utilise chat_structured() pour garantir un JSON conforme au schéma.
# Zéro parsing fragile : le LLM est forcé au format exact.
#
# Usage:
#   python agents/tc-generator-agent.py generate US-001  → TCs pour un endpoint
#   python agents/tc-generator-agent.py generate all     → tous les endpoints
#   python agents/tc-generator-agent.py write US-003     → écrit dans features/
#   python agents/tc-generator-agent.py preview US-002   → affiche sans écrire
# ============================================================

import sys, os, json, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm

FRAMEWORK    = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FEATURES_DIR = os.path.join(FRAMEWORK, "features")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

# ── Schéma JSON strict (Structured Output) ────────────────────────────────
# C'est ce schéma qui est transmis au LLM.
# Le LLM DOIT retourner exactement ce format — chat_structured() le garantit.

TC_SCHEMA = {
    "type": "object",
    "properties": {
        "test_cases": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tc_id":           {"type": "string",  "description": "ex: TC-015"},
                    "us_id":           {"type": "string",  "description": "ex: US-003"},
                    "type":            {"type": "string",  "enum": ["positif", "negatif", "auth", "limite", "securite", "performance"]},
                    "priority":        {"type": "string",  "enum": ["critical", "high", "medium", "low"]},
                    "title":           {"type": "string",  "description": "Description courte du scénario"},
                    "given":           {"type": "string",  "description": "Précondition Gherkin"},
                    "when":            {"type": "string",  "description": "Action Gherkin"},
                    "then":            {"type": "string",  "description": "Résultat attendu Gherkin"},
                    "expected_status": {"type": "integer", "description": "Code HTTP attendu (200, 201, 400, 401, 403, 404, 422...)"},
                    "tags":            {"type": "array",   "items": {"type": "string"}, "description": "ex: ['smoke', 'critical']"}
                },
                "required": ["tc_id", "us_id", "type", "priority", "title", "given", "when", "then", "expected_status", "tags"]
            }
        }
    },
    "required": ["test_cases"]
}

# ── Endpoints du framework restful-booker ─────────────────────────────────

ENDPOINTS = {
    "US-001": {
        "path":   "POST /auth",
        "desc":   "Génère un token d'authentification",
        "types":  ["positif", "negatif", "securite"],
        "method": "POST",
        "body":   '{"username": "admin", "password": "password123"}'
    },
    "US-002": {
        "path":   "GET /booking",
        "desc":   "Liste toutes les réservations avec filtres optionnels",
        "types":  ["positif", "negatif", "limite"],
        "method": "GET",
        "body":   None
    },
    "US-003": {
        "path":   "POST /booking",
        "desc":   "Crée une nouvelle réservation",
        "types":  ["positif", "negatif", "limite"],
        "method": "POST",
        "body":   '{"firstname": "Jim", "lastname": "Brown", "totalprice": 111, "depositpaid": true, "bookingdates": {...}}'
    },
    "US-004": {
        "path":   "GET /booking/{id}",
        "desc":   "Récupère les détails d'une réservation par ID",
        "types":  ["positif", "negatif"],
        "method": "GET",
        "body":   None
    },
    "US-005": {
        "path":   "PUT /booking/{id}",
        "desc":   "Modifie complètement une réservation (requiert auth token)",
        "types":  ["positif", "negatif", "auth"],
        "method": "PUT",
        "body":   "Corps complet obligatoire"
    },
    "US-006": {
        "path":   "PATCH /booking/{id}",
        "desc":   "Modifie partiellement une réservation (requiert auth token)",
        "types":  ["positif", "negatif", "auth"],
        "method": "PATCH",
        "body":   "Corps partiel accepté"
    },
    "US-007": {
        "path":   "DELETE /booking/{id}",
        "desc":   "Supprime une réservation (requiert auth token)",
        "types":  ["positif", "negatif", "auth", "securite"],
        "method": "DELETE",
        "body":   None
    },
    "US-008": {
        "path":   "GET /ping",
        "desc":   "Healthcheck de l'API",
        "types":  ["positif", "performance"],
        "method": "GET",
        "body":   None
    },
}

# TC numbering : dernier TC connu dans les features existantes + 1
def _next_tc_start() -> int:
    all_tcs = []
    for f in os.listdir(FEATURES_DIR) if os.path.isdir(FEATURES_DIR) else []:
        if f.endswith(".feature"):
            content = open(os.path.join(FEATURES_DIR, f), encoding="utf-8").read()
            all_tcs.extend([int(m) for m in re.findall(r"TC-(\d+)", content)])
    return max(all_tcs, default=0) + 1


# ── Génération d'un endpoint via Structured Output ─────────────────────────

def generate_tcs_for_endpoint(us_id: str, tc_start: int) -> list:
    ep = ENDPOINTS.get(us_id)
    if not ep:
        print(f"{R}  Endpoint {us_id} inconnu.{E}")
        return []

    types_str = ", ".join(ep["types"])
    body_info = f"Corps de requête : {ep['body']}" if ep["body"] else "Pas de corps requis"

    messages = [{
        "role": "user",
        "content": (
            f"Génère des cas de test API BDD pour cet endpoint :\n\n"
            f"  ID       : {us_id}\n"
            f"  Path     : {ep['path']}\n"
            f"  Méthode  : {ep['method']}\n"
            f"  Desc     : {ep['desc']}\n"
            f"  {body_info}\n\n"
            f"Types de test à générer : {types_str}\n"
            f"Commence la numérotation à TC-{tc_start:03d}.\n\n"
            f"Règles :\n"
            f"- Un TC par type (total : {len(ep['types'])} TCs)\n"
            f"- given/when/then en français, concis et testable\n"
            f"- expected_status HTTP correct pour chaque cas\n"
            f"- tags : inclure le type, 'smoke' si positif critique\n"
            f"- priority : critical si positif ou auth, high si negatif, medium sinon\n"
        )
    }]

    print(f"{C}  Appel LLM Structured Output pour {us_id}...{E}", end=" ", flush=True)
    try:
        result = llm.chat_structured(messages, TC_SCHEMA)
        tcs = result.get("test_cases", [])
        print(f"{G}{len(tcs)} TCs générés{E}")
        return tcs
    except Exception as e:
        print(f"{R}ERREUR : {e}{E}")
        return []


# ── Affichage formaté ──────────────────────────────────────────────────────

def print_tc(tc: dict):
    prio_color = G if tc["priority"] == "critical" else Y if tc["priority"] == "high" else C
    type_color = G if tc["type"] == "positif" else R if tc["type"] in ("negatif", "securite") else Y
    tags_str   = " ".join([f"@{t}" for t in tc.get("tags", [])])

    print(f"\n  {W}{tc['tc_id']}{E} [{type_color}{tc['type']}{E}] {prio_color}{tc['priority']}{E}")
    print(f"  {W}{tc['title']}{E}")
    print(f"  {Y}{tags_str} @{tc['us_id']}{E}")
    print(f"  {C}Given{E}  {tc['given']}")
    print(f"  {C}When{E}   {tc['when']}")
    print(f"  {C}Then{E}   {tc['then']}")
    print(f"  {C}HTTP{E}   {tc['expected_status']}")


# ── Conversion TCs → Gherkin .feature ─────────────────────────────────────

def tcs_to_gherkin(us_id: str, tcs: list) -> str:
    ep = ENDPOINTS[us_id]
    lines = [
        f"# Généré par tc-generator-agent (Structured Output)",
        f"# Endpoint : {ep['path']}",
        f"",
        f"Feature: {ep['desc']} [{us_id}]",
        f"  En tant que client API",
        f"  Je veux pouvoir utiliser {ep['path']}",
        f"  Afin de {ep['desc'].lower()}",
        f""
    ]
    for tc in tcs:
        tags_str = " ".join([f"@{t}" for t in tc.get("tags", [])])
        lines += [
            f"  @{tc['tc_id']} @{tc['us_id']} @{tc['type']} {tags_str}",
            f"  Scenario: {tc['title']}",
            f"    Given {tc['given']}",
            f"    When  {tc['when']}",
            f"    Then  {tc['then']}",
            f""
        ]
    return "\n".join(lines)


# ── Commandes ──────────────────────────────────────────────────────────────

def cmd_generate(target: str):
    print(f"\n{W}TC GENERATOR — Structured Output{E}")
    print(f"{Y}Schéma JSON strict → zéro parsing fragile{E}\n")

    targets = list(ENDPOINTS.keys()) if target == "all" else [target.upper()]
    tc_num  = _next_tc_start()
    all_tcs = {}

    for us in targets:
        if us not in ENDPOINTS:
            print(f"{R}  {us} inconnu. Endpoints valides : {', '.join(ENDPOINTS.keys())}{E}")
            continue
        tcs = generate_tcs_for_endpoint(us, tc_num)
        if tcs:
            all_tcs[us] = tcs
            for tc in tcs:
                print_tc(tc)
            tc_num += len(tcs)

    return all_tcs


def cmd_write(target: str):
    all_tcs = cmd_generate(target)
    if not all_tcs:
        return

    os.makedirs(FEATURES_DIR, exist_ok=True)
    for us, tcs in all_tcs.items():
        gherkin  = tcs_to_gherkin(us, tcs)
        filename = f"{us.lower().replace('-', '_')}.feature"
        filepath = os.path.join(FEATURES_DIR, filename)

        # Ne pas écraser un fichier existant non vide
        if os.path.exists(filepath) and os.path.getsize(filepath) > 100:
            backup = filepath + ".bak"
            os.rename(filepath, backup)
            print(f"\n{Y}  Backup : {filename}.bak (fichier existant conservé){E}")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(gherkin)
        print(f"{G}  Écrit : features/{filename} ({len(tcs)} scénarios){E}")


def cmd_preview(target: str):
    all_tcs = cmd_generate(target)
    if not all_tcs:
        return

    print(f"\n{W}{'='*58}{E}")
    print(f"{W}  APERÇU GHERKIN{E}")
    print(f"{W}{'='*58}{E}")

    for us, tcs in all_tcs.items():
        print(f"\n{C}--- features/{us.lower().replace('-', '_')}.feature ---{E}")
        print(tcs_to_gherkin(us, tcs))


def print_help():
    print(f"""
{W}TC GENERATOR AGENT — Structured Output{E}

  python agents/tc-generator-agent.py generate US-001   Génère les TCs (affiche)
  python agents/tc-generator-agent.py generate all      Tous les endpoints
  python agents/tc-generator-agent.py write    US-003   Génère + écrit dans features/
  python agents/tc-generator-agent.py preview  US-002   Affiche le Gherkin sans écrire

{W}Pourquoi Structured Output ?{E}
  Sans : LLM retourne du texte libre → parsing fragile → erreurs silencieuses
  Avec : LLM forcé au schéma JSON exact → json.loads() garanti → zéro hallucination

{W}Schéma appliqué :{E}
  tc_id, us_id, type, priority, title, given, when, then, expected_status, tags
""")


# ── Main ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd    = sys.argv[1] if len(sys.argv) > 1 else "help"
    target = sys.argv[2] if len(sys.argv) > 2 else "help"

    if cmd == "generate":
        cmd_generate(target)
    elif cmd == "write":
        cmd_write(target)
    elif cmd == "preview":
        cmd_preview(target)
    else:
        print_help()
