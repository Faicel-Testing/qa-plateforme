# ============================================================
# Prompt Versioning Agent — Gestion des versions de prompts LLM
# ============================================================
# Comme Git pour le code, cet agent versionne les prompts LLM.
# Permet de comparer, rollback, et A/B tester les prompts.
#
# Usage:
#   python agents/prompt-versioning-agent.py list              → tous les prompts
#   python agents/prompt-versioning-agent.py history <name>    → versions d'un prompt
#   python agents/prompt-versioning-agent.py diff <name> <v1> <v2>
#   python agents/prompt-versioning-agent.py promote <name> <version>
#   python agents/prompt-versioning-agent.py rollback <name>
#   python agents/prompt-versioning-agent.py ab-test <name>    → A/B test v_current vs v_prev
#   python agents/prompt-versioning-agent.py init              → crée les prompts de base
#   python agents/prompt-versioning-agent.py report            → rapport HTML
# ============================================================

import sys, os, json, glob, re, difflib
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm
from prompt_store import PromptStore

FRAMEWORK   = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS_DIR = os.path.join(FRAMEWORK, "allure-results")
DOCS_DIR    = os.path.join(FRAMEWORK, "docs")

store = PromptStore()

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"


# ── Prompts de base du framework ──────────────────────────────────────────
# Ces prompts sont utilisés par les agents existants.
# Les versionner ici permet de les améliorer sans risque.

BASE_PROMPTS = {
    "triage_classify": {
        "description": "Classifie un échec de test (triage-agent)",
        "agent":       "triage-agent",
        "tags":        ["classification", "triage"],
        "content": (
            "Tu es un expert QA. Analyse cet échec de test API et classe-le "
            "dans UNE seule catégorie : real_bug, flaky, env_issue, false_positive.\n"
            "Donne un score de confiance entre 0.0 et 1.0."
        ),
    },
    "rca_analysis": {
        "description": "Root Cause Analysis d'un échec (rca-agent)",
        "agent":       "rca-agent",
        "tags":        ["rca", "analysis"],
        "content": (
            "Tu es un expert QA. Effectue une analyse Root Cause Analysis (RCA) "
            "de cet échec de test API. Identifie la chaîne causale complète : "
            "symptôme → cause intermédiaire → cause racine. "
            "Propose une action corrective précise et vérifiable."
        ),
    },
    "release_decision": {
        "description": "Décision Go/No-Go de déploiement (release-advisor-agent)",
        "agent":       "release-advisor-agent",
        "tags":        ["release", "decision", "self-consistency"],
        "content": (
            "Tu es un expert QA chargé de valider les mises en production. "
            "Analyse ces résultats de tests et décide si on peut déployer en production. "
            "Sois strict : un seul test critique en échec = NO-GO."
        ),
    },
    "bug_patch": {
        "description": "Génération de patch correctif (bug-analyzer)",
        "agent":       "bug-analyzer",
        "tags":        ["fix", "patch"],
        "content": (
            "Tu es un expert Python / pytest-bdd. Analyse cet échec et génère "
            "un correctif précis pour le fichier de step definitions. "
            "Le patch doit être minimal et non destructif."
        ),
    },
    "coverage_suggest": {
        "description": "Suggestion de nouveaux cas de test (coverage-agent)",
        "agent":       "coverage-agent",
        "tags":        ["coverage", "suggestion"],
        "content": (
            "Tu es un expert QA API. Analyse les types de test manquants pour cet endpoint "
            "et propose des scénarios Gherkin BDD précis, testables et non triviaux. "
            "Chaque scénario doit couvrir un cas réel susceptible de trouver un bug."
        ),
    },
}


# ── Helpers ────────────────────────────────────────────────────────────────

def print_header(title: str):
    print(f"\n{W}{'='*60}{E}")
    print(f"{W}  {title}{E}")
    print(f"{W}{'='*60}{E}")

def confidence_color(c):
    if c is None: return Y
    return G if c >= 0.8 else Y if c >= 0.65 else R

def _load_sample_failure() -> dict | None:
    """Charge un exemple d'échec depuis allure-results pour l'A/B test."""
    for f in glob.glob(os.path.join(RESULTS_DIR, "*-result.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
            if d.get("status") in ("failed", "broken"):
                detail = d.get("statusDetails") or {}
                tags   = [lb["value"] for lb in d.get("labels",[]) if lb["name"]=="tag"]
                tc     = next((t for t in tags if re.match(r"tc-\d+",t)), "TC-?")
                return {
                    "name":    d.get("name","?"),
                    "tc":      tc,
                    "status":  d.get("status"),
                    "message": detail.get("message","")[:300],
                    "trace":   detail.get("trace","")[:300],
                }
        except Exception:
            pass
    return None


# ── Commandes ──────────────────────────────────────────────────────────────

def cmd_init():
    """Initialise les prompts de base du framework."""
    print_header("INITIALISATION DES PROMPTS DE BASE")
    created = 0
    skipped = 0
    for name, meta in BASE_PROMPTS.items():
        try:
            version = store.create(
                name        = name,
                content     = meta["content"],
                description = meta["description"],
                agent       = meta["agent"],
                tags        = meta["tags"],
            )
            print(f"  {G}✓{E}  {name:<30} v{version}  créé")
            created += 1
        except ValueError:
            print(f"  {Y}={E}  {name:<30} déjà existant — ignoré")
            skipped += 1
    print(f"\n  {G}{created} créé(s){E}  |  {Y}{skipped} ignoré(s){E}")


def cmd_list():
    print_header("PROMPTS VERSIONNÉS — LISTE COMPLÈTE")
    prompts = store.list_all()
    if not prompts:
        print(f"{Y}  Aucun prompt. Lance : python agents/prompt-versioning-agent.py init{E}")
        return

    print(f"  {W}{'Nom':<30} {'Version':>8} {'Versions':>9} {'Agent':<25} {'Confiance':>10}{E}")
    print(f"  {'-'*85}")
    for p in prompts:
        m    = p.get("metrics", {})
        conf = m.get("avg_confidence")
        cc   = confidence_color(conf)
        conf_str = f"{int(conf*100)}%" if conf else "—"
        calls    = m.get("calls", 0)
        print(f"  {C}{p['name']:<30}{E} {Y}v{p['current_version']:>7}{E} "
              f"{p['nb_versions']:>9}  {p['agent']:<25} "
              f"{cc}{conf_str:>9}{E}  ({calls} calls)")


def cmd_history(name: str):
    print_header(f"HISTORIQUE — {name}")
    versions = store.list_versions(name)
    if not versions:
        print(f"{R}  Prompt '{name}' introuvable.{E}")
        return

    for v in versions:
        current_tag = f" {G}{W}← ACTIF{E}" if v["is_current"] else ""
        print(f"\n  {Y}v{v['version']}{E}{current_tag}")
        print(f"  {v['created_at'][:19]}  —  {v.get('note','')}")
        # Aperçu du contenu (50 premiers chars)
        preview = v["content"][:80].replace("\n", " ")
        print(f"  {C}\"{preview}...\" {E}")


def cmd_diff(name: str, v1: str, v2: str):
    print_header(f"DIFF — {name}  v{v1} → v{v2}")

    c1 = store.get(name, v1)
    c2 = store.get(name, v2)
    if not c1:
        print(f"{R}  Version {v1} introuvable.{E}"); return
    if not c2:
        print(f"{R}  Version {v2} introuvable.{E}"); return

    diff = list(difflib.unified_diff(
        c1.splitlines(keepends=True),
        c2.splitlines(keepends=True),
        fromfile=f"v{v1}", tofile=f"v{v2}", lineterm=""
    ))

    if not diff:
        print(f"{G}  Les deux versions sont identiques.{E}")
        return

    for line in diff:
        if line.startswith("+") and not line.startswith("+++"):
            print(f"  {G}{line.rstrip()}{E}")
        elif line.startswith("-") and not line.startswith("---"):
            print(f"  {R}{line.rstrip()}{E}")
        elif line.startswith("@@"):
            print(f"  {C}{line.rstrip()}{E}")
        else:
            print(f"  {line.rstrip()}")


def cmd_promote(name: str, version: str):
    try:
        store.promote(name, version)
        print(f"{G}  ✓ '{name}' → version active : v{version}{E}")
    except ValueError as e:
        print(f"{R}  Erreur : {e}{E}")


def cmd_rollback(name: str):
    try:
        prev = store.rollback(name)
        print(f"{G}  ✓ '{name}' rollback → v{prev}{E}")
    except ValueError as e:
        print(f"{R}  Erreur : {e}{E}")


def cmd_ab_test(name: str):
    """
    A/B test : compare la version active vs la version précédente
    sur le même échantillon de données réelles.
    """
    print_header(f"A/B TEST — {name}")

    versions = store.list_versions(name)
    if len(versions) < 2:
        print(f"{Y}  Besoin d'au moins 2 versions pour un A/B test.{E}")
        return

    # Versions A (active) et B (précédente)
    current = store.get_meta(name)["current_version"]
    all_versions = [v["version"] for v in versions]
    current_idx  = all_versions.index(current)
    prev_version = all_versions[current_idx - 1] if current_idx > 0 else all_versions[-2]

    content_a = store.get(name, current)
    content_b = store.get(name, prev_version)

    print(f"  Version A (active)    : {G}v{current}{E}")
    print(f"  Version B (précédente): {Y}v{prev_version}{E}")

    # Données de test (failure réelle ou synthétique)
    sample = _load_sample_failure()
    if not sample:
        sample = {
            "name":    "test_tc023__delete_booking_without_token",
            "tc":      "tc-023",
            "status":  "failed",
            "message": "assert 403 == 201\nAssertionError: status code incorrect",
            "trace":   "tests/test_booking_delete_bdd.py:45",
        }
        print(f"  {Y}Aucun échec réel — utilisation d'un exemple synthétique{E}")
    else:
        print(f"  {C}Données réelles : [{sample['tc']}] {sample['name'][:45]}{E}")

    test_context = (
        f"Test : {sample['name']}\n"
        f"TC   : {sample['tc']} | Statut : {sample['status']}\n"
        f"Erreur : {sample['message'][:200]}\n"
        f"Trace  : {sample['trace'][:150]}"
    )

    schema = {
        "verdict":    "string — résultat de l'analyse",
        "confidence": "float entre 0.0 et 1.0",
        "reasoning":  "string — raisonnement court"
    }

    print(f"\n{C}  Appel A (v{current})...{E}", end=" ", flush=True)
    result_a = llm.chat_structured(
        [{"role": "system", "content": content_a},
         {"role": "user",   "content": test_context}],
        schema
    )
    store.record_usage(name, result_a.get("confidence"))
    conf_a = result_a.get("confidence", 0)
    print(f"{G if conf_a >= 0.75 else Y}{int(conf_a*100)}% confiance{E}")

    print(f"{C}  Appel B (v{prev_version})...{E}", end=" ", flush=True)
    result_b = llm.chat_structured(
        [{"role": "system", "content": content_b},
         {"role": "user",   "content": test_context}],
        schema
    )
    conf_b = result_b.get("confidence", 0)
    print(f"{G if conf_b >= 0.75 else Y}{int(conf_b*100)}% confiance{E}")

    # Résultat
    winner = "A" if conf_a >= conf_b else "B"
    winner_version = current if winner == "A" else prev_version
    diff_pct = abs(conf_a - conf_b) * 100

    print(f"\n  {W}Résultats A/B :{E}")
    print(f"  {G}v{current:<8}{E} (A)  confiance = {int(conf_a*100)}%  |  {result_a.get('verdict','?')[:50]}")
    print(f"  {Y}v{prev_version:<8}{E} (B)  confiance = {int(conf_b*100)}%  |  {result_b.get('verdict','?')[:50]}")
    print(f"\n  {W}Vainqueur : Version {winner} (v{winner_version}){E}  "
          f"[+{diff_pct:.1f}% confiance]")

    if winner == "B":
        print(f"\n  {Y}⚠ La version précédente (B) performe mieux.{E}")
        print(f"  Rollback recommandé : python agents/prompt-versioning-agent.py rollback {name}")
    else:
        print(f"\n  {G}✓ La version active (A) est meilleure — aucun changement nécessaire.{E}")

    return {"winner": winner, "conf_a": conf_a, "conf_b": conf_b,
            "version_a": current, "version_b": prev_version}


# ── Rapport HTML ───────────────────────────────────────────────────────────

def cmd_report():
    prompts = store.list_all()
    if not prompts:
        print(f"{Y}  Aucun prompt. Lance init d'abord.{E}")
        return

    rows = ""
    for p in prompts:
        m    = p.get("metrics", {})
        conf = m.get("avg_confidence")
        conf_color = "#27ae60" if conf and conf>=0.8 else "#e67e22" if conf and conf>=0.65 else "#e74c3c" if conf else "#888"
        conf_str   = f"{int(conf*100)}%" if conf else "—"
        calls_str  = str(m.get("calls", 0))
        last_used  = (m.get("last_used") or "—")[:10]
        versions   = store.list_versions(p["name"])
        history_html = "".join([
            f'<span title="{v.get(\"note\",\"\")}  {v[\"created_at\"][:10]}" '
            f'style="background:{"#2c3e50" if v["is_current"] else "#ecf0f1"};'
            f'color:{"#fff" if v["is_current"] else "#555"};'
            f'padding:2px 7px;border-radius:3px;font-size:11px;margin:1px;display:inline-block">'
            f'v{v["version"]}</span>'
            for v in versions
        ])
        tags_html = " ".join([
            f'<span style="background:#3498db;color:#fff;padding:1px 6px;border-radius:3px;font-size:11px">{t}</span>'
            for t in p.get("tags",[]) or store.get_meta(p["name"]).get("tags",[])
        ])
        rows += f"""
        <tr>
          <td><b style="color:#2c3e50">{p['name']}</b><br><small style="color:#888">{p['description'][:60]}</small></td>
          <td style="font-family:monospace;color:#e67e22">v{p['current_version']}</td>
          <td>{history_html}</td>
          <td style="text-align:center;color:{conf_color};font-weight:bold">{conf_str}</td>
          <td style="text-align:center">{calls_str}</td>
          <td style="color:#3498db">{p['agent']}</td>
          <td>{tags_html}</td>
          <td style="color:#888;font-size:12px">{last_used}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Prompt Versioning — Dashboard</title>
<style>
  body{{font-family:Arial,sans-serif;background:#f0f2f5;color:#333;margin:0;padding:20px}}
  h1{{color:#2c3e50}} h2{{color:#34495e;margin-top:30px}}
  .stat{{display:inline-block;background:#fff;border-radius:10px;padding:15px 25px;
         margin:8px;box-shadow:0 2px 8px rgba(0,0,0,.1);text-align:center}}
  .stat-val{{font-size:28px;font-weight:bold}} .stat-lbl{{font-size:12px;color:#888}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;
         overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1);margin-top:12px}}
  th{{background:#2c3e50;color:#fff;padding:10px 12px;text-align:left;font-size:12px}}
  td{{padding:10px 12px;border-bottom:1px solid #ecf0f1;vertical-align:middle}}
  tr:hover{{background:#f8f9fa}}
</style>
</head>
<body>
<h1>Prompt Versioning — Dashboard</h1>
<p style="color:#666">Comme Git pour le code — chaque prompt a un historique, un diff, et un A/B test possible.</p>

<div>
  <div class="stat"><div class="stat-val" style="color:#3498db">{len(prompts)}</div><div class="stat-lbl">Prompts versionnés</div></div>
  <div class="stat"><div class="stat-val" style="color:#9b59b6">{sum(p['nb_versions'] for p in prompts)}</div><div class="stat-lbl">Versions totales</div></div>
  <div class="stat"><div class="stat-val" style="color:#27ae60">{sum(p.get('metrics',{{}}).get('calls',0) for p in prompts)}</div><div class="stat-lbl">Utilisations totales</div></div>
</div>

<h2>Tous les prompts</h2>
<table>
  <tr><th>Prompt</th><th>Actif</th><th>Historique</th><th>Conf. moy.</th><th>Calls</th><th>Agent</th><th>Tags</th><th>Dernier usage</th></tr>
  {rows}
</table>

<h2>Commandes CLI</h2>
<pre style="background:#2c3e50;color:#a8ff78;padding:15px;border-radius:8px;font-size:13px">
python agents/prompt-versioning-agent.py init               # crée les prompts de base
python agents/prompt-versioning-agent.py list               # liste tous les prompts
python agents/prompt-versioning-agent.py history triage_classify
python agents/prompt-versioning-agent.py diff triage_classify 1.0.0 1.1.0
python agents/prompt-versioning-agent.py ab-test triage_classify
python agents/prompt-versioning-agent.py rollback triage_classify
python agents/prompt-versioning-agent.py promote triage_classify 1.0.0
</pre>

<p style="color:#999;font-size:12px;margin-top:30px">
  Généré par Prompt Versioning Agent | {len(prompts)} prompts | prompts/*.json
</p>
</body>
</html>"""

    out = os.path.join(DOCS_DIR, "prompt-versioning-report.html")
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n{G}  Dashboard HTML : docs/prompt-versioning-report.html{E}")


def print_help():
    print(f"""
{W}PROMPT VERSIONING AGENT — Gestion des versions de prompts LLM{E}

  python agents/prompt-versioning-agent.py init                    Crée les prompts de base
  python agents/prompt-versioning-agent.py list                    Liste tous les prompts
  python agents/prompt-versioning-agent.py history <name>          Historique d'un prompt
  python agents/prompt-versioning-agent.py diff <name> <v1> <v2>  Diff entre 2 versions
  python agents/prompt-versioning-agent.py promote <name> <v>     Active une version
  python agents/prompt-versioning-agent.py rollback <name>         Revient à la version précédente
  python agents/prompt-versioning-agent.py ab-test <name>          A/B test actif vs précédent
  python agents/prompt-versioning-agent.py report                  Dashboard HTML

{W}Prompts disponibles :{E}
  triage_classify    release_decision    rca_analysis
  bug_patch          coverage_suggest

{W}Comme Git pour les prompts :{E}
  Chaque save() crée une nouvelle version (semver auto-bump).
  rollback() revient en arrière. ab-test() compare sur données réelles.
""")


if __name__ == "__main__":
    args = sys.argv[1:]
    cmd  = args[0] if args else "help"

    if cmd == "init":
        cmd_init()
    elif cmd == "list":
        cmd_list()
    elif cmd == "history" and len(args) >= 2:
        cmd_history(args[1])
    elif cmd == "diff" and len(args) >= 4:
        cmd_diff(args[1], args[2], args[3])
    elif cmd == "promote" and len(args) >= 3:
        cmd_promote(args[1], args[2])
    elif cmd == "rollback" and len(args) >= 2:
        cmd_rollback(args[1])
    elif cmd == "ab-test" and len(args) >= 2:
        cmd_ab_test(args[1])
    elif cmd == "report":
        cmd_report()
    else:
        print_help()
