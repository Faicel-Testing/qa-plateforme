# ============================================================
# RCA Agent — Root Cause Analysis avec Chain of Thought
# ============================================================
# Différence vs bug-analyzer.py :
#   bug-analyzer → appel LLM simple, un échec à la fois, patch code
#   rca-agent    → CoT multi-étapes, groupe les failures liées,
#                  remonte la chaîne causale, rapport structuré
#
# Chain of Thought force le LLM à raisonner en 3 étapes avant
# de conclure → raisonnement traçable, hallucinations réduites.
#
# Usage:
#   python agents/rca-agent.py analyse    → RCA complète de tous les échecs
#   python agents/rca-agent.py group      → groupe par cause racine commune
#   python agents/rca-agent.py report     → rapport HTML avec chaînes causales
#   python agents/rca-agent.py single TC-023 → RCA d'un seul TC
# ============================================================

import sys, os, json, glob, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm

FRAMEWORK   = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS_DIR = os.path.join(FRAMEWORK, "allure-results")
DOCS_DIR    = os.path.join(FRAMEWORK, "docs")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

# Schéma Structured Output pour le résultat final du CoT
RCA_SCHEMA = {
    "type": "object",
    "properties": {
        "root_cause":      {"type": "string", "description": "Cause racine identifiée (1 phrase précise)"},
        "cause_category":  {"type": "string", "enum": ["assertion", "auth", "data", "network", "config", "fixture", "logic", "unknown"]},
        "chain":           {"type": "array",  "items": {"type": "string"}, "description": "Chaîne causale : symptôme → cause intermédiaire → cause racine"},
        "affected_layer":  {"type": "string", "enum": ["test_code", "step_definition", "api", "config", "data", "infrastructure"]},
        "fix_action":      {"type": "string", "description": "Action corrective concrète à faire"},
        "fix_priority":    {"type": "string", "enum": ["immediate", "high", "medium", "low"]},
        "related_tcs":     {"type": "array",  "items": {"type": "string"}, "description": "Autres TCs probablement affectés par la même cause"}
    },
    "required": ["root_cause", "cause_category", "chain", "affected_layer", "fix_action", "fix_priority", "related_tcs"]
}

CATEGORY_COLORS = {
    "assertion":     R,
    "auth":          Y,
    "data":          C,
    "network":       C,
    "config":        Y,
    "fixture":       Y,
    "logic":         R,
    "unknown":       Y,
}

PRIORITY_COLORS = {
    "immediate": R,
    "high":      Y,
    "medium":    C,
    "low":       G,
}


# ── Chargement des échecs Allure ───────────────────────────────────────────

def load_failures(tc_filter: str = None) -> list:
    failures = []
    for f in glob.glob(os.path.join(RESULTS_DIR, "*-result.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
            if d.get("status") not in ("failed", "broken"):
                continue

            tags  = [lb["value"] for lb in d.get("labels", []) if lb["name"] == "tag"]
            tc    = next((t for t in tags if re.match(r"tc-\d+", t)), None)
            us    = next((t for t in tags if re.match(r"us-\d+", t)), None)
            suite = next((lb["value"] for lb in d.get("labels", []) if lb["name"] == "suite"), "?")

            if tc_filter and tc and tc_filter.lower() != tc.lower():
                continue

            detail = d.get("statusDetails") or {}
            failures.append({
                "name":    d.get("name", "?"),
                "status":  d.get("status"),
                "tc":      tc,
                "us":      us,
                "suite":   suite,
                "tags":    tags,
                "message": detail.get("message", "")[:500],
                "trace":   detail.get("trace",   "")[:600],
            })
        except Exception:
            pass
    return failures


# ── Chain of Thought RCA ───────────────────────────────────────────────────

def run_cot_rca(failure: dict, all_tcs: list) -> dict:
    """
    Étape 1 : CoT pour raisonner pas à pas (texte libre, traçable)
    Étape 2 : Structured Output pour extraire le résultat structuré
    """
    other_tcs = [t for t in all_tcs if t != failure.get("tc")]

    # ── Étape 1 : Chain of Thought ──────────────────────────────────────
    cot_messages = [{
        "role": "user",
        "content": (
            f"Effectue une analyse Root Cause Analysis (RCA) de cet échec de test API :\n\n"
            f"Test    : {failure['name']}\n"
            f"TC      : {failure['tc'] or '?'} | US : {failure['us'] or '?'}\n"
            f"Suite   : {failure['suite']}\n"
            f"Statut  : {failure['status']}\n"
            f"Erreur  : {failure['message'] or 'aucun message'}\n"
            f"Trace   :\n{failure['trace'] or 'aucune trace'}\n\n"
            f"Autres TCs en échec dans la même session : {other_tcs}\n"
        )
    }]
    cot_reasoning = llm.chat_cot(cot_messages)

    # ── Étape 2 : Structured Output à partir du raisonnement CoT ────────
    struct_messages = [{
        "role": "user",
        "content": (
            f"Sur la base de cette analyse RCA :\n\n{cot_reasoning}\n\n"
            f"Extrais les informations structurées demandées.\n"
            f"Pour related_tcs, liste les TCs de cette liste qui pourraient "
            f"être affectés par la même cause : {other_tcs}"
        )
    }]
    structured = llm.chat_structured(struct_messages, RCA_SCHEMA)

    return {
        **failure,
        **structured,
        "cot_reasoning": cot_reasoning,
    }


# ── Affichage ──────────────────────────────────────────────────────────────

def print_rca(r: dict, show_cot: bool = False):
    cat_color  = CATEGORY_COLORS.get(r.get("cause_category", "unknown"), Y)
    prio_color = PRIORITY_COLORS.get(r.get("fix_priority", "medium"), Y)

    print(f"\n  {W}{'─'*54}{E}")
    print(f"  {W}{r.get('tc','?'):>8}{E}  {r['name'][:50]}")
    print(f"  Catégorie : {cat_color}{W}{r.get('cause_category','?'):<12}{E}  "
          f"Couche : {r.get('affected_layer','?')}")
    print(f"  Priorité  : {prio_color}{W}{r.get('fix_priority','?'):<10}{E}")

    # Chaîne causale
    chain = r.get("chain", [])
    if chain:
        print(f"\n  {W}Chaîne causale :{E}")
        for i, step in enumerate(chain):
            arrow = "  └─" if i == len(chain) - 1 else "  ├─"
            color = R if i == len(chain) - 1 else C
            print(f"{arrow} {color}{step}{E}")

    print(f"\n  {W}Cause racine :{E} {R}{r.get('root_cause','')}{E}")
    print(f"  {W}Action       :{E} {G}{r.get('fix_action','')}{E}")

    related = r.get("related_tcs", [])
    if related:
        print(f"  {W}TCs liés     :{E} {Y}{', '.join(related)}{E}")

    if show_cot and r.get("cot_reasoning"):
        print(f"\n  {C}── Raisonnement CoT (ÉTAPE 1) ──────────────{E}")
        for line in r["cot_reasoning"].split("\n"):
            if re.match(r"\s*ÉTAPE\s*\d", line, re.IGNORECASE):
                print(f"  {Y}{line}{E}")
            elif re.match(r"\s*CONCLUSION", line, re.IGNORECASE):
                print(f"  {G}{line}{E}")
            elif line.strip():
                print(f"  {line}")


def print_header(title: str):
    print(f"\n{W}{'='*58}{E}")
    print(f"{W}  {title}{E}")
    print(f"{W}{'='*58}{E}")


# ── Groupement par cause racine commune ───────────────────────────────────

def group_by_root_cause(rcas: list) -> dict:
    """Groupe les RCAs qui partagent la même catégorie et couche."""
    groups = {}
    for r in rcas:
        key = f"{r.get('cause_category','?')}::{r.get('affected_layer','?')}"
        groups.setdefault(key, []).append(r)
    return dict(sorted(groups.items(), key=lambda x: -len(x[1])))


# ── Commandes ──────────────────────────────────────────────────────────────

def cmd_analyse(show_cot: bool = False) -> list:
    print_header("RCA AGENT — Root Cause Analysis (Chain of Thought)")
    print(f"{Y}  CoT = raisonnement multi-étapes avant conclusion{E}\n")

    failures = load_failures()
    if not failures:
        print(f"{G}  Aucun échec dans allure-results.{E}")
        return []

    all_tcs = [f["tc"] for f in failures if f.get("tc")]
    print(f"  {len(failures)} échec(s) à analyser | TCs : {', '.join(all_tcs)}\n")

    rcas = []
    for i, f in enumerate(failures, 1):
        print(f"  {C}[{i}/{len(failures)}]{E} RCA CoT pour {f['tc'] or f['name'][:35]}...", flush=True)
        r = run_cot_rca(f, all_tcs)
        rcas.append(r)
        print_rca(r, show_cot=show_cot)

    return rcas


def cmd_group() -> list:
    rcas = cmd_analyse()
    if not rcas:
        return []

    groups = group_by_root_cause(rcas)

    print_header("GROUPEMENT PAR CAUSE RACINE COMMUNE")
    for key, items in groups.items():
        cat, layer = key.split("::")
        color = CATEGORY_COLORS.get(cat, Y)
        print(f"\n  {color}{W}[{cat.upper()} / {layer}]{E}  → {len(items)} TC(s) affectés")
        for r in items:
            print(f"    {R}✗{E} {r.get('tc','?'):>8}  {r['name'][:50]}")
        # Cause racine commune (celle du TC avec le plus de related_tcs)
        representative = max(items, key=lambda x: len(x.get("related_tcs", [])))
        print(f"    {W}Cause commune :{E} {representative.get('root_cause','')[:90]}")
        print(f"    {W}Action         :{E} {representative.get('fix_action','')[:90]}")

    return rcas


def cmd_single(tc_id: str):
    print_header(f"RCA AGENT — Analyse de {tc_id}")
    failures = load_failures(tc_filter=tc_id)
    if not failures:
        print(f"{R}  TC {tc_id} introuvable ou non en échec.{E}")
        return

    all_tcs = [f["tc"] for f in load_failures() if f.get("tc")]
    r = run_cot_rca(failures[0], all_tcs)
    print_rca(r, show_cot=True)  # Affiche le CoT complet pour un seul TC


# ── Rapport HTML ───────────────────────────────────────────────────────────

def cmd_report():
    rcas = cmd_analyse()
    if not rcas:
        return

    groups = group_by_root_cause(rcas)

    CAT_COLORS_HTML = {
        "assertion": "#e74c3c", "auth": "#e67e22", "data": "#3498db",
        "network": "#9b59b6", "config": "#e67e22", "fixture": "#f39c12",
        "logic": "#c0392b", "unknown": "#95a5a6",
    }
    PRIO_COLORS_HTML = {
        "immediate": "#e74c3c", "high": "#e67e22", "medium": "#3498db", "low": "#27ae60"
    }

    rows = ""
    for r in sorted(rcas, key=lambda x: ("immediate","high","medium","low").index(x.get("fix_priority","medium")) if x.get("fix_priority") in ("immediate","high","medium","low") else 3):
        cat   = r.get("cause_category", "unknown")
        prio  = r.get("fix_priority",   "medium")
        chain_html = " → ".join(r.get("chain", []))
        related_html = ", ".join(r.get("related_tcs", [])) or "—"
        rows += f"""
        <tr>
          <td style="font-family:monospace">{r.get('tc','—')}</td>
          <td style="font-size:12px">{r['name'][:55]}</td>
          <td><span style="background:{CAT_COLORS_HTML.get(cat,'#95a5a6')};color:#fff;padding:2px 7px;border-radius:3px;font-size:11px">{cat}</span></td>
          <td style="font-size:11px;color:#555">{chain_html[:100]}</td>
          <td style="font-size:12px">{r.get('root_cause','')[:70]}</td>
          <td style="font-size:12px;color:#27ae60">{r.get('fix_action','')[:70]}</td>
          <td><span style="background:{PRIO_COLORS_HTML.get(prio,'#3498db')};color:#fff;padding:2px 7px;border-radius:3px;font-size:11px">{prio}</span></td>
          <td style="font-family:monospace;font-size:11px;color:#e67e22">{related_html}</td>
        </tr>"""

    groups_html = ""
    for key, items in groups.items():
        cat, layer = key.split("::")
        rep = max(items, key=lambda x: len(x.get("related_tcs", [])))
        tcs_html = " ".join([f'<code style="background:#f0f0f0;padding:1px 5px;border-radius:3px">{r.get("tc","?")}</code>' for r in items])
        groups_html += f"""
        <div style="background:#fff;border-left:4px solid {CAT_COLORS_HTML.get(cat,'#95a5a6')};padding:12px 15px;margin:8px 0;border-radius:0 8px 8px 0;box-shadow:0 1px 4px rgba(0,0,0,.08)">
          <b style="color:{CAT_COLORS_HTML.get(cat,'#333')}">{cat.upper()} / {layer}</b>
          <span style="background:#eee;padding:1px 8px;border-radius:10px;font-size:12px;margin-left:8px">{len(items)} TC(s)</span><br>
          <div style="margin:6px 0">{tcs_html}</div>
          <div style="font-size:13px"><b>Cause :</b> {rep.get('root_cause','')}</div>
          <div style="font-size:13px;color:#27ae60"><b>Action :</b> {rep.get('fix_action','')}</div>
        </div>"""

    nb_immediate = sum(1 for r in rcas if r.get("fix_priority") == "immediate")
    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>RCA Agent — Root Cause Analysis</title>
<style>
  body{{font-family:Arial,sans-serif;background:#f5f5f5;color:#333;margin:0;padding:20px}}
  h1{{color:#2c3e50}} h2{{color:#34495e;margin-top:30px}}
  .stat{{display:inline-block;background:#fff;border-radius:8px;padding:15px 25px;margin:8px;box-shadow:0 2px 6px rgba(0,0,0,.1);text-align:center}}
  .stat-val{{font-size:28px;font-weight:bold}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1);margin-top:15px}}
  th{{background:#2c3e50;color:#fff;padding:10px;text-align:left;font-size:12px}}
  td{{padding:8px 10px;border-bottom:1px solid #ecf0f1;vertical-align:top}}
  tr:hover{{background:#f8f9fa}}
  code{{font-family:monospace}}
</style>
</head>
<body>
<h1>RCA Agent — Root Cause Analysis (Chain of Thought)</h1>
<p style="color:#666">Chain of Thought : le LLM raisonne en 3 étapes avant de conclure → chaîne causale traçable</p>

<div>
  <div class="stat"><div class="stat-val" style="color:#e74c3c">{len(rcas)}</div>Échecs analysés</div>
  <div class="stat"><div class="stat-val" style="color:#e74c3c">{nb_immediate}</div>Priorité Immédiate</div>
  <div class="stat"><div class="stat-val" style="color:#3498db">{len(groups)}</div>Causes racines distinctes</div>
</div>

<h2>Causes racines communes</h2>
{groups_html}

<h2>Détail par TC</h2>
<table>
  <tr><th>TC</th><th>Test</th><th>Catégorie</th><th>Chaîne causale</th><th>Cause racine</th><th>Action corrective</th><th>Priorité</th><th>TCs liés</th></tr>
  {rows}
</table>

<p style="color:#999;font-size:12px;margin-top:30px">
  Généré par RCA Agent — Chain of Thought (ÉTAPE 1→2→CONCLUSION)
</p>
</body>
</html>"""

    out = os.path.join(DOCS_DIR, "rca-report.html")
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n{G}  Rapport HTML : docs/rca-report.html{E}")


def print_help():
    print(f"""
{W}RCA AGENT — Root Cause Analysis avec Chain of Thought{E}

  python agents/rca-agent.py analyse          RCA de tous les échecs
  python agents/rca-agent.py group            Groupement par cause racine commune
  python agents/rca-agent.py single TC-023    RCA d'un seul TC (CoT visible)
  python agents/rca-agent.py report           Rapport HTML complet

{W}Différence vs bug-analyzer.py :{E}
  bug-analyzer  → llm.chat() simple, un échec, propose un patch code
  rca-agent     → CoT multi-étapes, groupe les failures liées,
                  remonte la chaîne causale, identifie les TCs impactés

{W}Chain of Thought — les 3 étapes forcées :{E}
  ÉTAPE 1  Analyse les données brutes (message, trace, status)
  ÉTAPE 2  Identifie les patterns et la chaîne d'événements
  CONCLUSION  Cause racine + action corrective précise
""")


# ── Main ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "analyse":
        cmd_analyse()
    elif cmd == "group":
        cmd_group()
    elif cmd == "single" and len(sys.argv) > 2:
        cmd_single(sys.argv[2])
    elif cmd == "report":
        cmd_report()
    else:
        print_help()
