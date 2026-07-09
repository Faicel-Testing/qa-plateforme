# ============================================================
# Codegen Agent — Génération de code Java API RestAssured
# ============================================================
# Commandes :
#   python agents/codegen-agent.py feature <nom> <endpoint>  → .feature Gherkin
#   python agents/codegen-agent.py steps <feature>            → step definitions Java
#   python agents/codegen-agent.py client <nom> <endpoint>    → Client Java (RestAssured)
#   python agents/codegen-agent.py list                       → features existantes
# ============================================================
# Application : restful-booker.herokuapp.com — 8 features / 51 scénarios
# ============================================================

import sys, os, re, argparse
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm
from prompt_store import PromptStore

_ps = PromptStore()

FRAMEWORK    = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FEATURES_DIR = os.path.join(FRAMEWORK, "src", "test", "resources", "features")
STEPS_DIR    = os.path.join(FRAMEWORK, "src", "test", "java", "com", "restfulbooker", "steps")
CLIENT_DIR   = os.path.join(FRAMEWORK, "src", "main", "java", "com", "restfulbooker", "client")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

PACKAGE_STEPS  = "com.restfulbooker.steps"
PACKAGE_CLIENT = "com.restfulbooker.client"


def _fmt_simple(template: str, **kw) -> str:
    result = template
    for k, v in kw.items():
        result = result.replace("{" + k + "}", str(v))
    return result


def _write_file(path: str, content: str, label: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        print(f"  {Y}[WARN] Fichier existant : {label} — écrasé{E}")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  {G}✓ Généré : {label}{E}")


# ── Génération feature ─────────────────────────────────────────────────────────

def cmd_feature(name: str, endpoint: str):
    _tpl = _ps.get("tc_generate") or (
        "Génère un fichier Gherkin (.feature) complet pour ce cas de test API :\n\n"
        "Nom      : {name}\n"
        "Endpoint : {endpoint}\n"
        "Application : restful-booker.herokuapp.com\n\n"
        "Génère un Feature file Gherkin propre (en français, style de la suite existante) avec :\n"
        "- Feature et Background (\"Given l'API est disponible\")\n"
        "- Scénarios avec tags appropriés (@smoke, @critical, @positif, @negatif, @securite)\n"
        "- Steps Given/When/Then bien rédigés\n"
        "Réponds UNIQUEMENT avec le contenu du fichier .feature (pas de markdown)."
    )
    messages = [{"role": "user", "content": _fmt_simple(_tpl, name=name, endpoint=endpoint)}]
    print(f"  {C}Génération feature : {name} ({endpoint})...{E}", flush=True)
    try:
        content = llm.chat(messages)
        _ps.record_usage("tc_generate")
        filename = f"{re.sub(r'[^a-zA-Z0-9_]', '_', name.lower())}.feature"
        path = os.path.join(FEATURES_DIR, filename)
        _write_file(path, content.strip(), filename)
        return path
    except Exception as ex:
        print(f"  {R}LLM erreur : {ex}{E}")
        return None


# ── Génération steps Java ──────────────────────────────────────────────────────

def cmd_steps(feature_file: str):
    if not os.path.exists(feature_file):
        feature_file = os.path.join(FEATURES_DIR, feature_file)
    if not os.path.exists(feature_file):
        print(f"  {R}Feature introuvable : {feature_file}{E}")
        return
    with open(feature_file, encoding="utf-8") as f:
        feature_content = f.read()
    class_name = re.sub(r'[^a-zA-Z0-9]', '', os.path.basename(feature_file).replace(".feature", "").title()) + "Steps"

    messages = [{"role": "user", "content": (
        f"Génère les Step Definitions Java pour ce fichier Gherkin :\n\n"
        f"```gherkin\n{feature_content}\n```\n\n"
        f"Contraintes :\n"
        f"- Package : {PACKAGE_STEPS}\n"
        f"- Classe : {class_name}\n"
        f"- Framework : RestAssured + Cucumber 7 + TestNG\n"
        f"- État partagé via un ScenarioContext injecté par constructeur (cucumber-picocontainer)\n"
        f"- Utilise les annotations @Given, @When, @Then de io.cucumber.java.en\n"
        f"- Steps contenant des accolades littérales ({{}}, {{\"x\": 1}}) ou {{id}} DOIVENT utiliser "
        f"la forme regex ancrée ^...$ avec échappement \\\\{{ \\\\}}, pas une Cucumber Expression\n"
        f"- Assertions via org.testng.Assert\n"
        f"Réponds UNIQUEMENT avec le code Java (pas de markdown)."
    )}]
    print(f"  {C}Génération steps Java pour {os.path.basename(feature_file)}...{E}", flush=True)
    try:
        content = llm.chat(messages)
        path = os.path.join(STEPS_DIR, f"{class_name}.java")
        _write_file(path, content.strip(), f"{class_name}.java")
        return path
    except Exception as ex:
        print(f"  {R}LLM erreur : {ex}{E}")
        return None


# ── Génération Client Java (RestAssured) ───────────────────────────────────────

def cmd_client(name: str, endpoint: str = "/"):
    class_name = name.replace(" ", "").replace("-", "") + "Client"
    messages = [{"role": "user", "content": (
        f"Génère un client API Java (RestAssured) pour l'endpoint '{endpoint}' de restful-booker.herokuapp.com\n\n"
        f"Contraintes :\n"
        f"- Package : {PACKAGE_CLIENT}\n"
        f"- Classe : {class_name} extends BaseApiClient\n"
        f"- Utilise les méthodes protégées get/post/put/patch/delete héritées de BaseApiClient\n"
        f"- Retourne des io.restassured.response.Response\n"
        f"- Imports nécessaires inclus\n"
        f"Réponds UNIQUEMENT avec le code Java (pas de markdown)."
    )}]
    print(f"  {C}Génération Client : {class_name}...{E}", flush=True)
    try:
        content = llm.chat(messages)
        path = os.path.join(CLIENT_DIR, f"{class_name}.java")
        _write_file(path, content.strip(), f"{class_name}.java")
        return path
    except Exception as ex:
        print(f"  {R}LLM erreur : {ex}{E}")
        return None


def cmd_list():
    print(f"\n{W}CODEGEN — Features existantes — restful-booker.herokuapp.com{E}\n")
    for f in sorted(glob_features()):
        print(f"  [✓] {os.path.basename(f)}")


def glob_features():
    import glob
    return glob.glob(os.path.join(FEATURES_DIR, "*.feature"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Codegen Agent — API RestAssured Java")
    parser.add_argument("command", choices=["feature", "steps", "client", "list"])
    parser.add_argument("name", nargs="?", default=None)
    parser.add_argument("endpoint", nargs="?", default="/")
    args = parser.parse_args()

    if args.command == "list":
        cmd_list()
    elif args.command == "feature":
        if args.name:
            cmd_feature(args.name, args.endpoint)
        else:
            print(f"  {R}Usage: codegen-agent.py feature <nom> <endpoint>{E}")
    elif args.command == "steps":
        if args.name:
            cmd_steps(args.name)
        else:
            print(f"  {R}Usage: codegen-agent.py steps <feature.feature>{E}")
    elif args.command == "client":
        if args.name:
            cmd_client(args.name, args.endpoint)
        else:
            print(f"  {R}Usage: codegen-agent.py client <nom> <endpoint>{E}")
