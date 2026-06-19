# ============================================================
# Quality Agent — KPI · Analyse · Flaky · Gate
# ============================================================
# Commandes :
#   python agents/quality-agent.py analyze        → analyse qualité globale
#   python agents/quality-agent.py kpi            → dashboard KPI HTML
#   python agents/quality-agent.py flaky [--runs] → détection tests instables
#   python agents/quality-agent.py verify         → cohérence features/steps/pages
#   python agents/quality-agent.py gate           → quality gate Go/No-Go
# ============================================================

import sys, os, json, glob, re, subprocess, time
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

FRAMEWORK    = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ALLURE_DIR   = os.path.join(FRAMEWORK, "target", "allure-results")
FEATURES_DIR = os.path.join(FRAMEWORK, "src", "test", "resources", "features")
STEPS_DIR    = os.path.join(FRAMEWORK, "src", "test", "java", "com", "qacart", "todo", "steps")
PAGES_DIR    = os.path.join(FRAMEWORK, "src", "test", "java", "com", "qacart", "todo", "pages")
DOCS_DIR     = os.path.join(FRAMEWORK, "docs")
FLAKY_FILE   = os.path.join(DOCS_DIR, "flaky-report.json")
KPI_FILE     = os.path.join(DOCS_DIR, "kpi-dashboard.html")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

QUALITY_GATE = {"pass_rate": 90.0, "fail_rate": 5.0, "confidence": 0.70}


# ── Chargement résultats ───────────────────────────────────────────────────────

def load_results() -> list:
    results = []
    for f in glob.glob(os.path.join(ALLURE_DIR, "*.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            if "name" in data and "status" in data:
                results.append(data)
        except Exception:
            pass
    return results


def parse_stats(results: list) -> dict:
    total   = len(results)
    passed  = sum(1 for r in results if r.get("status") == "passed")
    failed  = sum(1 for r in results if r.get("status") == "failed")
    broken  = sum(1 for r in results if r.get("status") == "broken")
    skipped = sum(1 for r in results if r.get("status") == "skipped")
    pass_rate = round(passed / total * 100, 1) if total else 0
    fail_rate = round((failed + broken) / total * 100, 1) if total else 0
    return dict(total=total, passed=passed, failed=failed, broken=broken,
                skipped=skipped, pass_rate=pass_rate, fail_rate=fail_rate)


# ── Commandes ──────────────────────────────────────────────────────────────────

def cmd_analyze():
    print(f"\n{W}QUALITY AGENT — Analyse qualité Selenium BDD{E}\n")
    results = load_results()
    if not results:
        print(f"  {R}Aucun résultat Allure dans target/allure-results.{E}")
        print(f"  {Y}Lance d'abord : python agents/runner-agent.py run{E}")
        return {}
    stats = parse_stats(results)
    gate_ok = stats["pass_rate"] >= QUALITY_GATE["pass_rate"] and stats["fail_rate"] <= QUALITY_GATE["fail_rate"]

    print(f"  Total    : {W}{stats['total']}{E}")
    print(f"  {G}Passés   : {stats['passed']}{E}")
    print(f"  {R}Échoués  : {stats['failed']}{E}")
    print(f"  {Y}Brisés   : {stats['broken']}{E}")
    print(f"  Ignorés  : {stats['skipped']}")
    print(f"\n  Pass rate : {G if gate_ok else R}{stats['pass_rate']}%{E}  |  "
          f"Fail rate : {G if gate_ok else R}{stats['fail_rate']}%{E}")
    print(f"  Quality Gate : {G+'PASS ✓' if gate_ok else R+'FAIL ✗'}{E}")

    # Analyse LLM des échecs
    failures = [r for r in results if r.get("status") in ("failed", "broken")]
    if failures:
        fail_text = "\n".join(
            f"- {r['name']}: {r.get('statusDetails',{}).get('message','?')[:80]}"
            for r in failures[:8]
        )
        messages = [{"role": "user", "content": (
            f"Suite de tests Selenium BDD — résumé qualité :\n\n"
            f"Pass rate: {stats['pass_rate']}% | Fail rate: {stats['fail_rate']}% | "
            f"Total: {stats['total']}\n\n"
            f"Échecs:\n{fail_text}\n\n"
            f"En 3 points, identifie les patterns d'échec et donne des recommandations."
        )}]
        try:
            analysis = llm.chat(messages)
            print(f"\n{W}  Analyse LLM :{E}")
            for line in analysis.strip().split("\n"):
                print(f"  {line}")
        except Exception as e:
            print(f"  {Y}LLM indisponible : {e}{E}")
    return stats


def cmd_kpi():
    print(f"\n{W}QUALITY AGENT — Dashboard KPI HTML{E}")
    results = load_results()
    stats = parse_stats(results) if results else {"total":0,"passed":0,"failed":0,"broken":0,"skipped":0,"pass_rate":0,"fail_rate":0}
    gate_ok = stats["pass_rate"] >= QUALITY_GATE["pass_rate"]

    # Features count
    features = glob.glob(os.path.join(FEATURES_DIR, "*.feature"))
    pages    = glob.glob(os.path.join(PAGES_DIR, "*.java"))

    gate_color = "#2ecc71" if gate_ok else "#e74c3c"
    html = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<title>KPI Dashboard — ui_selenium_bdd</title>
<style>
body{{background:#0d1117;color:#c9d1d9;font-family:'Segoe UI',sans-serif;margin:0;padding:20px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin:20px 0}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:20px;text-align:center}}
.metric{{font-size:2.5em;font-weight:bold;margin:8px 0}}
.label{{color:#8b949e;font-size:0.85em;text-transform:uppercase;letter-spacing:1px}}
.gate{{background:{gate_color}22;border:2px solid {gate_color};border-radius:12px;
       padding:16px;text-align:center;font-size:1.5em;font-weight:bold;color:{gate_color}}}
h1{{color:#58a6ff;border-bottom:1px solid #30363d;padding-bottom:12px}}
</style></head><body>
<h1>🧪 KPI Dashboard — Selenium BDD (automationexercise.com)</h1>
<p style="color:#8b949e">Généré le {time.strftime('%Y-%m-%d %H:%M')} UTC</p>
<div class="gate">{'✅ QUALITY GATE : PASS' if gate_ok else '❌ QUALITY GATE : FAIL'}</div>
<div class="grid">
  <div class="card"><div class="metric" style="color:#58a6ff">{stats['total']}</div><div class="label">Tests exécutés</div></div>
  <div class="card"><div class="metric" style="color:#2ecc71">{stats['passed']}</div><div class="label">Passés</div></div>
  <div class="card"><div class="metric" style="color:#e74c3c">{stats['failed']}</div><div class="label">Échoués</div></div>
  <div class="card"><div class="metric" style="color:#f39c12">{stats['broken']}</div><div class="label">Brisés</div></div>
  <div class="card"><div class="metric" style="color:{gate_color}">{stats['pass_rate']}%</div><div class="label">Pass Rate (seuil 90%)</div></div>
  <div class="card"><div class="metric" style="color:{gate_color}">{stats['fail_rate']}%</div><div class="label">Fail Rate (seuil 5%)</div></div>
  <div class="card"><div class="metric" style="color:#a371f7">{len(features)}</div><div class="label">Feature files</div></div>
  <div class="card"><div class="metric" style="color:#79c0ff">{len(pages)}</div><div class="label">Page Objects</div></div>
</div>
</body></html>"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(KPI_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  {G}Dashboard : docs/kpi-dashboard.html{E}")
    return stats


def cmd_flaky(runs: int = 3):
    print(f"\n{W}QUALITY AGENT — Détection flaky ({runs} runs){E}")
    flaky_file = os.path.join(DOCS_DIR, "flaky-report.json")
    if not os.path.exists(flaky_file):
        print(f"  {Y}Aucun rapport flaky. Lance d'abord : python agents/runner-agent.py flaky{E}")
        return {}
    with open(flaky_file, encoding="utf-8") as f:
        data = json.load(f)
    flaky = data.get("flaky", {})
    runs  = data.get("runs", runs)
    if not flaky:
        print(f"  {G}Aucun test flaky détecté sur {runs} runs.{E}")
        return {}

    critical_flaky = [n for n, s in flaky.items() if any(st in ("failed","broken") for st in s)]
    print(f"\n  {R}{len(flaky)} test(s) flaky{E} | {R}{len(critical_flaky)} critique(s){E}")
    for name, statuses in sorted(flaky.items(), key=lambda x: x[1].count("failed"), reverse=True):
        print(f"  {Y}[{'/'.join(statuses)}]{E} {name[:65]}")

    if flaky:
        flaky_text = "\n".join(f"- {n} ({' / '.join(s)})" for n, s in list(flaky.items())[:10])
        _tpl = _ps.get("flaky_analyze") or (
            "Ces tests Selenium BDD sont flaky :\n{flaky_list}\n\n"
            "En 3 points, explique les causes (timing, sélecteurs, données, état) "
            "et propose des actions de stabilisation."
        )
        messages = [{"role": "user", "content": _fmt(_tpl, flaky_list=flaky_text, runs=str(runs))}]
        try:
            analysis = llm.chat(messages)
            _ps.record_usage("flaky_analyze")
            print(f"\n{W}  Analyse LLM :{E}")
            for line in analysis.strip().split("\n"):
                print(f"  {line}")
        except Exception as e:
            print(f"  {Y}LLM indisponible : {e}{E}")
    return flaky


def cmd_verify():
    print(f"\n{W}QUALITY AGENT — Vérification cohérence features / steps / pages{E}\n")
    features = glob.glob(os.path.join(FEATURES_DIR, "*.feature"))
    steps    = glob.glob(os.path.join(STEPS_DIR, "*.java"))
    pages    = glob.glob(os.path.join(PAGES_DIR, "*.java"))

    print(f"  Features : {len(features)}")
    print(f"  Steps    : {len(steps)}")
    print(f"  Pages    : {len(pages)}")

    # Extraire les scénarios des features
    scenarios = []
    for f in features:
        with open(f, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = re.match(r"\s*(Scenario|Scenario Outline):\s*(.+)", line)
                if m:
                    scenarios.append(m.group(2).strip())

    # Extraire les step definitions
    step_patterns = []
    for s in steps:
        with open(s, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = re.search(r'@(Given|When|Then|And)\("(.+?)"\)', line)
                if m:
                    step_patterns.append(m.group(2))

    print(f"\n  Scénarios trouvés : {len(scenarios)}")
    print(f"  Step definitions  : {len(step_patterns)}")

    if scenarios and step_patterns:
        context = f"Features : {len(features)} | Scénarios : {len(scenarios)} | Steps : {len(step_patterns)} | Pages : {len(pages)}"
        messages = [{"role": "user", "content": (
            f"Vérifie la cohérence de ce framework Selenium BDD Java :\n\n{context}\n\n"
            f"Premiers scénarios : {', '.join(scenarios[:5])}\n"
            f"Premiers patterns : {', '.join(step_patterns[:5])}\n\n"
            f"En 3 points, identifie les risques de cohérence (steps non implémentés, pages manquantes, etc.)."
        )}]
        try:
            result = llm.chat_adversarial(messages)
            print(f"\n{W}  Vérification adversariale :{E}")
            for line in result.get("final", "").strip().split("\n"):
                print(f"  {line}")
        except Exception as e:
            print(f"  {Y}LLM indisponible : {e}{E}")


def cmd_gate():
    print(f"\n{W}QUALITY AGENT — Quality Gate Go/No-Go{E}\n")
    results = load_results()
    if not results:
        print(f"  {R}Aucun résultat — lance d'abord un run.{E}")
        return False
    stats = parse_stats(results)
    gate_ok = (stats["pass_rate"] >= QUALITY_GATE["pass_rate"] and
               stats["fail_rate"] <= QUALITY_GATE["fail_rate"])
    color = G if gate_ok else R

    print(f"  Pass rate : {color}{stats['pass_rate']}%{E}  (seuil : ≥ {QUALITY_GATE['pass_rate']}%)")
    print(f"  Fail rate : {color}{stats['fail_rate']}%{E}  (seuil : ≤ {QUALITY_GATE['fail_rate']}%)")
    print(f"\n  {color}{W}{'✅ PASS — GO' if gate_ok else '❌ FAIL — NO-GO'}{E}")

    if not gate_ok:
        if stats["pass_rate"] < QUALITY_GATE["pass_rate"]:
            print(f"  {R}Bloquant : Pass rate insuffisant ({stats['pass_rate']}% < 90%){E}")
        if stats["fail_rate"] > QUALITY_GATE["fail_rate"]:
            print(f"  {R}Bloquant : Trop d'échecs ({stats['fail_rate']}% > 5%){E}")
    return gate_ok


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Quality Agent — Selenium BDD")
    parser.add_argument("command", choices=["analyze", "kpi", "flaky", "verify", "gate"])
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()

    if args.command == "analyze": cmd_analyze()
    elif args.command == "kpi":   cmd_kpi()
    elif args.command == "flaky": cmd_flaky(args.runs)
    elif args.command == "verify":cmd_verify()
    elif args.command == "gate":  cmd_gate()
