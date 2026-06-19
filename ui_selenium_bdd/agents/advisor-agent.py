# ============================================================
# Advisor Agent — Décision Release · Prédiction · Recommandations
# ============================================================
# Commandes :
#   python agents/advisor-agent.py release [N]  → Go/No-Go production (N votes)
#   python agents/advisor-agent.py predict      → prédiction prochains échecs
#   python agents/advisor-agent.py recommend    → recommandations amélioration
#   python agents/advisor-agent.py report       → rapport HTML
# ============================================================

import sys, os, json, glob, time
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

FRAMEWORK  = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ALLURE_DIR = os.path.join(FRAMEWORK, "target", "allure-results")
DOCS_DIR   = os.path.join(FRAMEWORK, "docs")
FLAKY_FILE = os.path.join(DOCS_DIR, "flaky-report.json")
BASELINE   = os.path.join(DOCS_DIR, "baseline.json")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

VOTE_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict":   {"type": "string", "enum": ["GO", "NO-GO"]},
        "risk":      {"type": "string", "enum": ["low", "medium", "high", "critical"]},
        "blockers":  {"type": "array", "items": {"type": "string"}},
        "warnings":  {"type": "array", "items": {"type": "string"}},
        "reasoning": {"type": "string"},
    }
}

PREDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "gate_will_pass":      {"type": "boolean"},
        "confidence":          {"type": "number"},
        "likely_failures":     {"type": "array", "items": {"type": "string"}},
        "likely_flaky":        {"type": "array", "items": {"type": "string"}},
        "risk_level":          {"type": "string", "enum": ["low", "medium", "high", "critical"]},
        "reasoning":           {"type": "string"},
        "recommended_actions": {"type": "array", "items": {"type": "string"}},
    }
}

RISK_COLORS = {"low": G, "medium": Y, "high": R, "critical": R}


def collect_context() -> dict:
    results = []
    for f in glob.glob(os.path.join(ALLURE_DIR, "*.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            if "name" in data and "status" in data:
                results.append(data)
        except Exception:
            pass
    total   = len(results)
    passed  = sum(1 for r in results if r.get("status") == "passed")
    failed  = sum(1 for r in results if r.get("status") == "failed")
    broken  = sum(1 for r in results if r.get("status") == "broken")
    skipped = sum(1 for r in results if r.get("status") == "skipped")
    pass_rate = round(passed / total * 100, 1) if total else 0
    fail_rate = round((failed + broken) / total * 100, 1) if total else 0

    flaky_tests = {}
    if os.path.exists(FLAKY_FILE):
        try:
            with open(FLAKY_FILE, encoding="utf-8") as f:
                flaky_tests = json.load(f).get("flaky", {})
        except Exception:
            pass

    failures = [r for r in results if r.get("status") in ("failed", "broken")]
    return dict(total=total, passed=passed, failed=failed, broken=broken,
                skipped=skipped, pass_rate=pass_rate, fail_rate=fail_rate,
                failures=failures, flaky_tests=flaky_tests)


def format_context(ctx: dict) -> str:
    lines = [
        f"Pass rate  : {ctx['pass_rate']}% ({ctx['passed']}/{ctx['total']})",
        f"Fail rate  : {ctx['fail_rate']}% ({ctx['failed']+ctx['broken']} échecs)",
        f"Ignorés    : {ctx['skipped']}",
        f"Flaky      : {len(ctx['flaky_tests'])} tests instables",
    ]
    if ctx["failures"]:
        lines.append("\nÉchecs :")
        for r in ctx["failures"][:5]:
            msg = r.get("statusDetails", {}).get("message", "?")[:60]
            lines.append(f"  - {r['name'][:50]} : {msg}")
    return "\n".join(lines)


# ── Release ────────────────────────────────────────────────────────────────────

def cmd_release(n_votes: int = 3):
    print(f"\n{W}ADVISOR — Release Decision (Self-Consistency, {n_votes} votes){E}")
    print(f"{Y}  {n_votes} appels LLM indépendants, vote majoritaire{E}\n")
    ctx     = collect_context()
    ctx_str = format_context(ctx)

    _tpl = _ps.get("release_vote") or (
        "Tu es QA Lead senior. Évalue si ce build Selenium BDD peut être déployé en production.\n\n"
        "{context_str}\n\n"
        "Critères de blocage :\n"
        "- Pass rate < 90%\n"
        "- Taux d'échec > 5%\n"
        "- Test critique ou smoke en échec\n"
        "- Test flaky critique présent\n\n"
        "Renvoie un verdict GO ou NO-GO avec le risque, les blockers et le raisonnement."
    )
    messages = [{"role": "user", "content": _fmt(_tpl, context_str=ctx_str)}]
    result   = llm.chat_self_consistent(messages, VOTE_SCHEMA, verdict_key="verdict", n=n_votes)
    _ps.record_usage("release_vote")

    verdict   = result["majority_verdict"]
    agreement = result["agreement_rate"]
    gate_color = G if verdict == "GO" else R
    print(f"  {gate_color}{W}  VERDICT : {verdict}  {E}")
    print(f"  Agreement : {int(agreement * 100)}%  |  Votes : {result['votes']}")

    majority_resp = next((r for r in result["responses"] if str(r.get("verdict","")).upper() == verdict), {})
    risk = majority_resp.get("risk", "unknown")
    print(f"  Risque    : {RISK_COLORS.get(risk,Y)}{risk.upper()}{E}")

    for b in majority_resp.get("blockers", []):
        print(f"  {R}✗{E} {b}")
    for w in majority_resp.get("warnings", []):
        print(f"  {Y}!{E} {w}")
    if agreement < 1.0:
        print(f"\n  {Y}[WARN] Désaccord ({int(agreement*100)}%). Vérification humaine recommandée.{E}")
    print(f"\n  {gate_color}Déploiement {'AUTORISÉ' if verdict=='GO' else 'BLOQUÉ'}.{E}")
    return verdict == "GO", result


def cmd_predict():
    print(f"\n{W}ADVISOR — Prédiction (Structured Output){E}\n")
    ctx     = collect_context()
    ctx_str = format_context(ctx)

    _tpl = _ps.get("predict_gate") or (
        "Analyse les tendances de cette suite de tests Selenium BDD et prédis :\n\n"
        "{context_str}\n\n"
        "Sur la base de ces données, prédis pour le PROCHAIN run :\n"
        "1. Est-ce que le quality gate va passer ?\n"
        "2. Quels tests vont probablement échouer ?\n"
        "3. Quels tests vont devenir flaky ?\n"
        "4. Quel est le niveau de risque global ?\n"
        "5. Quelles actions recommandes-tu avant le prochain run ?\n"
    )
    messages = [{"role": "user", "content": _fmt(_tpl, context_str=ctx_str)}]
    try:
        result = llm.chat_structured(messages, PREDICT_SCHEMA)
        _ps.record_usage("predict_gate", confidence=result.get("confidence", 0))
    except Exception as e:
        print(f"{R}  LLM indisponible : {e}{E}")
        return {}

    gate_ok    = result.get("gate_will_pass", False)
    confidence = result.get("confidence", 0)
    risk       = result.get("risk_level", "unknown")
    print(f"  Gate prochain run : {G if gate_ok else R}{'OUI' if gate_ok else 'NON'}{E} "
          f"(confidence : {int(confidence*100)}%)")
    print(f"  Risque global     : {RISK_COLORS.get(risk,Y)}{risk.upper()}{E}")

    if result.get("likely_failures"):
        print(f"\n  {R}Tests susceptibles d'échouer :{E}")
        for t in result["likely_failures"][:5]:
            print(f"    - {t}")
    if result.get("recommended_actions"):
        print(f"\n  {C}Actions recommandées :{E}")
        for a in result["recommended_actions"][:5]:
            print(f"    → {a}")
    return result


def cmd_recommend():
    print(f"\n{W}ADVISOR — Recommandations qualité{E}\n")
    ctx     = collect_context()
    ctx_str = format_context(ctx)
    messages = [{"role": "user", "content": (
        f"Analyse cette suite de tests Selenium BDD :\n\n{ctx_str}\n\n"
        f"Application testée : automationexercise.com (e-commerce, 26 cas de test)\n"
        f"Stack : Java 17, Selenium 4, Cucumber 7, TestNG\n\n"
        f"Donne 5 recommandations concrètes pour améliorer la qualité et la maintenabilité."
    )}]
    try:
        result = llm.chat(messages)
        for line in result.strip().split("\n"):
            print(f"  {line}")
    except Exception as e:
        print(f"{R}  LLM indisponible : {e}{E}")


def cmd_report():
    print(f"\n{W}ADVISOR — Rapport HTML{E}")
    ctx    = collect_context()
    stats  = {k: ctx[k] for k in ("total","passed","failed","broken","skipped","pass_rate","fail_rate")}
    gate_ok = stats["pass_rate"] >= 90 and stats["fail_rate"] <= 5
    gate_color = "#2ecc71" if gate_ok else "#e74c3c"

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Advisor Report — Selenium BDD</title>
<style>body{{background:#0d1117;color:#c9d1d9;font-family:'Segoe UI',sans-serif;padding:20px}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;margin:12px 0}}
h1{{color:#58a6ff}}h2{{color:#58a6ff;font-size:1em}}
.verdict{{font-size:2em;font-weight:bold;color:{gate_color};text-align:center;padding:20px}}
</style></head><body>
<h1>📊 Advisor Report — ui_selenium_bdd</h1>
<p style="color:#8b949e">Généré le {time.strftime('%Y-%m-%d %H:%M')}</p>
<div class="card"><div class="verdict">{'✅ GO — RELEASE AUTORISÉE' if gate_ok else '❌ NO-GO — RELEASE BLOQUÉE'}</div></div>
<div class="card"><h2>Métriques</h2>
<p>Total: {stats['total']} | Passés: {stats['passed']} | Échoués: {stats['failed']} | Brisés: {stats['broken']}</p>
<p>Pass rate: {stats['pass_rate']}% | Fail rate: {stats['fail_rate']}%</p>
</div></body></html>"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, "advisor-report.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  {G}Rapport : docs/advisor-report.html{E}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Advisor Agent — Selenium BDD")
    parser.add_argument("command", choices=["release", "predict", "recommend", "report"])
    parser.add_argument("n_votes", nargs="?", type=int, default=3)
    args = parser.parse_args()

    if args.command == "release":   cmd_release(args.n_votes)
    elif args.command == "predict": cmd_predict()
    elif args.command == "recommend": cmd_recommend()
    elif args.command == "report":  cmd_report()
