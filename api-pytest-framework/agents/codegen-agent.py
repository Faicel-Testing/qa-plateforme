# ============================================================
# Codegen Agent — Spécification · Génération · Couverture
# ============================================================
# Absorbe : api-spec-agent · api-generate-agent · tc-generator-agent · coverage-agent
#
# Commandes :
#   python agents/codegen-agent.py spec [--file=specs/booking-api.md]  → analyse une spec
#   python agents/codegen-agent.py generate                             → génère les test_*.py
#   python agents/codegen-agent.py tc US-001                           → génère les TCs d'une US
#   python agents/codegen-agent.py coverage                            → analyse lacunes couverture
#   python agents/codegen-agent.py full [--file=specs/booking-api.md]  → spec + generate + coverage
# ============================================================

import sys, os, json, glob, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm
from jira_fetcher_agent import JiraClient

FRAMEWORK    = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SPECS_DIR    = os.path.join(FRAMEWORK, "specs")
FEATURES_DIR = os.path.join(FRAMEWORK, "features")
TESTS_DIR    = os.path.join(FRAMEWORK, "tests")
STEPS_DIR    = os.path.join(FEATURES_DIR, "steps")
DOCS_DIR     = os.path.join(FRAMEWORK, "docs")
SPEC_OUTPUT  = os.path.join(DOCS_DIR, "spec-output.json")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

# Marqueurs BDD connus de la plateforme
KNOWN_MARKERS = ["smoke", "critical", "regression", "flaky", "auth", "booking",
                 "health", "positif", "negatif", "securite", "limite", "performance"]

# Schéma Structured Output pour les TCs
TC_SCHEMA = {
    "type": "object",
    "properties": {
        "test_cases": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tc_id":       {"type": "string", "description": "ex: tc-001"},
                    "title":       {"type": "string"},
                    "description": {"type": "string"},
                    "markers":     {"type": "array", "items": {"type": "string"}},
                    "steps":       {"type": "array", "items": {"type": "string"}},
                    "expected":    {"type": "string"},
                    "us_id":       {"type": "string", "description": "ex: us-001"},
                    "endpoint":    {"type": "string"},
                    "method":      {"type": "string", "enum": ["GET","POST","PUT","PATCH","DELETE"]},
                    "status_code": {"type": "integer"},
                    "test_type":   {"type": "string", "enum": ["positif","negatif","securite","limite","performance"]}
                },
                "required": ["tc_id","title","markers","expected","us_id","endpoint","method","status_code","test_type"]
            }
        }
    },
    "required": ["test_cases"]
}

# Schéma Structured Output pour la spec
SPEC_SCHEMA = {
    "type": "object",
    "properties": {
        "api_name":    {"type": "string"},
        "base_url":    {"type": "string"},
        "endpoints": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "us_id":       {"type": "string"},
                    "method":      {"type": "string"},
                    "path":        {"type": "string"},
                    "description": {"type": "string"},
                    "auth":        {"type": "boolean"},
                    "request_body": {"type": "object"},
                    "response_codes": {"type": "array", "items": {"type": "integer"}}
                },
                "required": ["us_id","method","path","description","auth","response_codes"]
            }
        }
    },
    "required": ["api_name","base_url","endpoints"]
}


# ── Spec — Analyse de la spécification API ─────────────────────────────────

def read_spec_file(file_path: str) -> str:
    if not os.path.exists(file_path):
        # Chercher dans specs/
        candidates = glob.glob(os.path.join(SPECS_DIR, "*.md")) + glob.glob(os.path.join(SPECS_DIR, "*.yaml"))
        if candidates:
            file_path = candidates[0]
            print(f"{Y}  [INFO] Spec trouvee : {file_path}{E}")
        else:
            raise FileNotFoundError(f"Aucune spec trouvee dans {SPECS_DIR}/")
    with open(file_path, encoding="utf-8") as f:
        return f.read()


def cmd_spec(file_path: str = None) -> dict:
    print(f"\n{W}CODEGEN AGENT — Spec Analyzer{E}\n")
    if not file_path:
        candidates = glob.glob(os.path.join(SPECS_DIR, "*.md")) + glob.glob(os.path.join(SPECS_DIR, "*.yaml"))
        file_path = candidates[0] if candidates else None

    if not file_path or not os.path.exists(file_path):
        print(f"{R}  [ERR] Aucun fichier de spec. Créez specs/votre-api.md{E}")
        return {}

    spec_text = open(file_path, encoding="utf-8").read()
    print(f"  Analyse de : {os.path.basename(file_path)} ({len(spec_text)} chars)")

    messages = [{"role": "user", "content": (
        f"Analyse cette specification API et extrait les endpoints avec leurs details :\n\n{spec_text[:4000]}"
    )}]
    result = llm.chat_structured(messages, SPEC_SCHEMA)

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(SPEC_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    endpoints = result.get("endpoints", [])
    print(f"\n{G}  API : {result.get('api_name','?')} | Base URL : {result.get('base_url','?')}{E}")
    print(f"  {len(endpoints)} endpoint(s) extracte(s) -> docs/spec-output.json")
    for ep in endpoints:
        print(f"  {C}{ep.get('method','?'):7}{E} {ep.get('path','?'):<35} [{ep.get('us_id','?')}]")

    return result


# ── Generate — Génération des fichiers test_*.py ──────────────────────────

def load_spec_output() -> dict:
    if not os.path.exists(SPEC_OUTPUT):
        raise FileNotFoundError(f"docs/spec-output.json introuvable. Lancez d'abord : codegen-agent.py spec")
    with open(SPEC_OUTPUT, encoding="utf-8") as f:
        return json.load(f)


def generate_test_file(endpoint: dict, api_name: str, base_url: str) -> str:
    us_id  = endpoint.get("us_id", "us-000")
    method = endpoint.get("method", "GET")
    path   = endpoint.get("path", "/")
    desc   = endpoint.get("description", "")
    auth   = endpoint.get("auth", False)
    codes  = endpoint.get("response_codes", [200])

    messages = [{"role": "user", "content": (
        f"Génère un fichier pytest BDD pour cet endpoint API.\n\n"
        f"API     : {api_name}\n"
        f"Base URL: {base_url}\n"
        f"US      : {us_id}\n"
        f"Methode : {method} {path}\n"
        f"Auth    : {'Oui (token Bearer)' if auth else 'Non'}\n"
        f"Codes   : {codes}\n"
        f"Desc    : {desc}\n\n"
        f"Le fichier doit :\n"
        f"- Etre un fichier pytest standard (pas BDD Gherkin)\n"
        f"- Importer requests, pytest, conftest\n"
        f"- Inclure des marqueurs pytest : @pytest.mark.smoke, @pytest.mark.{us_id}\n"
        f"- Tester les codes HTTP attendus : {codes}\n"
        f"- Inclure au moins un test positif et un test negatif\n"
        f"- Utiliser des fixtures conftest (base_url, auth_token si besoin)\n"
        f"- Nommer le fichier : test_{us_id.replace('-','_')}_bdd.py\n\n"
        f"Retourne UNIQUEMENT le code Python, sans explication."
    )}]
    return llm.chat(messages)


def cmd_generate():
    print(f"\n{W}CODEGEN AGENT — Generate Tests{E}\n")
    try:
        spec = load_spec_output()
    except FileNotFoundError as e:
        print(f"{R}  [ERR] {e}{E}")
        return

    api_name = spec.get("api_name", "API")
    base_url = spec.get("base_url", "")
    endpoints = spec.get("endpoints", [])
    os.makedirs(TESTS_DIR, exist_ok=True)

    generated = []
    for i, ep in enumerate(endpoints, 1):
        us_id = ep.get("us_id", f"us-{i:03d}")
        filename = f"test_{us_id.replace('-','_')}_bdd.py"
        filepath = os.path.join(TESTS_DIR, filename)

        print(f"  {C}[{i}/{len(endpoints)}]{E} Generation : {filename}...", end=" ", flush=True)
        code = generate_test_file(ep, api_name, base_url)

        # Nettoyer les balises markdown si LLM les inclut
        code = re.sub(r"^```(?:python)?\s*", "", code, flags=re.MULTILINE)
        code = re.sub(r"\s*```$", "", code, flags=re.MULTILINE)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code.strip() + "\n")

        generated.append(filename)
        print(f"{G}OK{E}")

    print(f"\n{G}  {len(generated)} fichier(s) genere(s) dans tests/{E}")
    for name in generated:
        print(f"  {G}✓{E} {name}")


# ── TC — Génération de cas de test structurés ─────────────────────────────

def cmd_tc(us_id: str):
    print(f"\n{W}CODEGEN AGENT — TC Generator ({us_id}){E}\n")
    jira = JiraClient()

    # Essayer de récupérer la US depuis Jira
    issue = jira.get_issue(us_id.upper())
    if issue:
        summary  = issue.get("fields", {}).get("summary", "")
        desc_raw = issue.get("fields", {}).get("description", {})
        if isinstance(desc_raw, dict):
            desc = " ".join(
                block.get("text", "")
                for content in desc_raw.get("content", [])
                for block in content.get("content", [])
                if isinstance(block, dict)
            )
        else:
            desc = str(desc_raw)
        context = f"User Story Jira — {us_id.upper()}\nTitre : {summary}\nDescription : {desc[:1000]}"
        print(f"  {G}[JIRA]{E} {us_id.upper()} : {summary[:60]}")
    else:
        context = f"User Story : {us_id.upper()} — API REST Hotel Booking"
        print(f"  {Y}[LOCAL]{E} Jira inaccessible, génération sans contexte Jira")

    messages = [{"role": "user", "content": (
        f"Génère des cas de test BDD exhaustifs pour cette user story :\n\n{context}\n\n"
        f"Inclure : tests positifs, négatifs, sécurité, limites.\n"
        f"Marqueurs disponibles : {KNOWN_MARKERS}\n"
        f"Pour chaque TC, assigne un tc_id unique (tc-001, tc-002...) et le us_id={us_id.lower()}"
    )}]
    result = llm.chat_structured(messages, TC_SCHEMA)

    test_cases = result.get("test_cases", [])
    print(f"\n  {len(test_cases)} TC(s) genere(s) pour {us_id.upper()}")

    output_file = os.path.join(DOCS_DIR, f"tc-{us_id.lower()}.json")
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    for tc in test_cases:
        markers = ", ".join(tc.get("markers", []))
        print(f"  {C}{tc.get('tc_id','?')}{E}  [{tc.get('test_type','?'):12}]  "
              f"{tc.get('title','')[:50]}  {Y}[{markers}]{E}")

    print(f"\n  {G}Sauvegarde : docs/tc-{us_id.lower()}.json{E}")
    return test_cases


# ── Coverage — Analyse des lacunes ────────────────────────────────────────

def load_existing_features() -> list:
    features = []
    for fpath in glob.glob(os.path.join(FEATURES_DIR, "*.feature")):
        try:
            content = open(fpath, encoding="utf-8").read()
            scenarios = re.findall(r"Scenario(?:\s+Outline)?:\s*(.+)", content)
            tags      = re.findall(r"@(\w[\w-]*)", content)
            endpoints = re.findall(r"(GET|POST|PUT|PATCH|DELETE)\s+(/[\w/{}]+)", content)
            features.append({
                "file":      os.path.basename(fpath),
                "scenarios": scenarios,
                "tags":      list(set(tags)),
                "endpoints": endpoints,
            })
        except Exception:
            pass
    return features


def cmd_coverage():
    print(f"\n{W}CODEGEN AGENT — Coverage Analysis{E}\n")
    features = load_existing_features()

    if not features:
        print(f"{Y}  [WARN] Aucun fichier .feature dans features/. Rien a analyser.{E}")
        return

    total_scenarios = sum(len(f["scenarios"]) for f in features)
    all_tags        = [tag for f in features for tag in f["tags"]]
    smoke_count     = all_tags.count("smoke")
    critical_count  = all_tags.count("critical")
    negative_count  = all_tags.count("negatif")

    print(f"  {len(features)} feature(s)  |  {total_scenarios} scenarios  |  "
          f"@smoke:{smoke_count}  @critical:{critical_count}  @negatif:{negative_count}")

    # Analyse CoT des lacunes
    features_summary = json.dumps([{
        "file": f["file"],
        "nb_scenarios": len(f["scenarios"]),
        "tags": f["tags"][:10],
    } for f in features], ensure_ascii=False)

    messages = [{"role": "user", "content": (
        f"Analyse la couverture de tests de cette suite API BDD et identifie les lacunes :\n\n"
        f"{features_summary}\n\n"
        f"Identifie :\n"
        f"1. Les types de tests manquants (securite, performance, limites...)\n"
        f"2. Les endpoints probablement non couverts\n"
        f"3. Les tags sous-representés (@negatif, @securite, @limite)\n"
        f"4. Les 3 nouveaux TCs les plus prioritaires a creer\n\n"
        f"Soit concis et actionnable."
    )}]
    analysis = llm.chat_cot(messages)

    print(f"\n{W}  Analyse des lacunes (CoT) :{E}")
    for line in analysis.strip().split("\n"):
        if re.match(r"\s*ÉTAPE\s*\d", line, re.IGNORECASE):
            print(f"  {Y}{line}{E}")
        elif re.match(r"\s*CONCLUSION", line, re.IGNORECASE):
            print(f"  {G}{line}{E}")
        elif line.strip():
            print(f"  {line}")

    # Sauvegarder le rapport
    report = {
        "total_features": len(features),
        "total_scenarios": total_scenarios,
        "coverage_by_tag": {
            "smoke": smoke_count,
            "critical": critical_count,
            "negatif": negative_count,
        },
        "analysis": analysis,
    }
    out = os.path.join(DOCS_DIR, "coverage-report.json")
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n{G}  Rapport : docs/coverage-report.json{E}")


def cmd_full(file_path: str = None):
    print(f"\n{W}CODEGEN AGENT — Full Pipeline{E}")
    print(f"{Y}  spec → generate → coverage{E}\n")
    spec = cmd_spec(file_path)
    if spec:
        cmd_generate()
    cmd_coverage()


# ── Main ───────────────────────────────────────────────────────────────────

def print_help():
    print(f"""
{W}CODEGEN AGENT — Spécification · Génération · Couverture{E}

  python agents/codegen-agent.py spec                     Analyse une spec API (docs/spec-output.json)
  python agents/codegen-agent.py spec --file=specs/X.md  Spec depuis un fichier specifique
  python agents/codegen-agent.py generate                 Génère les test_*.py depuis spec-output.json
  python agents/codegen-agent.py tc US-001               Génère les TCs structures d'une US
  python agents/codegen-agent.py coverage                 Analyse les lacunes de couverture (CoT)
  python agents/codegen-agent.py full                     Pipeline complet spec + generate + coverage

{W}Modules absorbes :{E} api-spec-agent · api-generate-agent · tc-generator-agent · coverage-agent
""")


if __name__ == "__main__":
    file_arg = next((a.split("=")[1] for a in sys.argv if a.startswith("--file=")), None)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "spec":
        cmd_spec(file_arg)
    elif cmd == "generate":
        cmd_generate()
    elif cmd == "tc":
        us = sys.argv[2] if len(sys.argv) > 2 else "US-001"
        cmd_tc(us)
    elif cmd == "coverage":
        cmd_coverage()
    elif cmd == "full":
        cmd_full(file_arg)
    else:
        print_help()
