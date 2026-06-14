# ============================================================
# RCA Agent — Root Cause Analysis Mobile (Chain of Thought)
# ============================================================
# Chain of Thought multi-étapes, groupe les failures liées,
# remonte la chaîne causale spécifique Appium/Android.
#
# Catégories causales mobiles :
#   locator    → AppiumBy incorrect, UI selector invalide
#   app_crash  → App killed, WebDriverException, session perdue
#   timeout    → Wait trop court, animation, device lent
#   device     → Émulateur instable, ADB disconnect
#   assertion  → Valeur attendue incorrecte dans le test
#   data       → Données de test incorrectes (config.properties)
#   unknown    → Cause non identifiable
#
# Usage:
#   python agents/rca-agent.py analyse      → RCA de tous les échecs
#   python agents/rca-agent.py group        → groupe par cause racine
#   python agents/rca-agent.py report       → rapport HTML
#   python agents/rca-agent.py single Test03_AddTodo → RCA d'un seul test
# ============================================================

import sys, os, json, glob
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm

FRAMEWORK   = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS_DIR = os.path.join(FRAMEWORK, "target", "allure-results")
DOCS_DIR    = os.path.join(FRAMEWORK, "docs")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

RCA_SCHEMA = {
    "root_cause":     "string — cause racine identifiée (1 phrase précise)",
    "cause_category": "locator | app_crash | timeout | device | assertion | data | unknown",
    "chain":          ["symptôme", "cause intermédiaire", "cause racine"],
    "affected_layer": "page_object | test_code | app | device | config",
    "fix_action":     "string — action corrective concrète à réaliser",
    "fix_priority":   "immediate | high | medium | low",
    "related_tests":  ["liste des autres noms de tests probablement affectés par la même cause"]
}

CATEGORY_COLORS = {
    "locator":    R,
    "app_crash":  R,
    "timeout":    Y,
    "device":     C,
    "assertion":  Y,
    "data":       C,
    "unknown":    Y,
}

PRIORITY_COLORS = {
    "immediate": R,
    "high":      Y,
    "medium":    C,
    "low":       G,
}

CAT_COLORS_HTML = {
    "locator":    "#e74c3c",
    "app_crash":  "#c0392b",
    "timeout":    "#e67e22",
    "device":     "#3498db",
    "assertion":  "#f39c12",
    "data":       "#9b59b6",
    "unknown":    "#95a5a6",
}


# ── Chargement des échecs Allure ───────────────────────────────────────────

def load_failures(class_filter: str = None) -> list:
    failures = []
    for f in glob.glob(os.path.join(RESULTS_DIR, "*-result.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
            if d.get("status") not in ("failed", "broken"):
                continue

            labels     = d.get("labels", [])
            test_class = next((lb["value"] for lb in labels if lb["name"] == "testClass"), "?")
            short_cls  = test_class.split(".")[-1] if "." in test_class else test_class
            groups     = [lb["value"] for lb in labels if lb["name"] == "tag"]

            if class_filter and class_filter.lower() not in short_cls.lower():
                continue

            detail = d.get("statusDetails") or {}
            failures.append({
                "name":       d.get("name", "?"),
                "test_class": short_cls,
                "status":     d.get("status"),
                "groups":     groups,
                "message":    detail.get("message", "")[:500],
                "trace":      detail.get("trace",   "")[:600],
            })
        except Exception:
            pass
    return failures


# ── Chain of Thought RCA ───────────────────────────────────────────────────

def run_cot_rca(failure: dict, all_tests: list) -> dict:
    other = [t for t in all_tests if t != failure["name"]]

    cot_messages = [{
        "role": "user",
        "content": (
            f"Effectue une analyse Root Cause Analysis (RCA) de cet échec de test mobile Appium/Android :\n\n"
            f"Test         : {failure['name']}\n"
            f"Classe       : {failure['test_class']}\n"
            f"Groups       : {failure['groups']}\n"
            f"Statut       : {failure['status']}\n"
            f"Erreur       : {failure['message'] or 'aucun message'}\n"
            f"Stack trace  :\n{failure['trace'] or 'aucune trace'}\n\n"
            f"Autres tests en échec dans la même session : {other}\n\n"
            f"Contexte : App Android (QAcart-To-Do.apk), framework Appium 9.2.2 + TestNG 7.10.2.\n"
            f"Les page objects utilisent AppiumBy.androidUIAutomator() et AppiumBy.className()."
        )
    }]
    cot_reasoning = llm.chat_cot(cot_messages)

    struct_messages = [{
        "role": "user",
        "content": (
            f"Sur la base de cette analyse RCA :\n\n{cot_reasoning}\n\n"
            f"Extrais les informations structurées. "
            f"Pour related_tests, liste les tests de cette liste pouvant partager la même cause : {other}"
        )
    }]
    structured = llm.chat_structured(struct_messages, RCA_SCHEMA)

    return {**failure, **structured, "cot_reasoning": cot_reasoning}


# ── Affichage ──────────────────────────────────────────────────────────────

def print_rca(r: dict, show_cot: bool = False):
    cat_color  = CATEGORY_COLORS.get(r.get("cause_category", "unknown"), Y)
    prio_color = PRIORITY_COLORS.get(r.get("fix_priority", "medium"), Y)

    print(f"\n  {W}{'─'*54}{E}")
    print(f"  {W}{r['test_class']:>25}{E}  {r['name'][:30]}")
    print(f"  Catégorie : {cat_color}{W}{r.get('cause_category','?'):<14}{E}  Couche : {r.get('affected_layer','?')}")
    print(f"  Priorité  : {prio_color}{W}{r.get('fix_priority','?'):<10}{E}")

    chain = r.get("chain", [])
    if chain:
        print(f"\n  {W}Chaîne causale :{E}")
        for i, step in enumerate(chain):
            arrow = "  └─" if i == len(chain) - 1 else "  ├─"
            color = R if i == len(chain) - 1 else C
            print(f"{arrow} {color}{step}{E}")

    print(f"\n  {W}Cause racine :{E} {R}{r.get('root_cause','')}{E}")
    print(f"  {W}Action       :{E} {G}{r.get('fix_action','')}{E}")

    related = r.get("related_tests", [])
    if related:
        print(f"  {W}Tests liés   :{E} {Y}{', '.join(related)}{E}")

    if show_cot and r.get("cot_reasoning"):
        print(f"\n  {C}── Raisonnement CoT ──────────────────────────────{E}")
        for line in r["cot_reasoning"].split("\n"):
            if "ÉTAPE" in line.upper():
                print(f"  {Y}{line}{E}")
            elif "CONCLUSION" in line.upper():
                print(f"  {G}{line}{E}")
            elif line.strip():
                print(f"  {line}")


# ── Commandes ──────────────────────────────────────────────────────────────

def cmd_analyse(show_cot: bool = False) -> list:
    print(f"\n{W}RCA AGENT MOBILE — Chain of Thought{E}")
    print(f"{C}Source : target/allure-results/{E}\n")

    failures = load_failures()
    if not failures:
        print(f"{G}  Aucun échec dans target/allure-results/.{E}")
        return []

    all_tests = [f["name"] for f in failures]
    print(f"  {len(failures)} échec(s) à analyser\n")

    rcas = []
    for i, f in enumerate(failures, 1):
        print(f"  {C}[{i}/{len(failures)}]{E} RCA CoT pour {f['test_class']}.{f['name'][:25]}...", flush=True)
        r = run_cot_rca(f, all_tests)
        rcas.append(r)
        print_rca(r, show_cot=show_cot)

    return rcas


def cmd_group() -> list:
    rcas = cmd_analyse()
    if not rcas:
        return []

    groups = {}
    for r in rcas:
        key = f"{r.get('cause_category','?')}::{r.get('affected_layer','?')}"
        groups.setdefault(key, []).append(r)
    groups = dict(sorted(groups.items(), key=lambda x: -len(x[1])))

    print(f"\n{W}{'='*58}{E}")
    print(f"{W}  GROUPEMENT PAR CAUSE RACINE COMMUNE{E}")
    print(f"{W}{'='*58}{E}")
    for key, items in groups.items():
        cat, layer = key.split("::")
        color = CATEGORY_COLORS.get(cat, Y)
        print(f"\n  {color}{W}[{cat.upper()} / {layer}]{E}  → {len(items)} test(s) affecté(s)")
        for r in items:
            print(f"    {R}✗{E} {r['test_class']}.{r['name'][:45]}")
        rep = max(items, key=lambda x: len(x.get("related_tests", [])))
        print(f"    {W}Cause   :{E} {rep.get('root_cause','')[:90]}")
        print(f"    {W}Action  :{E} {rep.get('fix_action','')[:90]}")
    return rcas


def cmd_single(class_name: str):
    print(f"\n{W}RCA AGENT — Analyse de {class_name}{E}")
    failures = load_failures(class_filter=class_name)
    if not failures:
        print(f"{R}  Test '{class_name}' introuvable ou non en échec.{E}")
        return
    all_tests = [f["name"] for f in load_failures()]
    r = run_cot_rca(failures[0], all_tests)
    print_rca(r, show_cot=True)


def cmd_report():
    rcas = cmd_analyse()
    if not rcas:
        return

    groups = {}
    for r in rcas:
        key = f"{r.get('cause_category','?')}::{r.get('affected_layer','?')}"
        groups.setdefault(key, []).append(r)

    PRIO = {"immediate": 0, "high": 1, "medium": 2, "low": 3}
    PRIO_HTML = {"immediate": "#e74c3c", "high": "#e67e22", "medium": "#3498db", "low": "#27ae60"}

    rows = ""
    for r in sorted(rcas, key=lambda x: PRIO.get(x.get("fix_priority","medium"), 2)):
        cat   = r.get("cause_category", "unknown")
        prio  = r.get("fix_priority", "medium")
        chain_html = " → ".join(r.get("chain", []))
        related_html = ", ".join(r.get("related_tests", [])) or "—"
        rows += f"""
        <tr>
          <td style="font-family:monospace;font-size:11px">{r['test_class']}</td>
          <td style="font-size:12px">{r['name'][:45]}</td>
          <td><span style="background:{CAT_COLORS_HTML.get(cat,'#95a5a6')};color:#fff;padding:2px 7px;border-radius:3px;font-size:11px">{cat}</span></td>
          <td style="font-size:11px;color:#555">{chain_html[:100]}</td>
          <td style="font-size:12px">{r.get('root_cause','')[:60]}</td>
          <td style="font-size:12px;color:#27ae60">{r.get('fix_action','')[:60]}</td>
          <td><span style="background:{PRIO_HTML.get(prio,'#3498db')};color:#fff;padding:2px 7px;border-radius:3px;font-size:11px">{prio}</span></td>
          <td style="font-size:11px;color:#e67e22">{related_html}</td>
        </tr>"""

    groups_html = ""
    for key, items in sorted(groups.items(), key=lambda x: -len(x[1])):
        cat, layer = key.split("::")
        rep  = max(items, key=lambda x: len(x.get("related_tests", [])))
        tcs  = " ".join([f'<code style="background:#f0f0f0;padding:1px 5px;border-radius:3px">{r["test_class"]}.{r["name"]}</code>' for r in items])
        groups_html += f"""
        <div style="background:#fff;border-left:4px solid {CAT_COLORS_HTML.get(cat,'#95a5a6')};padding:12px 15px;margin:8px 0;border-radius:0 8px 8px 0;box-shadow:0 1px 4px rgba(0,0,0,.08)">
          <b style="color:{CAT_COLORS_HTML.get(cat,'#333')}">{cat.upper()} / {layer}</b>
          <span style="background:#eee;padding:1px 8px;border-radius:10px;font-size:12px;margin-left:8px">{len(items)} test(s)</span><br>
          <div style="margin:6px 0;font-size:12px">{tcs}</div>
          <div style="font-size:13px"><b>Cause :</b> {rep.get('root_cause','')}</div>
          <div style="font-size:13px;color:#27ae60"><b>Action :</b> {rep.get('fix_action','')}</div>
        </div>"""

    nb_imm = sum(1 for r in rcas if r.get("fix_priority") == "immediate")

    html = f"""<!DOCTYPE html>
<html lang="fr"><head>
<meta charset="utf-8">
<title>RCA Agent Mobile — Root Cause Analysis</title>
<style>
  body{{font-family:Arial,sans-serif;background:#f5f5f5;color:#333;margin:0;padding:20px}}
  h1{{color:#2c3e50}} h2{{color:#34495e;margin-top:30px}}
  .stat{{display:inline-block;background:#fff;border-radius:8px;padding:15px 25px;margin:8px;box-shadow:0 2px 6px rgba(0,0,0,.1);text-align:center}}
  .stat-val{{font-size:28px;font-weight:bold}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1);margin-top:15px}}
  th{{background:#2c3e50;color:#fff;padding:10px;text-align:left;font-size:12px}}
  td{{padding:8px 10px;border-bottom:1px solid #ecf0f1;vertical-align:top}}
  tr:hover{{background:#f8f9fa}}
  code{{font-family:monospace;font-size:11px}}
</style>
</head><body>
<h1>🔍 RCA Agent — Mobile (Chain of Thought)</h1>
<p style="color:#666">CoT : le LLM raisonne en 3 étapes → chaîne causale traçable · App : QAcart-To-Do.apk</p>
<div>
  <div class="stat"><div class="stat-val" style="color:#e74c3c">{len(rcas)}</div>Échecs analysés</div>
  <div class="stat"><div class="stat-val" style="color:#e74c3c">{nb_imm}</div>Priorité Immédiate</div>
  <div class="stat"><div class="stat-val" style="color:#3498db">{len(groups)}</div>Causes racines distinctes</div>
</div>
<h2>Causes racines communes</h2>
{groups_html}
<h2>Détail par test</h2>
<table>
  <tr><th>Classe</th><th>Méthode</th><th>Catégorie</th><th>Chaîne causale</th><th>Cause racine</th><th>Action corrective</th><th>Priorité</th><th>Tests liés</th></tr>
  {rows}
</table>
<p style="color:#999;font-size:12px;margin-top:30px">RCA Agent Mobile — Appium/Android · Chain of Thought</p>
</body></html>"""

    out = os.path.join(DOCS_DIR, "rca-report.html")
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n{G}  Rapport HTML : docs/rca-report.html{E}")


def print_help():
    print(f"""
{W}RCA AGENT MOBILE — Root Cause Analysis (Chain of Thought){E}
Source : target/allure-results/

  python agents/rca-agent.py analyse              RCA de tous les échecs
  python agents/rca-agent.py group                Groupement par cause racine
  python agents/rca-agent.py single Test03_AddTodo RCA d'un seul test (CoT visible)
  python agents/rca-agent.py report               Rapport HTML → docs/rca-report.html

{W}Catégories causales mobiles :{E}
  locator    AppiumBy invalide, UI selector introuvable
  app_crash  App killed, session Appium perdue, WebDriverException
  timeout    Wait dépassé, device lent, animation bloquante
  device     Émulateur instable, ADB error
  assertion  Valeur attendue incorrecte dans le test
  data       Données config.properties erronées
""")


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
