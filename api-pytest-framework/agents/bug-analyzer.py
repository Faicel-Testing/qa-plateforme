# ============================================================
# Bug Analyzer — Diagnostic + Réparation automatique des tests
# ============================================================
# Complémentaire à rca-agent.py :
#   rca-agent    → DIAGNOSTIC  (chaîne causale, groupement, rapport)
#   bug-analyzer → RÉPARATION  (patch automatique dans les fichiers)
#
# Techniques :
#   Chain of Thought  → comprendre l'échec avant de proposer un fix
#   Structured Output → patch structuré (fichier, old_code, new_code)
#   Confidence Score  → safe_to_autofix=false si LLM n'est pas sûr
#
# Usage:
#   python agents/bug-analyzer.py                → affiche les correctifs
#   python agents/bug-analyzer.py --dry-run      → montre le diff sans écrire
#   python agents/bug-analyzer.py --apply        → applique les correctifs
#   python agents/bug-analyzer.py --apply TC-023 → applique un seul TC
# ============================================================

import sys, os, json, glob, re, shutil, argparse, difflib
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm

FRAMEWORK   = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS_DIR = os.path.join(FRAMEWORK, "allure-results")
STEPS_DIR   = os.path.join(FRAMEWORK, "features", "steps")
TESTS_DIR   = os.path.join(FRAMEWORK, "tests")
FEATURES_DIR = os.path.join(FRAMEWORK, "features")
BACKUP_DIR  = os.path.join(FRAMEWORK, "docs", "bug-analyzer-backups")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

# ── Schéma Structured Output pour le patch ───────────────────────────────
# safe_to_autofix=false → le bug-analyzer refuse d'appliquer sans confirmation

PATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "root_cause":       {"type": "string",  "description": "Cause racine en 1 phrase"},
        "fix_description":  {"type": "string",  "description": "Ce que le patch corrige"},
        "fix_type":         {"type": "string",  "enum": ["assertion", "fixture", "step", "config", "data", "feature", "none"]},
        "file_to_fix":      {"type": "string",  "description": "Chemin relatif depuis la racine du framework, ex: features/steps/booking_steps.py"},
        "old_code":         {"type": "string",  "description": "Bloc de code exact à remplacer (doit exister tel quel dans le fichier)"},
        "new_code":         {"type": "string",  "description": "Code de remplacement corrigé"},
        "confidence":       {"type": "number",  "description": "0.0 à 1.0 — certitude du fix"},
        "safe_to_autofix":  {"type": "boolean", "description": "true si le patch est sûr à appliquer automatiquement"},
        "warning":          {"type": "string",  "description": "Message si safe_to_autofix=false"}
    },
    "required": ["root_cause", "fix_description", "fix_type", "file_to_fix",
                 "old_code", "new_code", "confidence", "safe_to_autofix"]
}


# ── Chargement des fichiers sources disponibles ───────────────────────────

def _build_source_index() -> dict:
    """Index {chemin_relatif: contenu} de tous les fichiers Python du framework."""
    index = {}
    patterns = [
        os.path.join(STEPS_DIR,  "*.py"),
        os.path.join(TESTS_DIR,  "*.py"),
        os.path.join(FEATURES_DIR, "*.feature"),
    ]
    for pattern in patterns:
        for fpath in glob.glob(pattern):
            rel = os.path.relpath(fpath, FRAMEWORK).replace("\\", "/")
            try:
                index[rel] = open(fpath, encoding="utf-8").read()
            except Exception:
                pass
    return index


# ── Chargement des échecs Allure ───────────────────────────────────────────

def load_failures(tc_filter: str = None) -> list:
    failures = []
    for f in glob.glob(os.path.join(RESULTS_DIR, "*-result.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
            if d.get("status") not in ("failed", "broken"):
                continue

            tags   = [lb["value"] for lb in d.get("labels", []) if lb["name"] == "tag"]
            tc     = next((t for t in tags if re.match(r"tc-\d+", t)), None)
            suite  = next((lb["value"] for lb in d.get("labels", []) if lb["name"] == "suite"), "?")
            detail = d.get("statusDetails") or {}

            if tc_filter and tc and tc_filter.lower() != tc.lower():
                continue

            failures.append({
                "name":    d.get("name", "?"),
                "status":  d.get("status"),
                "tc":      tc,
                "suite":   suite,
                "message": detail.get("message", "")[:500],
                "trace":   detail.get("trace",   "")[:800],
            })
        except Exception:
            pass
    return failures


# ── Analyse CoT + génération du patch Structured Output ───────────────────

def analyze_and_patch(failure: dict, source_index: dict) -> dict:
    """
    Phase 1 — CoT : comprend l'échec et identifie le fichier à corriger.
    Phase 2 — Structured Output : génère le patch précis (old_code / new_code).
    """
    # Trouver le fichier steps lié à la suite du test
    suite_name  = failure.get("suite", "")
    likely_step = re.sub(r"test_(.+)_bdd", r"\1_steps", suite_name)
    likely_file = f"features/steps/{likely_step}.py"
    file_content = source_index.get(likely_file, "")

    # Fallback : chercher dans tous les steps
    if not file_content:
        for rel, content in source_index.items():
            if failure.get("tc", "").lower() in content.lower() or \
               (likely_step.replace("_steps", "") in rel and rel.endswith(".py")):
                likely_file  = rel
                file_content = content
                break

    # ── Phase 1 : Chain of Thought ─────────────────────────────────────
    cot_messages = [{
        "role": "user",
        "content": (
            f"Analyse cet échec de test API et prépare un correctif :\n\n"
            f"Test    : {failure['name']}\n"
            f"TC      : {failure.get('tc','?')} | Suite : {failure['suite']}\n"
            f"Statut  : {failure['status']}\n"
            f"Erreur  : {failure['message'] or 'aucun message'}\n"
            f"Trace   :\n{failure['trace'][:500] or 'aucune trace'}\n\n"
            f"Fichier source probable ({likely_file}) :\n"
            f"```python\n{file_content[:1200]}\n```\n\n"
            f"Fichiers disponibles : {list(source_index.keys())}"
        )
    }]
    cot_reasoning = llm.chat_cot(cot_messages)

    # ── Phase 2 : Structured Output (patch précis) ─────────────────────
    patch_messages = [{
        "role": "user",
        "content": (
            f"Sur la base de cette analyse :\n{cot_reasoning}\n\n"
            f"Génère le patch structuré.\n"
            f"RÈGLES CRITIQUES pour old_code / new_code :\n"
            f"- old_code DOIT être un extrait exact du fichier source\n"
            f"- Copie le code mot pour mot depuis le fichier, ne l'invente pas\n"
            f"- Si tu n'es pas certain du code exact → safe_to_autofix=false\n"
            f"- file_to_fix = chemin relatif depuis la racine (ex: features/steps/booking_steps.py)\n"
            f"- fix_type='none' si le bug est dans l'API et non dans les tests\n"
        )
    }]
    patch = llm.chat_structured(patch_messages, PATCH_SCHEMA)
    patch["cot_reasoning"] = cot_reasoning
    patch["failure"]       = failure
    return patch


# ── Affichage du diff ──────────────────────────────────────────────────────

def print_diff(old_code: str, new_code: str):
    old_lines = old_code.splitlines(keepends=True)
    new_lines = new_code.splitlines(keepends=True)
    diff = list(difflib.unified_diff(old_lines, new_lines,
                                      fromfile="avant", tofile="après", lineterm=""))
    for line in diff:
        if line.startswith("+") and not line.startswith("+++"):
            print(f"  {G}{line.rstrip()}{E}")
        elif line.startswith("-") and not line.startswith("---"):
            print(f"  {R}{line.rstrip()}{E}")
        elif line.startswith("@@"):
            print(f"  {C}{line.rstrip()}{E}")
        else:
            print(f"  {line.rstrip()}")


def print_patch(p: dict, show_diff: bool = True):
    f = p.get("failure", {})
    conf = p.get("confidence", 0)
    safe = p.get("safe_to_autofix", False)

    conf_color = G if conf >= 0.8 else Y if conf >= 0.6 else R
    safe_label = f"{G}✓ AUTO-APPLICABLE{E}" if safe else f"{R}⚠ RÉVISION REQUISE{E}"

    print(f"\n  {W}{'─'*54}{E}")
    print(f"  {W}{f.get('tc','?'):>8}{E}  {f.get('name','')[:50]}")
    print(f"  {R}Cause :{E} {p.get('root_cause','')}")
    print(f"  {G}Fix   :{E} {p.get('fix_description','')}")
    print(f"  Fichier    : {C}{p.get('file_to_fix','?')}{E}")
    print(f"  Type       : {p.get('fix_type','?')}  |  "
          f"Confiance : {conf_color}{int(conf*100)}%{E}  |  {safe_label}")

    if p.get("warning"):
        print(f"  {Y}⚠ {p['warning']}{E}")

    if show_diff and p.get("old_code") and p.get("new_code"):
        print(f"\n  {W}Diff :{E}")
        print_diff(p["old_code"], p["new_code"])


# ── Application du patch ───────────────────────────────────────────────────

def apply_patch(p: dict, source_index: dict, force: bool = False) -> bool:
    """
    Applique le patch dans le fichier source.
    Crée un backup avant modification.
    Retourne True si appliqué, False sinon.
    """
    if not p.get("safe_to_autofix") and not force:
        print(f"  {Y}⊘ Ignoré (safe_to_autofix=false) — utilise --force pour forcer{E}")
        return False

    if p.get("fix_type") == "none":
        print(f"  {C}⊘ Aucun patch à appliquer (bug dans l'API, pas dans les tests){E}")
        return False

    file_rel = p.get("file_to_fix", "")
    old_code = p.get("old_code", "")
    new_code = p.get("new_code", "")

    if not file_rel or not old_code or not new_code:
        print(f"  {R}⊘ Patch incomplet (file/old_code/new_code manquant){E}")
        return False

    # Résoudre le chemin absolu
    file_abs = os.path.join(FRAMEWORK, file_rel.replace("/", os.sep))
    if not os.path.exists(file_abs):
        print(f"  {R}⊘ Fichier introuvable : {file_rel}{E}")
        return False

    content = open(file_abs, encoding="utf-8").read()

    # Vérifier que old_code existe bien dans le fichier
    if old_code not in content:
        print(f"  {R}⊘ old_code introuvable dans {file_rel} — patch non applicable{E}")
        print(f"  {Y}   (Le code a peut-être déjà été modifié){E}")
        return False

    # Backup
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup_name = os.path.basename(file_abs) + f".{p['failure'].get('tc','bak')}.bak"
    shutil.copy2(file_abs, os.path.join(BACKUP_DIR, backup_name))

    # Appliquer
    new_content = content.replace(old_code, new_code, 1)
    with open(file_abs, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"  {G}✓ Patch appliqué : {file_rel}{E}")
    print(f"  {C}  Backup : docs/bug-analyzer-backups/{backup_name}{E}")
    return True


# ── Main ───────────────────────────────────────────────────────────────────

def run(apply: bool, dry_run: bool, force: bool, tc_filter: str = None):
    print(f"\n{W}BUG ANALYZER — Diagnostic + Réparation automatique{E}")
    print(f"{C}  CoT (comprendre) + Structured Output (patch précis){E}")
    if apply:
        print(f"{Y}  Mode : --apply {'--force ' if force else ''}— écriture dans les fichiers{E}")
    elif dry_run:
        print(f"{Y}  Mode : --dry-run — affichage uniquement{E}")
    print()

    failures = load_failures(tc_filter)
    if not failures:
        print(f"{G}  Aucun échec dans allure-results.{E}")
        return

    print(f"  {len(failures)} échec(s) détecté(s)")
    source_index = _build_source_index()
    print(f"  {len(source_index)} fichiers sources indexés\n")

    applied = 0
    skipped = 0

    for i, failure in enumerate(failures, 1):
        print(f"\n{C}  [{i}/{len(failures)}]{E} Analyse CoT + patch pour "
              f"{failure.get('tc') or failure['name'][:40]}...", flush=True)

        patch = analyze_and_patch(failure, source_index)
        print_patch(patch, show_diff=True)

        if apply:
            ok = apply_patch(patch, source_index, force=force)
            if ok:
                applied += 1
            else:
                skipped += 1

    if apply:
        print(f"\n  {G}Patchs appliqués : {applied}{E}  |  "
              f"{Y}Ignorés : {skipped}{E}")
        if applied:
            print(f"  {C}Backups dans : docs/bug-analyzer-backups/{E}")
    else:
        print(f"\n  {Y}Lance avec --apply pour écrire les corrections.{E}")


def print_help():
    print(f"""
{W}BUG ANALYZER — Diagnostic + Réparation automatique{E}

  python agents/bug-analyzer.py                   Analyse tous les échecs
  python agents/bug-analyzer.py --dry-run         Affiche diff sans écrire
  python agents/bug-analyzer.py --apply           Applique les patches sûrs
  python agents/bug-analyzer.py --apply TC-023    Applique un seul TC
  python agents/bug-analyzer.py --apply --force   Applique même si incertain

{W}Complémentaire à rca-agent.py :{E}
  rca-agent    → DIAGNOSTIC  (chaîne causale, groupement par cause)
  bug-analyzer → RÉPARATION  (patch dans features/steps/*.py)

{W}Sécurité :{E}
  safe_to_autofix=false  → patch refusé automatiquement (LLM incertain)
  Backup créé dans docs/bug-analyzer-backups/ avant toute modification
  old_code vérifié dans le fichier avant application
""")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bug Analyzer — patch automatique")
    parser.add_argument("--apply",   action="store_true", help="Applique les patches")
    parser.add_argument("--dry-run", action="store_true", help="Affiche sans écrire")
    parser.add_argument("--force",   action="store_true", help="Applique même si safe_to_autofix=false")
    parser.add_argument("tc",        nargs="?", default=None, help="TC-XXX optionnel")
    args = parser.parse_args()

    if len(sys.argv) == 1:
        print_help()
    else:
        run(apply=args.apply, dry_run=args.dry_run, force=args.force, tc_filter=args.tc)
