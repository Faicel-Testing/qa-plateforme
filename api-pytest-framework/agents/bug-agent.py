# ============================================================
# Bug Agent — Triage · RCA · Repair (Agentic Loop)
# ============================================================
# Absorbe : triage-agent · rca-agent · bug-analyzer
#
# Commandes :
#   python agents/bug-agent.py triage          → classifie tous les échecs (Confidence Scoring)
#   python agents/bug-agent.py rca             → Root Cause Analysis (Chain of Thought)
#   python agents/bug-agent.py rca TC-023      → RCA d'un seul TC
#   python agents/bug-agent.py repair          → propose et applique des patches
#   python agents/bug-agent.py repair --apply  → applique automatiquement les patches sûrs
#   python agents/bug-agent.py report          → rapport HTML complet (triage + RCA)
#   python agents/bug-agent.py loop            → boucle agentique : triage→rca→repair
#
# Agentic loop :
#   AGENT_MAX_ITER=5 (env) ou --max-iter=N (CLI), hard cap 20
# ============================================================

import sys, os, json, glob, re, shutil, difflib, argparse
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm

FRAMEWORK    = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS_DIR  = os.path.join(FRAMEWORK, "allure-results")
STEPS_DIR    = os.path.join(FRAMEWORK, "features", "steps")
TESTS_DIR    = os.path.join(FRAMEWORK, "tests")
FEATURES_DIR = os.path.join(FRAMEWORK, "features")
DOCS_DIR     = os.path.join(FRAMEWORK, "docs")
BACKUP_DIR   = os.path.join(DOCS_DIR, "bug-agent-backups")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

CONFIDENCE_THRESHOLD = 0.70
DEFAULT_MAX_ITER = int(os.environ.get("AGENT_MAX_ITER", "5"))
HARD_CAP         = 20

# ── Schémas Structured Output ──────────────────────────────────────────────

RCA_SCHEMA = {
    "type": "object",
    "properties": {
        "root_cause":     {"type": "string"},
        "cause_category": {"type": "string", "enum": ["assertion", "auth", "data", "network", "config", "fixture", "logic", "unknown"]},
        "chain":          {"type": "array", "items": {"type": "string"}},
        "affected_layer": {"type": "string", "enum": ["test_code", "step_definition", "api", "config", "data", "infrastructure"]},
        "fix_action":     {"type": "string"},
        "fix_priority":   {"type": "string", "enum": ["immediate", "high", "medium", "low"]},
        "related_tcs":    {"type": "array", "items": {"type": "string"}},
    },
    "required": ["root_cause", "cause_category", "chain", "affected_layer", "fix_action", "fix_priority", "related_tcs"]
}

PATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "root_cause":      {"type": "string"},
        "fix_description": {"type": "string"},
        "fix_type":        {"type": "string", "enum": ["assertion", "fixture", "step", "config", "data", "feature", "none"]},
        "file_to_fix":     {"type": "string"},
        "old_code":        {"type": "string"},
        "new_code":        {"type": "string"},
        "confidence":      {"type": "number"},
        "safe_to_autofix": {"type": "boolean"},
        "warning":         {"type": "string"},
    },
    "required": ["root_cause", "fix_description", "fix_type", "file_to_fix",
                 "old_code", "new_code", "confidence", "safe_to_autofix"]
}

CATEGORY_COLORS = {
    "real_bug": R, "flaky": Y, "env_issue": C, "false_positive": G, "unknown": Y,
    "assertion": R, "auth": Y, "data": C, "network": C, "config": Y,
    "fixture": Y, "logic": R,
}

CATEGORY_LABELS = {
    "real_bug": "VRAI BUG", "flaky": "FLAKY   ", "env_issue": "ENV     ",
    "false_positive": "FAUX POS", "unknown": "INCONNU ",
}

PRIORITY_COLORS = {"immediate": R, "high": Y, "medium": C, "low": G}


# ── Chargement des résultats Allure ───────────────────────────────────────

def load_failures(tc_filter: str = None) -> list:
    failures = []
    for f in glob.glob(os.path.join(RESULTS_DIR, "*-result.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
            if d.get("status") not in ("failed", "broken"):
                continue
            tags   = [lb["value"] for lb in d.get("labels", []) if lb["name"] == "tag"]
            tc     = next((t for t in tags if re.match(r"tc-\d+", t)), None)
            us     = next((t for t in tags if re.match(r"us-\d+", t)), None)
            suite  = next((lb["value"] for lb in d.get("labels", []) if lb["name"] == "suite"), "?")
            detail = d.get("statusDetails") or {}

            if tc_filter and tc and tc_filter.lower() != tc.lower():
                continue

            failures.append({
                "name":    d.get("name", "?"),
                "status":  d.get("status"),
                "tc":      tc, "us": us, "suite": suite, "tags": tags,
                "message": detail.get("message", "")[:500],
                "trace":   detail.get("trace",   "")[:600],
            })
        except Exception:
            pass
    return failures


def _source_index() -> dict:
    index = {}
    for pattern in [
        os.path.join(STEPS_DIR, "*.py"),
        os.path.join(TESTS_DIR, "*.py"),
        os.path.join(FEATURES_DIR, "*.feature"),
    ]:
        for fpath in glob.glob(pattern):
            rel = os.path.relpath(fpath, FRAMEWORK).replace("\\", "/")
            try:
                index[rel] = open(fpath, encoding="utf-8").read()
            except Exception:
                pass
    return index


# ── Triage — Confidence Scoring ────────────────────────────────────────────

def classify_failure(failure: dict) -> dict:
    messages = [{"role": "user", "content": (
        f"Analyse cet echec de test API et classe-le dans UNE seule categorie :\n\n"
        f"Test    : {failure['name']}\n"
        f"TC      : {failure['tc'] or '?'} | US : {failure['us'] or '?'}\n"
        f"Statut  : {failure['status']}\n"
        f"Message : {failure['message'] or 'aucun message'}\n"
        f"Trace   : {failure['trace'][:200] or 'aucune trace'}\n\n"
        f"Categories :\n"
        f"  real_bug       -> Bug dans le code applicatif\n"
        f"  flaky          -> Test instable (timeout, race condition)\n"
        f"  env_issue      -> Probleme infrastructure\n"
        f"  false_positive -> Le test lui-meme est incorrect\n\n"
        f"Reponds avec la categorie, un score de confiance 0.0-1.0, et le raisonnement."
    )}]
    raw = llm.chat_confident(messages)
    response_text = str(raw.get("response", "")).lower()
    category = "unknown"
    for cat in ("real_bug", "flaky", "env_issue", "false_positive"):
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


def confidence_bar(score: float) -> str:
    filled = int(score * 20)
    color  = G if score >= 0.8 else Y if score >= 0.6 else R
    return f"{color}{'█' * filled}{'░' * (20 - filled)}{E} {int(score * 100)}%"


def cmd_triage() -> list:
    print(f"\n{W}BUG AGENT — Triage (Confidence Scoring){E}")
    print(f"{Y}Seuil revision humaine : confidence < {int(CONFIDENCE_THRESHOLD*100)}%{E}\n")
    failures = load_failures()
    if not failures:
        print(f"{G}  Aucun echec dans allure-results.{E}")
        return []
    print(f"  {len(failures)} echec(s) detecte(s)\n")
    results = []
    for i, f in enumerate(failures, 1):
        print(f"  {C}[{i}/{len(failures)}]{E} Classification de {f['tc'] or f['name'][:40]}...", end=" ", flush=True)
        r = classify_failure(f)
        results.append(r)
        cat   = r["category"]
        color = CATEGORY_COLORS.get(cat, Y)
        flag  = f" {R}⚠{E}" if r["needs_human_review"] else f" {G}✓{E}"
        print(f"{color}{CATEGORY_LABELS.get(cat,cat)}{E} {int(r['confidence']*100)}%{flag}")

    # Résumé
    by_cat = {}
    for r in results:
        by_cat.setdefault(r["category"], []).append(r)
    nb_review = sum(1 for r in results if r["needs_human_review"])
    print(f"\n  {W}Resume :{E} ", end="")
    for cat, items in sorted(by_cat.items()):
        print(f"{CATEGORY_COLORS.get(cat,Y)}{CATEGORY_LABELS.get(cat,cat).strip()}x{len(items)}{E}  ", end="")
    print(f"\n  Revisions humaines : {R if nb_review else G}{nb_review}/{len(results)}{E}")
    return results


# ── RCA — Chain of Thought ─────────────────────────────────────────────────

def run_rca(failure: dict, all_tcs: list) -> dict:
    other_tcs = [t for t in all_tcs if t != failure.get("tc")]

    cot_messages = [{"role": "user", "content": (
        f"Effectue une RCA de cet echec de test API :\n\n"
        f"Test    : {failure['name']}\n"
        f"TC      : {failure['tc'] or '?'} | US : {failure['us'] or '?'}\n"
        f"Suite   : {failure['suite']}\n"
        f"Statut  : {failure['status']}\n"
        f"Erreur  : {failure['message'] or 'aucun message'}\n"
        f"Trace   :\n{failure['trace'] or 'aucune trace'}\n\n"
        f"Autres TCs en echec : {other_tcs}\n"
    )}]
    cot_reasoning = llm.chat_cot(cot_messages)

    struct_messages = [{"role": "user", "content": (
        f"Sur la base de cette RCA :\n\n{cot_reasoning}\n\n"
        f"Extrais les informations structurees. Pour related_tcs, utilise cette liste : {other_tcs}"
    )}]
    structured = llm.chat_structured(struct_messages, RCA_SCHEMA)
    return {**failure, **structured, "cot_reasoning": cot_reasoning}


def print_rca(r: dict, show_cot: bool = False):
    cat_color  = CATEGORY_COLORS.get(r.get("cause_category", "unknown"), Y)
    prio_color = PRIORITY_COLORS.get(r.get("fix_priority", "medium"), Y)
    print(f"\n  {W}{'─'*54}{E}")
    print(f"  {W}{r.get('tc','?'):>8}{E}  {r['name'][:50]}")
    print(f"  Categorie : {cat_color}{W}{r.get('cause_category','?'):<12}{E}  Couche : {r.get('affected_layer','?')}")
    print(f"  Priorite  : {prio_color}{W}{r.get('fix_priority','?'):<10}{E}")
    chain = r.get("chain", [])
    if chain:
        print(f"\n  {W}Chaine causale :{E}")
        for i, step in enumerate(chain):
            arrow = "  └─" if i == len(chain) - 1 else "  ├─"
            color = R if i == len(chain) - 1 else C
            print(f"{arrow} {color}{step}{E}")
    print(f"\n  {W}Cause racine :{E} {R}{r.get('root_cause','')}{E}")
    print(f"  {W}Action       :{E} {G}{r.get('fix_action','')}{E}")
    related = r.get("related_tcs", [])
    if related:
        print(f"  {W}TCs lies     :{E} {Y}{', '.join(related)}{E}")
    if show_cot and r.get("cot_reasoning"):
        print(f"\n  {C}── Raisonnement CoT ──────────────{E}")
        for line in r["cot_reasoning"].split("\n"):
            if re.match(r"\s*ÉTAPE\s*\d", line, re.IGNORECASE):
                print(f"  {Y}{line}{E}")
            elif re.match(r"\s*CONCLUSION", line, re.IGNORECASE):
                print(f"  {G}{line}{E}")
            elif line.strip():
                print(f"  {line}")


def cmd_rca(tc_filter: str = None) -> list:
    print(f"\n{W}BUG AGENT — RCA (Chain of Thought){E}")
    print(f"{Y}  CoT = raisonnement multi-etapes avant conclusion{E}\n")
    failures = load_failures(tc_filter)
    if not failures:
        print(f"{G}  Aucun echec.{E}" if not tc_filter else f"{R}  TC {tc_filter} introuvable ou non en echec.{E}")
        return []
    all_tcs = [f["tc"] for f in load_failures() if f.get("tc")]
    print(f"  {len(failures)} echec(s) | TCs : {', '.join(all_tcs)}\n")
    rcas = []
    for i, f in enumerate(failures, 1):
        print(f"  {C}[{i}/{len(failures)}]{E} RCA pour {f['tc'] or f['name'][:35]}...", flush=True)
        r = run_rca(f, all_tcs)
        rcas.append(r)
        print_rca(r, show_cot=(tc_filter is not None))
    return rcas


# ── Repair — Patch automatique ─────────────────────────────────────────────

def generate_patch(failure: dict, source_index: dict) -> dict:
    source_ctx = "\n\n".join(
        [f"# {path}\n{content[:800]}" for path, content in source_index.items()][:6]
    )
    cot_messages = [{"role": "user", "content": (
        f"Analyse cet echec de test et propose un correctif :\n\n"
        f"Test    : {failure['name']}\n"
        f"TC      : {failure['tc'] or '?'}\n"
        f"Message : {failure['message'] or 'aucun message'}\n"
        f"Trace   :\n{failure['trace'] or 'aucune trace'}\n\n"
        f"Fichiers sources disponibles :\n{source_ctx}"
    )}]
    cot_reasoning = llm.chat_cot(cot_messages)

    struct_messages = [{"role": "user", "content": (
        f"Sur la base de cette analyse :\n{cot_reasoning}\n\n"
        f"Fournis le patch structure. Pour old_code et new_code, utilise du code existant dans les fichiers sources."
    )}]
    try:
        patch = llm.chat_structured(struct_messages, PATCH_SCHEMA)
    except Exception as e:
        patch = {
            "root_cause": "LLM indisponible", "fix_description": str(e),
            "fix_type": "none", "file_to_fix": "", "old_code": "", "new_code": "",
            "confidence": 0.0, "safe_to_autofix": False, "warning": "LLM error"
        }
    patch["cot_reasoning"] = cot_reasoning
    patch["tc"] = failure.get("tc")
    patch["test_name"] = failure["name"]
    return patch


def apply_patch(patch: dict, dry_run: bool = True) -> bool:
    file_rel = patch.get("file_to_fix", "")
    old_code = patch.get("old_code", "")
    new_code = patch.get("new_code", "")
    if not file_rel or not old_code or patch.get("fix_type") == "none":
        print(f"  {Y}  [SKIP] Pas de patch applicable.{E}")
        return False

    file_path = os.path.join(FRAMEWORK, file_rel.replace("/", os.sep))
    if not os.path.exists(file_path):
        print(f"  {R}  [ERR] Fichier introuvable : {file_rel}{E}")
        return False

    content = open(file_path, encoding="utf-8").read()
    if old_code not in content:
        print(f"  {Y}  [WARN] old_code introuvable dans {file_rel}{E}")
        return False

    new_content = content.replace(old_code, new_code, 1)

    # Afficher le diff
    diff = list(difflib.unified_diff(
        content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"a/{file_rel}", tofile=f"b/{file_rel}", n=3
    ))
    for line in diff[:30]:
        color = G if line.startswith("+") else R if line.startswith("-") else ""
        print(f"  {color}{line.rstrip()}{E}")

    if dry_run:
        print(f"  {Y}  [DRY-RUN] Patch non applique.{E}")
        return False

    # Backup + application
    os.makedirs(BACKUP_DIR, exist_ok=True)
    shutil.copy2(file_path, os.path.join(BACKUP_DIR, os.path.basename(file_path) + ".bak"))
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"  {G}  [OK] Patch applique : {file_rel}{E}")
    return True


def cmd_repair(apply: bool = False, tc_filter: str = None):
    print(f"\n{W}BUG AGENT — Repair {'(apply)' if apply else '(dry-run)'}{E}\n")
    failures = load_failures(tc_filter)
    if not failures:
        print(f"{G}  Aucun echec.{E}")
        return

    source_index = _source_index()
    patches = []
    for i, f in enumerate(failures, 1):
        print(f"\n  {C}[{i}/{len(failures)}]{E} Patch pour {f['tc'] or f['name'][:35]}...")
        patch = generate_patch(f, source_index)
        patches.append(patch)

        conf  = patch.get("confidence", 0)
        safe  = patch.get("safe_to_autofix", False)
        color = G if conf >= 0.8 else Y if conf >= 0.6 else R
        print(f"  {W}Cause :{E} {patch.get('root_cause','')[:80]}")
        print(f"  {W}Fix   :{E} {patch.get('fix_description','')[:80]}")
        print(f"  {W}Conf  :{E} {color}{int(conf*100)}%{E}  Safe:{G if safe else R}{safe}{E}")

        if apply:
            if safe:
                apply_patch(patch, dry_run=False)
            else:
                warning = patch.get("warning", "LLM peu confiant")
                print(f"  {R}  [SKIP] Non safe_to_autofix : {warning}{E}")
        else:
            apply_patch(patch, dry_run=True)

    applied = sum(1 for p in patches if p.get("safe_to_autofix"))
    print(f"\n  {W}Resume :{E} {len(patches)} patches | {G}{applied} applicables{E} | "
          f"{R}{len(patches)-applied} manuels{E}")


# ── Rapport HTML ───────────────────────────────────────────────────────────

def cmd_report():
    print(f"\n{W}BUG AGENT — Rapport HTML{E}")
    triage_results = cmd_triage()
    rca_results    = cmd_rca()

    by_cat = {}
    for r in triage_results:
        by_cat.setdefault(r["category"], []).append(r)

    CAT_COLORS_HTML = {
        "real_bug": "#e74c3c", "flaky": "#e67e22",
        "env_issue": "#3498db", "false_positive": "#27ae60", "unknown": "#95a5a6",
    }
    PRIO_COLORS_HTML = {
        "immediate": "#e74c3c", "high": "#e67e22", "medium": "#3498db", "low": "#27ae60"
    }

    triage_rows = ""
    for r in sorted(triage_results, key=lambda x: x["confidence"]):
        cat   = r["category"]
        color = CAT_COLORS_HTML.get(cat, "#95a5a6")
        pct   = int(r["confidence"] * 100)
        bar   = (f'<div style="background:#eee;border-radius:4px;height:14px;width:120px;display:inline-block">'
                 f'<div style="background:{color};width:{pct}%;height:100%;border-radius:4px"></div></div>')
        flag  = ('<span style="background:#e74c3c;color:#fff;padding:1px 6px;border-radius:3px;font-size:11px">⚠ RÉVISION</span>'
                 if r["needs_human_review"] else '')
        triage_rows += (f"<tr>"
                        f"<td style='font-family:monospace;font-size:12px'>{r['tc'] or '—'}</td>"
                        f"<td style='font-size:12px'>{r['name'][:60]}</td>"
                        f"<td><span style='background:{color};color:#fff;padding:2px 8px;border-radius:3px;font-size:12px'>"
                        f"{CATEGORY_LABELS.get(cat,cat).strip()}</span></td>"
                        f"<td>{bar} {pct}%</td>"
                        f"<td style='font-size:11px;color:#666'>{r.get('reasoning','')[:80]}</td>"
                        f"<td>{flag}</td></tr>")

    rca_rows = ""
    for r in rca_results:
        cat   = r.get("cause_category", "unknown")
        prio  = r.get("fix_priority", "medium")
        chain_html = " → ".join(r.get("chain", []))
        rca_rows += (f"<tr>"
                     f"<td style='font-family:monospace'>{r.get('tc','—')}</td>"
                     f"<td style='font-size:12px'>{r['name'][:50]}</td>"
                     f"<td><span style='background:{CAT_COLORS_HTML.get(cat,'#95a5a6')};color:#fff;"
                     f"padding:2px 7px;border-radius:3px;font-size:11px'>{cat}</span></td>"
                     f"<td style='font-size:11px;color:#555'>{chain_html[:100]}</td>"
                     f"<td style='font-size:12px'>{r.get('root_cause','')[:70]}</td>"
                     f"<td style='font-size:12px;color:#27ae60'>{r.get('fix_action','')[:70]}</td>"
                     f"<td><span style='background:{PRIO_COLORS_HTML.get(prio,'#3498db')};color:#fff;"
                     f"padding:2px 7px;border-radius:3px;font-size:11px'>{prio}</span></td></tr>")

    nb_review = sum(1 for r in triage_results if r["needs_human_review"])
    avg_conf  = int(sum(r["confidence"] for r in triage_results) / len(triage_results) * 100) if triage_results else 0

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Bug Agent — Triage & RCA</title>
<style>
  body{{font-family:Arial,sans-serif;background:#f5f5f5;color:#333;margin:0;padding:20px}}
  h1{{color:#2c3e50}} h2{{color:#34495e;margin-top:30px}}
  .stat{{display:inline-block;background:#fff;border-radius:8px;padding:15px 25px;margin:8px;
         box-shadow:0 2px 6px rgba(0,0,0,.1);text-align:center}}
  .stat-val{{font-size:28px;font-weight:bold}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;
         box-shadow:0 2px 8px rgba(0,0,0,.1);margin-top:15px}}
  th{{background:#2c3e50;color:#fff;padding:10px;text-align:left;font-size:13px}}
  td{{padding:9px 10px;border-bottom:1px solid #ecf0f1;vertical-align:middle}}
  tr:hover{{background:#f8f9fa}}
</style>
</head>
<body>
<h1>Bug Agent — Triage & RCA</h1>
<div>
  <div class="stat"><div class="stat-val" style="color:#e74c3c">{len(triage_results)}</div>Echecs analysés</div>
  <div class="stat"><div class="stat-val" style="color:#e67e22">{avg_conf}%</div>Confiance moyenne</div>
  <div class="stat"><div class="stat-val" style="color:{'#e74c3c' if nb_review else '#27ae60'}">{nb_review}</div>Révisions humaines</div>
  <div class="stat"><div class="stat-val" style="color:#e74c3c">{len(by_cat.get('real_bug',[]))}</div>Vrais bugs</div>
  <div class="stat"><div class="stat-val" style="color:#e67e22">{len(by_cat.get('flaky',[]))}</div>Flaky</div>
</div>
<h2>Triage — Classification ({len(triage_results)} échecs)</h2>
<table>
  <tr><th>TC</th><th>Nom du test</th><th>Catégorie</th><th>Confiance</th><th>Raisonnement</th><th>Action</th></tr>
  {triage_rows}
</table>
<h2>RCA — Causes racines ({len(rca_results)} analyses)</h2>
<table>
  <tr><th>TC</th><th>Test</th><th>Catégorie</th><th>Chaîne causale</th><th>Cause racine</th><th>Action</th><th>Priorité</th></tr>
  {rca_rows}
</table>
<p style="color:#999;font-size:12px;margin-top:30px">Généré par Bug Agent — Triage + RCA (CoT + Confidence Scoring)</p>
</body>
</html>"""

    out = os.path.join(DOCS_DIR, "bug-report.html")
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n{G}  Rapport HTML : docs/bug-report.html{E}")


# ── Agentic Loop ────────────────────────────────────────────────────────────

def cmd_loop(max_iter: int = DEFAULT_MAX_ITER):
    max_iter = min(max_iter, HARD_CAP)
    print(f"\n{W}BUG AGENT — Agentic Loop (max_iter={max_iter}){E}")
    print(f"{Y}  Boucle : Triage → RCA → Repair → vérification{E}\n")

    iter_count = 0
    while iter_count < max_iter:
        iter_count += 1
        print(f"\n{C}{'─'*50}{E}")
        print(f"{C}  Iteration {iter_count}/{max_iter}{E}")
        print(f"{C}{'─'*50}{E}")

        # Étape 1 : Triage
        triage_results = cmd_triage()
        real_bugs = [r for r in triage_results if r["category"] == "real_bug"]

        if not real_bugs:
            print(f"\n{G}  [LOOP] Aucun vrai bug detecte. Boucle terminee.{E}")
            break

        print(f"\n{Y}  {len(real_bugs)} vrai(s) bug(s) detecte(s) — RCA en cours...{E}")

        # Étape 2 : RCA sur les vrais bugs uniquement
        all_tcs = [f["tc"] for f in real_bugs if f.get("tc")]
        rcas = []
        for f in real_bugs:
            r = run_rca(f, all_tcs)
            rcas.append(r)
            print_rca(r)

        # Étape 3 : Repair sur les priorités immédiates
        immediate = [r for r in rcas if r.get("fix_priority") == "immediate"]
        if not immediate:
            print(f"\n{G}  [LOOP] Aucune priorite immediate. Boucle terminee.{E}")
            break

        print(f"\n{Y}  {len(immediate)} priorite(s) immediate(s) — Repair en cours...{E}")
        source_index = _source_index()
        applied_any = False
        for f in immediate:
            patch = generate_patch(f, source_index)
            if patch.get("safe_to_autofix") and apply_patch(patch, dry_run=False):
                applied_any = True

        if not applied_any:
            print(f"\n{Y}  [LOOP] Aucun patch safe applique. Intervention manuelle requise.{E}")
            break

        print(f"\n{G}  [LOOP] Iteration {iter_count} terminee. Verification au prochain cycle...{E}")

    print(f"\n{W}  Boucle agentique terminee ({iter_count} iteration(s)){E}")


# ── Main ───────────────────────────────────────────────────────────────────

def print_help():
    print(f"""
{W}BUG AGENT — Triage · RCA · Repair{E}

  python agents/bug-agent.py triage          Classifie tous les echecs (Confidence Scoring)
  python agents/bug-agent.py rca             Root Cause Analysis de tous les echecs (CoT)
  python agents/bug-agent.py rca TC-023      RCA d'un seul TC (CoT complet visible)
  python agents/bug-agent.py repair          Propose des patches (dry-run)
  python agents/bug-agent.py repair --apply  Applique les patches safe_to_autofix=true
  python agents/bug-agent.py report          Rapport HTML complet (triage + RCA)
  python agents/bug-agent.py loop            Boucle agentique : triage → rca → repair

{W}Options :{E}
  --max-iter=N   Iterations max de la boucle (defaut={DEFAULT_MAX_ITER}, hard cap=20)
  --apply        Applique les patches (sans dry-run)
  AGENT_MAX_ITER Variable d'environnement pour configurer le max par defaut

{W}Modules absorbes :{E} triage-agent · rca-agent · bug-analyzer
""")


if __name__ == "__main__":
    # Parse --max-iter
    max_iter_arg = next((int(a.split("=")[1]) for a in sys.argv if a.startswith("--max-iter=")), DEFAULT_MAX_ITER)
    apply_flag   = "--apply" in sys.argv
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "triage":
        cmd_triage()
    elif cmd == "rca":
        tc_filter = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("-") else None
        cmd_rca(tc_filter)
    elif cmd == "repair":
        tc_filter = next((a for a in sys.argv[2:] if not a.startswith("-")), None)
        cmd_repair(apply=apply_flag, tc_filter=tc_filter)
    elif cmd == "report":
        cmd_report()
    elif cmd == "loop":
        cmd_loop(max_iter=max_iter_arg)
    else:
        print_help()
