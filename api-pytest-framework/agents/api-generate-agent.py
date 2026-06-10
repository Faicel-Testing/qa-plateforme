# ============================================
# API Generate Agent — Génère les fichiers test_*_bdd.py
# ============================================
# Rôle unique : lire docs/spec-output.json (produit par api-spec-agent)
# et générer les fichiers test_*.py correspondants dans tests/.
#
# Usage:
#   python agents/api-generate-agent.py             → génère depuis features/
#   python agents/api-generate-agent.py --input=docs/spec-output.json
#   python agents/api-generate-agent.py --dry-run   → affiche sans écrire
#
# Output:
#   tests/test_<endpoint>_bdd.py  ←  un fichier par feature
# ============================================

import sys, os, json, glob, re, argparse
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm

FRAMEWORK    = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FEATURES_DIR = os.path.join(FRAMEWORK, "features")
STEPS_DIR    = os.path.join(FEATURES_DIR, "steps")
TESTS_DIR    = os.path.join(FRAMEWORK, "tests")
SPEC_FILE    = os.path.join(FRAMEWORK, "docs", "spec-output.json")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

# ── Schéma Structured Output ───────────────────────────────────────────────
# Le LLM DOIT retourner exactement ce format — aucun parsing fragile.

GENERATE_SCHEMA = {
    "type": "object",
    "properties": {
        "test_files": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "filename":     {"type": "string",  "description": "ex: test_booking_bdd.py"},
                    "feature_file": {"type": "string",  "description": "ex: booking.feature"},
                    "us_id":        {"type": "string",  "description": "ex: US-002"},
                    "method":       {"type": "string",  "description": "ex: GET"},
                    "path":         {"type": "string",  "description": "ex: /booking"},
                    "description":  {"type": "string",  "description": "Description courte de l'endpoint"},
                    "steps_modules":{"type": "array",   "items": {"type": "string"},
                                     "description": "Modules steps à importer ex: ['common_steps', 'booking_steps']"}
                },
                "required": ["filename", "feature_file", "us_id", "method", "path", "description", "steps_modules"]
            }
        }
    },
    "required": ["test_files"]
}


# ── Lecture des sources ────────────────────────────────────────────────────

def load_from_spec(spec_path: str) -> list:
    """Charge les user stories depuis spec-output.json."""
    with open(spec_path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("user_stories", data) if isinstance(data, dict) else data


def load_from_features() -> list:
    """
    Fallback : scanne features/*.feature directement.
    Extrait feature_file, feature_name, us_id, tags depuis chaque fichier.
    """
    features = []
    for fpath in sorted(glob.glob(os.path.join(FEATURES_DIR, "*.feature"))):
        fname   = os.path.basename(fpath)
        content = open(fpath, encoding="utf-8").read()

        feature_match = re.search(r"Feature:\s*(.+)", content)
        us_match      = re.search(r"US-[A-Z]*-?(\d+)|US-(\d+)", content, re.IGNORECASE)
        method_match  = re.search(r"\b(GET|POST|PUT|PATCH|DELETE)\b", content)
        path_match    = re.search(r"(/\w[/\w{}\-]*)", content)

        features.append({
            "feature_file":   fname,
            "feature_name":   feature_match.group(1).strip() if feature_match else fname,
            "us_id":          us_match.group(0).upper() if us_match else "US-???",
            "method":         method_match.group(1) if method_match else "GET",
            "path":           path_match.group(1) if path_match else "/",
            "content_sample": content[:600],
        })
    return features


def list_steps_modules() -> list:
    """Liste les modules steps disponibles dans features/steps/."""
    modules = []
    for f in sorted(glob.glob(os.path.join(STEPS_DIR, "*_steps.py"))):
        name = os.path.basename(f).replace(".py", "")
        if not name.startswith("__"):
            modules.append(name)
    return modules


# ── Appel LLM avec Structured Output ──────────────────────────────────────

def plan_test_files(features: list, steps_modules: list) -> list:
    """
    Demande au LLM (via Structured Output) de planifier les fichiers
    test_*_bdd.py à générer, avec les bons imports steps.
    """
    features_summary = "\n".join([
        f"- {f['feature_file']} | {f.get('us_id','?')} | {f.get('method','?')} {f.get('path','?')} | {f.get('feature_name', f['feature_file'])}"
        for f in features
    ])
    steps_list = ", ".join(steps_modules)

    messages = [{
        "role": "user",
        "content": (
            f"Voici les fichiers .feature du framework pytest-bdd :\n{features_summary}\n\n"
            f"Modules steps disponibles : {steps_list}\n\n"
            f"Pour chaque feature, génère un fichier test_*_bdd.py avec :\n"
            f"- filename : test_<nom>_bdd.py (basé sur le nom du .feature)\n"
            f"- feature_file : nom exact du .feature\n"
            f"- us_id : l'ID user story extrait de la feature\n"
            f"- method : méthode HTTP principale (GET/POST/PUT/PATCH/DELETE)\n"
            f"- path : chemin de l'endpoint principal\n"
            f"- description : description courte (5 mots max)\n"
            f"- steps_modules : liste des modules steps à importer\n"
            f"  Règle : toujours inclure 'common_steps', puis le module spécifique\n"
            f"  qui correspond au nom de la feature (ex: booking.feature → booking_steps)\n"
            f"  N'inclus que des modules qui existent dans la liste fournie.\n"
        )
    }]

    print(f"{C}  Appel LLM Structured Output — planification des fichiers...{E}", flush=True)
    result = llm.chat_structured(messages, GENERATE_SCHEMA)
    return result.get("test_files", [])


# ── Génération du contenu Python ───────────────────────────────────────────

def render_test_file(tf: dict) -> str:
    """Génère le contenu Python du fichier test_*_bdd.py."""
    imports = "\n".join([f"from steps.{m} import *" for m in tf["steps_modules"]])
    return (
        f'"""{tf["us_id"]} -- {tf["method"]} {tf["path"]} -- {tf["description"]}"""\n'
        f"from pytest_bdd import scenarios\n"
        f"{imports}\n"
        f"\n"
        f'scenarios("{tf["feature_file"]}")\n'
    )


# ── Affichage ──────────────────────────────────────────────────────────────

def print_plan(test_files: list):
    print(f"\n  {'Fichier généré':<35} {'Feature':<30} {'US':>8} {'Steps modules'}")
    print(f"  {'-'*90}")
    for tf in test_files:
        modules = ", ".join(tf["steps_modules"])
        print(f"  {G}{tf['filename']:<35}{E} {C}{tf['feature_file']:<30}{E} {Y}{tf['us_id']:>8}{E} {modules}")


# ── Commandes ──────────────────────────────────────────────────────────────

def run(spec_path: str = None, dry_run: bool = False):
    print(f"\n{W}API GENERATE AGENT — Structured Output{E}")

    # 1. Charger les sources
    if spec_path and os.path.exists(spec_path):
        print(f"{C}  Source : {spec_path}{E}")
        features = load_from_spec(spec_path)
    else:
        if spec_path:
            print(f"{Y}  {spec_path} introuvable — fallback sur features/*.feature{E}")
        else:
            print(f"{C}  Source : features/*.feature{E}")
        features = load_from_features()

    if not features:
        print(f"{R}  Aucune feature trouvée.{E}")
        return

    print(f"  {len(features)} feature(s) détectée(s)")

    # 2. Lister les modules steps disponibles
    steps_modules = list_steps_modules()
    print(f"  Modules steps : {', '.join(steps_modules)}")

    # 3. LLM planifie les fichiers (Structured Output)
    test_files = plan_test_files(features, steps_modules)

    if not test_files:
        print(f"{R}  LLM n'a retourné aucun fichier à générer.{E}")
        return

    print_plan(test_files)

    # 4. Générer les fichiers
    created = 0
    skipped = 0
    for tf in test_files:
        out_path = os.path.join(TESTS_DIR, tf["filename"])
        content  = render_test_file(tf)

        if dry_run:
            print(f"\n{Y}  [DRY-RUN] {tf['filename']}{E}")
            print(f"{C}{content}{E}")
            continue

        # Ne pas écraser un fichier existant avec du contenu différent
        if os.path.exists(out_path):
            existing = open(out_path, encoding="utf-8").read()
            if existing.strip() == content.strip():
                print(f"  {Y}={E}  {tf['filename']} (identique, ignoré)")
                skipped += 1
                continue

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  {G}✓{E}  {tf['filename']}")
        created += 1

    if not dry_run:
        print(f"\n  {G}{created} fichier(s) créé(s){E} | {Y}{skipped} ignoré(s) (déjà à jour){E}")


# ── Main ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="API Generate Agent")
    parser.add_argument("--input",   default=None,  help="Chemin vers spec-output.json")
    parser.add_argument("--dry-run", action="store_true", help="Affiche sans écrire")
    args = parser.parse_args()

    run(spec_path=args.input or SPEC_FILE, dry_run=args.dry_run)
