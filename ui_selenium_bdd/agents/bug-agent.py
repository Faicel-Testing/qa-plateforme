# ============================================================
# Bug Agent — Triage · RCA · Réparation Selenium BDD
# ============================================================
# Commandes :
#   python agents/bug-agent.py triage          → classifie les échecs Allure
#   python agents/bug-agent.py rca [tc]        → Root Cause Analysis (CoT)
#   python agents/bug-agent.py repair [tc]     → patch automatique Java
#   python agents/bug-agent.py loop            → boucle agentique complète
#   python agents/bug-agent.py report          → rapport HTML docs/bug-report.html
# ============================================================

import sys, os, json, glob, re, shutil, difflib, argparse
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm
from prompt_store import PromptStore

_ps = PromptStore()

def _fmt(template: str, **kw) -> str:
    result = template
    for key, val in kw.items():
        result = result.replace("{" + key + "}", str(val))
    return result

FRAMEWORK   = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ALLURE_DIR  = os.path.join(FRAMEWORK, "target", "allure-results")
PAGES_DIR   = os.path.join(FRAMEWORK, "src", "test", "java", "com", "qacart", "todo", "pages")
STEPS_DIR   = os.path.join(FRAMEWORK, "src", "test", "java", "com", "qacart", "todo", "steps")
FEATURES_DIR= os.path.join(FRAMEWORK, "src", "test", "resources", "features")
DOCS_DIR    = os.path.join(FRAMEWORK, "docs")
BACKUP_DIR  = os.path.join(DOCS_DIR, "bug-agent-backups")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

CONFIDENCE_THRESHOLD = 0.70
DEFAULT_MAX_ITER = int(os.environ.get("AGENT_MAX_ITER", "5"))
HARD_CAP = 20

TRIAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "category":           {"type": "string", "enum": ["real_bug", "flaky", "env_issue", "false_positive", "selector_issue", "timing_issue"]},
        "confidence":         {"type": "number"},
        "reasoning":          {"type": "string"},
        "needs_human_review": {"type": "boolean"},
    }
}

RCA_SCHEMA = {
    "type": "object",
    "properties": {
        "root_cause":     {"type": "string"},
        "cause_category": {"type": "string", "enum": ["assertion", "selector", "timing", "data", "network", "config", "java_exception", "unknown"]},
        "chain":          {"type": "array", "items": {"type": "string"}},
        "affected_layer": {"type": "string", "enum": ["feature", "step_definition", "page_object", "webdriver", "application", "data", "infrastructure"]},
        "fix_action":     {"type": "string"},
        "fix_priority":   {"type": "string", "enum": ["immediate", "high", "medium", "low"]},
        "related_tests":  {"type": "array", "items": {"type": "string"}},
    }
}

PATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "file_to_modify": {"type": "string"},
        "class_name":     {"type": "string"},
        "method_name":    {"type": "string"},
        "old_code":       {"type": "string"},
        "new_code":       {"type": "string"},
        "explanation":    {"type": "string"},
        "confidence":     {"type": "number"},
    }
}

CATEGORY_COLORS = {
    "real_bug":       R,
    "flaky":          Y,
    "env_issue":      C,
    "false_positive": "\033[2m",
    "selector_issue": Y,
    "timing_issue":   Y,
}
CATEGORY_LABELS = {
    "real_bug":       " BUG RÉEL     ",
    "flaky":          " FLAKY        ",
    "env_issue":      " ENV / INFRA  ",
    "false_positive": " FAUX POSITIF ",
    "selector_issue": " SÉLECTEUR    ",
    "timing_issue":   " TIMING       ",
}
PRIORITY_COLORS = {"immediate": R, "high": R, "medium": Y, "low": G}


# ── Chargement des résultats Allure ───────────────────────────────────────────

def load_failures(name_filter: str = None) -> list:
    failures = []
    for f in glob.glob(os.path.join(ALLURE_DIR, "*.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            if data.get("status") not in ("failed", "broken"):
                continue
            details = data.get("statusDetails", {})
            labels  = {lbl["name"]: lbl["value"] for lbl in data.get("labels", [])}
            entry = {
                "name":    data.get("name", "?"),
                "status":  data.get("status"),
                "message": details.get("message", ""),
                "trace":   details.get("trace", ""),
                "feature": labels.get("feature", ""),
                "suite":   labels.get("suite", ""),
                "tags":    [lbl["value"] for lbl in data.get("labels", []) if lbl["name"] == "tag"],
            }
            if name_filter and name_filter.lower() not in entry["name"].lower():
                continue
            failures.append(entry)
        except Exception:
            pass
    return failures


def load_source_index() -> dict:
    index = {}
    for directory in [PAGES_DIR, STEPS_DIR]:
        for f in glob.glob(os.path.join(directory, "**", "*.java"), recursive=True):
            try:
                with open(f, encoding="utf-8") as fh:
                    index[os.path.relpath(f, FRAMEWORK)] = fh.read()
            except Exception:
                pass
    return index


# ── Triage ─────────────────────────────────────────────────────────────────────

def classify_failure(failure: dict) -> dict:
    _tpl = _ps.get("triage_classify") or (
        "Analyse cet échec de test Selenium BDD et classe-le dans UNE seule catégorie :\n\n"
        "Test    : {test_name}\n"
        "Feature : {feature}\n"
        "Statut  : {status}\n"
        "Message : {error_message}\n"
        "Trace   : {stack_trace}\n\n"
        "Catégories (Selenium/Java) :\n"
        "  real_bug       → Bug dans l'application web\n"
        "  selector_issue → Sélecteur CSS/XPath cassé ou obsolète\n"
        "  timing_issue   → Problème de synchronisation (wait, timing)\n"
        "  flaky          → Test instable (réseau, état)\n"
        "  env_issue      → Problème d'environnement/infrastructure\n"
        "  false_positive → Le test lui-même est incorrect\n\n"
        "Réponds avec la catégorie, un score de confiance 0.0-1.0, et le raisonnement."
    )
    messages = [{"role": "user", "content": _fmt(_tpl,
        test_name=failure["name"],
        feature=failure.get("feature", "?"),
        status=failure["status"],
        error_message=failure["message"] or "aucun message",
        stack_trace=(failure["trace"] or "aucune trace")[:300],
    )}]
    raw = llm.chat_confident(messages)
    _ps.record_usage("triage_classify", confidence=float(raw.get("confidence", 0.5)))
    response_text = str(raw.get("response", "")).lower()
    category = "unknown"
    for cat in ("selector_issue", "timing_issue", "real_bug", "flaky", "env_issue", "false_positive"):
        if cat in response_text:
            category = cat
            break
    return {
        **failure,
        "category":           category,
        "confidence":         float(raw.get("confidence", 0.5)),
        "reasoning":          raw.get("reasoning", ""),
        "needs_human_review": raw.get("needs_human_review", True),
    }


def cmd_triage(name_filter: str = None):
    print(f"\n{W}BUG AGENT — Triage Selenium (Confidence Scoring){E}")
    print(f"{Y}Seuil révision humaine : confidence < {int(CONFIDENCE_THRESHOLD*100)}%{E}\n")
    failures = load_failures(name_filter)
    if not failures:
        print(f"{G}  Aucun échec dans target/allure-results.{E}")
        return []
    print(f"  {len(failures)} échec(s) détecté(s)\n")
    results = []
    for i, f in enumerate(failures, 1):
        print(f"  {C}[{i}/{len(failures)}]{E} {f['name'][:50]}...", end=" ", flush=True)
        r = classify_failure(f)
        results.append(r)
        cat   = r["category"]
        color = CATEGORY_COLORS.get(cat, Y)
        flag  = f" {R}⚠{E}" if r["needs_human_review"] else f" {G}✓{E}"
        print(f"{color}{CATEGORY_LABELS.get(cat, cat)}{E} {int(r['confidence']*100)}%{flag}")
    nb_review = sum(1 for r in results if r["needs_human_review"])
    print(f"\n  Révisions humaines nécessaires : {R if nb_review else G}{nb_review}/{len(results)}{E}")
    return results


# ── RCA ────────────────────────────────────────────────────────────────────────

def run_rca(failure: dict, all_tests: list) -> dict:
    other_tests = [t for t in all_tests if t != failure.get("name")]
    _rca_tpl = _ps.get("rca_analyze") or (
        "Effectue une RCA de cet échec de test Selenium BDD (Java) :\n\n"
        "Test    : {test_name}\n"
        "Feature : {feature}\n"
        "Statut  : {status}\n"
        "Erreur  : {error_message}\n"
        "Trace   :\n{stack_trace}\n\n"
        "Autres tests en échec : {other_tests}\n\n"
        "Identifie la couche affectée : feature | step_definition | page_object | webdriver | application"
    )
    cot_messages = [{"role": "user", "content": _fmt(_rca_tpl,
        test_name=failure["name"],
        feature=failure.get("feature", "?"),
        status=failure["status"],
        error_message=failure["message"] or "aucun message",
        stack_trace=failure["trace"] or "aucune trace",
        other_tests=str(other_tests[:5]),
    )}]
    cot_reasoning = llm.chat_cot(cot_messages)
    _ps.record_usage("rca_analyze")

    struct_messages = [{"role": "user", "content": (
        f"Sur la base de cette RCA Selenium :\n\n{cot_reasoning}\n\n"
        f"Extrais les informations structurées."
    )}]
    structured = llm.chat_structured(struct_messages, RCA_SCHEMA)
    return {**failure, **structured, "cot_reasoning": cot_reasoning}


def cmd_rca(name_filter: str = None):
    print(f"\n{W}BUG AGENT — RCA Selenium (Chain of Thought){E}\n")
    failures = load_failures(name_filter)
    if not failures:
        print(f"{G}  Aucun échec.{E}")
        return []
    all_tests = [f["name"] for f in load_failures()]
    rcas = []
    for i, f in enumerate(failures, 1):
        print(f"  {C}[{i}/{len(failures)}]{E} RCA pour {f['name'][:50]}...", flush=True)
        r = run_rca(f, all_tests)
        rcas.append(r)
        cat_color  = CATEGORY_COLORS.get(r.get("cause_category", ""), Y)
        prio_color = PRIORITY_COLORS.get(r.get("fix_priority", "medium"), Y)
        print(f"  Catégorie : {cat_color}{r.get('cause_category','?')}{E}  "
              f"Couche : {r.get('affected_layer','?')}  "
              f"Priorité : {prio_color}{r.get('fix_priority','?')}{E}")
        print(f"  Cause    : {R}{r.get('root_cause','')[:80]}{E}")
        print(f"  Action   : {G}{r.get('fix_action','')[:80]}{E}\n")
    return rcas


# ── Repair ─────────────────────────────────────────────────────────────────────

def generate_patch(failure: dict, source_index: dict) -> dict:
    source_ctx = "\n\n".join(
        [f"// {path}\n{content[:600]}" for path, content in source_index.items()][:5]
    )
    _patch_tpl = _ps.get("repair_patch") or (
        "Analyse cet échec de test Selenium Java et propose un correctif :\n\n"
        "Test    : {test_name}\n"
        "Feature : {feature}\n"
        "Message : {error_message}\n"
        "Trace   :\n{stack_trace}\n\n"
        "Fichiers sources Java disponibles :\n{source_context}\n\n"
        "Propose un correctif minimal. Indique le fichier à modifier, la méthode, "
        "le code à remplacer et le nouveau code. Privilégie les sélecteurs CSS robustes "
        "ou les attentes explicites (ExpectedConditions)."
    )
    cot_messages = [{"role": "user", "content": _fmt(_patch_tpl,
        test_name=failure["name"],
        feature=failure.get("feature", "?"),
        error_message=failure["message"] or "aucun message",
        stack_trace=failure["trace"] or "aucune trace",
        source_context=source_ctx,
    )}]
    cot_reasoning = llm.chat_cot(cot_messages)
    _ps.record_usage("repair_patch")

    struct_messages = [{"role": "user", "content": (
        f"Sur la base de cette analyse :\n{cot_reasoning}\n\n"
        f"Fournis le patch structuré (fichier Java, classe, méthode, ancien code, nouveau code)."
    )}]
    try:
        patch = llm.chat_structured(struct_messages, PATCH_SCHEMA)
    except Exception:
        patch = {}
    return {**failure, "patch": patch, "cot_reasoning": cot_reasoning}


def apply_patch(patch_info: dict) -> bool:
    patch = patch_info.get("patch", {})
    file_rel = patch.get("file_to_modify", "")
    old_code = patch.get("old_code", "")
    new_code = patch.get("new_code", "")
    if not all([file_rel, old_code, new_code]):
        return False
    file_path = os.path.join(FRAMEWORK, file_rel)
    if not os.path.exists(file_path):
        return False
    with open(file_path, encoding="utf-8") as f:
        content = f.read()
    if old_code not in content:
        return False
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup = os.path.join(BACKUP_DIR, os.path.basename(file_path) + f".{int(time.time())}.bak")
    shutil.copy2(file_path, backup)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content.replace(old_code, new_code, 1))
    return True


def cmd_repair(name_filter: str = None):
    print(f"\n{W}BUG AGENT — Repair Java (CoT + Patch){E}\n")
    failures = load_failures(name_filter)
    if not failures:
        print(f"{G}  Aucun échec à réparer.{E}")
        return
    source_index = load_source_index()
    repaired = 0
    for i, f in enumerate(failures[:5], 1):
        print(f"  {C}[{i}]{E} Repair {f['name'][:55]}...", flush=True)
        result = generate_patch(f, source_index)
        patch  = result.get("patch", {})
        print(f"  Fichier : {patch.get('file_to_modify','?')}")
        print(f"  Méthode : {patch.get('method_name','?')}")
        print(f"  {C}{patch.get('explanation','')[:100]}{E}")
        if apply_patch(result):
            print(f"  {G}✓ Patch appliqué{E}")
            repaired += 1
        else:
            print(f"  {Y}⚠ Patch non applicable (diff manuel requis){E}")
    print(f"\n  {G}{repaired}/{min(len(failures),5)} réparés{E}")


def cmd_loop(name_filter: str = None, max_iter: int = DEFAULT_MAX_ITER):
    print(f"\n{W}BUG AGENT — Loop agentique (max_iter={max_iter}){E}")
    print(f"  Triage → RCA → Repair → Vérification\n")
    failures = load_failures(name_filter)
    if not failures:
        print(f"{G}  Aucun échec.{E}")
        return
    iter_count = 0
    while failures and iter_count < min(max_iter, HARD_CAP):
        iter_count += 1
        print(f"  {W}Itération {iter_count}/{max_iter}{E} — {len(failures)} échec(s)")
        triaged = [classify_failure(f) for f in failures[:3]]
        real_bugs = [t for t in triaged if t["category"] in ("real_bug", "selector_issue", "timing_issue")]
        if not real_bugs:
            print(f"  {G}Aucun bug réel détecté — arrêt.{E}")
            break
        source_index = load_source_index()
        for bug in real_bugs:
            result = generate_patch(bug, source_index)
            if apply_patch(result):
                print(f"  {G}✓ Fix appliqué : {bug['name'][:50]}{E}")
        failures = load_failures(name_filter)
        if not failures:
            print(f"  {G}Tous les bugs résolus !{E}")
            break


def cmd_report():
    print(f"\n{W}BUG AGENT — Génération rapport HTML{E}")
    failures = load_failures()
    os.makedirs(DOCS_DIR, exist_ok=True)
    if not failures:
        print(f"  {G}Aucun échec à reporter.{E}")
        return
    triaged = []
    for f in failures[:10]:
        try:
            triaged.append(classify_failure(f))
        except Exception:
            triaged.append({**f, "category": "unknown", "confidence": 0})

    rows = ""
    for r in triaged:
        cat_color = {"real_bug": "#e74c3c", "selector_issue": "#e67e22", "timing_issue": "#f39c12",
                     "flaky": "#f1c40f", "env_issue": "#3498db", "false_positive": "#95a5a6"}.get(r["category"], "#999")
        rows += f"""<tr>
            <td>{r['name'][:60]}</td>
            <td style="color:{cat_color};font-weight:bold">{r['category']}</td>
            <td>{int(r.get('confidence',0)*100)}%</td>
            <td>{r.get('reasoning','')[:80]}</td>
        </tr>"""

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
    <title>Bug Report — Selenium BDD</title>
    <style>body{{font-family:sans-serif;padding:20px;background:#111;color:#eee}}
    table{{width:100%;border-collapse:collapse}}th,td{{padding:8px;text-align:left;border-bottom:1px solid #333}}
    th{{background:#222}}h1{{color:#e74c3c}}</style></head>
    <body><h1>🐛 Bug Report — ui_selenium_bdd</h1>
    <p>Généré le {time.strftime('%Y-%m-%d %H:%M')} — {len(failures)} échec(s) analysé(s)</p>
    <table><tr><th>Test</th><th>Catégorie</th><th>Confiance</th><th>Raisonnement</th></tr>
    {rows}</table></body></html>"""

    out = os.path.join(DOCS_DIR, "bug-report.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  {G}Rapport : docs/bug-report.html{E}")


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bug Agent — Selenium BDD")
    parser.add_argument("command", choices=["triage", "rca", "repair", "loop", "report"])
    parser.add_argument("filter", nargs="?", default=None, help="Filtre sur le nom du test")
    parser.add_argument("--max-iter", type=int, default=DEFAULT_MAX_ITER)
    args = parser.parse_args()

    if args.command == "triage":  cmd_triage(args.filter)
    elif args.command == "rca":   cmd_rca(args.filter)
    elif args.command == "repair":cmd_repair(args.filter)
    elif args.command == "loop":  cmd_loop(args.filter, args.max_iter)
    elif args.command == "report":cmd_report()
