# ============================================================
# Advisor Agent — Release · Prédiction · Recommandations
# ============================================================
# Absorbe : release-advisor-agent · predictive-agent
#
# Commandes :
#   python agents/advisor-agent.py release [N]  → décision Go/No-Go production (N votes)
#   python agents/advisor-agent.py predict      → prédiction des défaillances futures
#   python agents/advisor-agent.py recommend    → recommandations d'amélioration
#   python agents/advisor-agent.py report       → rapport HTML complet
# ============================================================

import sys, os, json, glob, re
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
RESULTS_DIR = os.path.join(FRAMEWORK, "allure-results")
DOCS_DIR    = os.path.join(FRAMEWORK, "docs")
FLAKY_FILE  = os.path.join(DOCS_DIR, "flaky-report.json")
BASELINE    = os.path.join(DOCS_DIR, "baseline.json")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

# Schéma vote individuel Self-Consistency
VOTE_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict":   {"type": "string", "enum": ["GO", "NO-GO"]},
        "risk":      {"type": "string", "enum": ["low", "medium", "high", "critical"]},
        "blockers":  {"type": "array",  "items": {"type": "string"}},
        "warnings":  {"type": "array",  "items": {"type": "string"}},
        "reasoning": {"type": "string"},
    },
    "required": ["verdict", "risk", "blockers", "warnings", "reasoning"]
}

PREDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "gate_will_pass":    {"type": "boolean"},
        "confidence":        {"type": "number"},
        "likely_failures":   {"type": "array", "items": {"type": "string"}},
        "likely_flaky":      {"type": "array", "items": {"type": "string"}},
        "risk_level":        {"type": "string", "enum": ["low", "medium", "high", "critical"]},
        "reasoning":         {"type": "string"},
        "recommended_actions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["gate_will_pass", "confidence", "likely_failures", "likely_flaky",
                 "risk_level", "reasoning", "recommended_actions"]
}

RISK_COLORS = {"low": G, "medium": Y, "high": R, "critical": R}


# ── Collecte du contexte ───────────────────────────────────────────────────

def collect_context() -> dict:
    ctx = {"total": 0, "passed": 0, "failed": 0, "broken": 0, "failures": []}
    for f in glob.glob(os.path.join(RESULTS_DIR, "*-result.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
            s = d.get("status", "unknown")
            if s == "passed":
                ctx["passed"] += 1
            elif s == "failed":
                ctx["failed"] += 1
            elif s == "broken":
                ctx["broken"] += 1
            ctx["total"] += 1
            if s in ("failed", "broken"):
                tags = [lb["value"] for lb in d.get("labels", []) if lb["name"] == "tag"]
                tc   = next((t for t in tags if re.match(r"tc-\d+", t)), None)
                ctx["failures"].append({
                    "name": d.get("name", "?"), "tc": tc,
                    "message": (d.get("statusDetails") or {}).get("message", "")[:150],
                    "status":  s,
                })
        except Exception:
            pass

    total = ctx["total"] or 1
    ctx["pass_rate"] = round(ctx["passed"] / total * 100, 1)
    ctx["fail_rate"] = round((ctx["failed"] + ctx["broken"]) / total * 100, 1)

    # Données flaky
    ctx["flaky_tests"] = {}
    if os.path.exists(FLAKY_FILE):
        try:
            ctx["flaky_tests"] = json.load(open(FLAKY_FILE, encoding="utf-8")).get("flaky_tests", {})
        except Exception:
            pass

    # Historique baseline
    ctx["baseline_count"] = 0
    if os.path.exists(BASELINE):
        try:
            bl = json.load(open(BASELINE, encoding="utf-8"))
            ctx["baseline_count"] = len(bl.get("passed_tests", []))
        except Exception:
            pass

    return ctx


def format_context_for_llm(ctx: dict) -> str:
    failures_text = "\n".join([
        f"  - [{f['tc'] or '?'}] {f['name']}: {f['message'][:80]}"
        for f in ctx["failures"][:8]
    ])
    flaky_text = "\n".join([
        f"  - {name} ({int(d['fail_rate']*100)}% fail rate)"
        for name, d in list(ctx["flaky_tests"].items())[:5]
    ])
    return (
        f"Resultats courants : {ctx['total']} tests | Pass: {ctx['passed']} ({ctx['pass_rate']}%) | "
        f"Fail: {ctx['failed']} | Broken: {ctx['broken']}\n"
        f"Baseline : {ctx['baseline_count']} tests reference\n"
        f"Tests flaky : {len(ctx['flaky_tests'])}\n"
        f"{'Echecs:\n' + failures_text if ctx['failures'] else 'Aucun echec.'}\n"
        f"{'Tests flaky:\n' + flaky_text if ctx['flaky_tests'] else ''}"
    )


# ── Release — Self-Consistency Go/No-Go ───────────────────────────────────

def cmd_release(n_votes: int = 3):
    print(f"\n{W}ADVISOR AGENT — Release Decision (Self-Consistency, {n_votes} votes){E}")
    print(f"{Y}  Self-Consistency : {n_votes} appels LLM independants, vote majoritaire{E}\n")

    ctx     = collect_context()
    ctx_str = format_context_for_llm(ctx)

    _tpl = _ps.get("release_vote") or (
        "Tu es QA Lead senior. Evalues si ce build peut etre deploye en production.\n\n"
        "{context_str}\n\n"
        "Criteres de blocage :\n"
        "- Pass rate < 90%\n"
        "- Taux d'echec > 5%\n"
        "- Test critique ou smoke en echec\n"
        "- Test flaky critique present\n\n"
        "Renvoie un verdict GO ou NO-GO avec le risque, les blockers et le raisonnement."
    )
    messages = [{"role": "user", "content": _fmt(_tpl, context_str=ctx_str)}]

    result = llm.chat_self_consistent(messages, VOTE_SCHEMA, verdict_key="verdict", n=n_votes)
    _ps.record_usage("release_vote")

    verdict   = result["majority_verdict"]
    agreement = result["agreement_rate"]
    votes     = result["votes"]
    responses = result["responses"]

    # Affichage
    gate_color = G if verdict == "GO" else R
    print(f"  {gate_color}{W}  VERDICT : {verdict}  {E}")
    print(f"  Agreement : {int(agreement * 100)}%  |  Votes : {votes}")

    # Risque du vote majoritaire
    majority_resp = next((r for r in responses if str(r.get("verdict", "")).upper() == verdict), {})
    risk = majority_resp.get("risk", "unknown")
    print(f"  Risque    : {RISK_COLORS.get(risk, Y)}{risk.upper()}{E}")

    blockers = majority_resp.get("blockers", [])
    warnings = majority_resp.get("warnings", [])

    if blockers:
        print(f"\n{R}  Blockers :{E}")
        for b in blockers:
            print(f"  {R}x{E} {b}")
    if warnings:
        print(f"\n{Y}  Avertissements :{E}")
        for w in warnings:
            print(f"  {Y}!{E} {w}")

    if result["minority_reasons"]:
        print(f"\n{C}  Votes minoritaires :{E}")
        for reason in result["minority_reasons"]:
            print(f"  {C}~{E} {reason[:100]}")

    # Recommandation si pas unanime
    if agreement < 1.0:
        print(f"\n{Y}  [WARN] Desaccord entre les votes ({int(agreement*100)}%). Verification humaine recommandee.{E}")

    gate_passed = verdict == "GO"
    print(f"\n  {gate_color}Deploiement {'AUTORISE' if gate_passed else 'BLOQUE'}.{E}")
    return gate_passed, result


# ── Predict — Prédiction des défaillances futures ─────────────────────────

def cmd_predict():
    print(f"\n{W}ADVISOR AGENT — Prediction (Structured Output){E}\n")

    ctx     = collect_context()
    ctx_str = format_context_for_llm(ctx)

    _tpl = _ps.get("predict_gate") or (
        "Analyse les tendances de cette suite de tests API et predis :\n\n"
        "{context_str}\n\n"
        "Sur la base de ces donnees, predis pour le PROCHAIN run :\n"
        "1. Est-ce que le quality gate va passer ?\n"
        "2. Quels TCs vont probablement echouer ?\n"
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
    likely_f   = result.get("likely_failures", [])
    likely_fl  = result.get("likely_flaky", [])
    actions    = result.get("recommended_actions", [])

    print(f"  Gate prochain run : {G if gate_ok else R}{'OUI' if gate_ok else 'NON'}{E} "
          f"(confidence : {int(confidence*100)}%)")
    print(f"  Risque global    : {RISK_COLORS.get(risk, Y)}{risk.upper()}{E}")

    if likely_f:
        print(f"\n{R}  TCs probablement en echec :{E}")
        for tc in likely_f:
            print(f"  {R}x{E} {tc}")

    if likely_fl:
        print(f"\n{Y}  TCs qui vont devenir flaky :{E}")
        for tc in likely_fl:
            print(f"  {Y}~{E} {tc}")

    if actions:
        print(f"\n{G}  Actions recommandees :{E}")
        for a in actions:
            print(f"  {G}>{E} {a}")

    # Sauvegarder
    os.makedirs(DOCS_DIR, exist_ok=True)
    out_file = os.path.join(DOCS_DIR, "prediction-report.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n{G}  Rapport : docs/prediction-report.json{E}")
    return result


# ── Recommend — Recommandations d'amélioration ─────────────────────────────

def cmd_recommend():
    print(f"\n{W}ADVISOR AGENT — Recommendations{E}\n")
    ctx     = collect_context()
    ctx_str = format_context_for_llm(ctx)

    messages = [{"role": "user", "content": (
        f"En tant qu'architecte QA senior, analyse cette suite de tests API et fournis "
        f"des recommandations concretes d'amelioration.\n\n"
        f"{ctx_str}\n\n"
        f"Structure tes recommandations en :\n"
        f"1. Actions immediates (bloquantes)\n"
        f"2. Ameliorations court terme (1-2 sprints)\n"
        f"3. Evolution architecturale (long terme)\n"
        f"Sois concis et actionnable."
    )}]
    analysis = llm.chat_cot(messages)

    print(f"{W}  Recommandations (CoT) :{E}")
    for line in analysis.strip().split("\n"):
        if re.match(r"\s*ÉTAPE\s*\d", line, re.IGNORECASE):
            print(f"  {Y}{line}{E}")
        elif re.match(r"\s*CONCLUSION", line, re.IGNORECASE):
            print(f"  {G}{line}{E}")
        elif line.strip():
            print(f"  {line}")


# ── Report HTML ────────────────────────────────────────────────────────────

def cmd_report():
    print(f"\n{W}ADVISOR AGENT — Rapport HTML{E}")
    gate_ok, release_result = cmd_release()
    predict_result          = cmd_predict()

    verdict      = release_result.get("majority_verdict", "?")
    agreement    = release_result.get("agreement_rate", 0)
    votes        = release_result.get("votes", {})
    gate_color   = "#27ae60" if gate_ok else "#e74c3c"
    risk         = predict_result.get("risk_level", "unknown")
    risk_color   = {"low": "#27ae60", "medium": "#e67e22", "high": "#e74c3c", "critical": "#8e44ad"}.get(risk, "#95a5a6")
    actions_html = "".join(f"<li>{a}</li>" for a in predict_result.get("recommended_actions", []))
    failures_html = "".join(f"<li style='color:#e74c3c'>{tc}</li>" for tc in predict_result.get("likely_failures", []))
    votes_html   = " ".join(f"<span style='background:{'#27ae60' if v=='GO' else '#e74c3c'};color:#fff;"
                            f"padding:4px 10px;border-radius:4px;margin:2px'>{v} ({c})</span>"
                            for v, c in votes.items())

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Advisor Agent — Release & Prediction</title>
<style>
  body{{font-family:Arial,sans-serif;background:#f5f5f5;color:#333;margin:0;padding:20px}}
  h1{{color:#2c3e50}} h2{{color:#34495e;margin-top:30px}}
  .stat{{display:inline-block;background:#fff;border-radius:8px;padding:18px 28px;margin:8px;
         box-shadow:0 2px 6px rgba(0,0,0,.1);text-align:center}}
  .stat-val{{font-size:32px;font-weight:bold}}
  .verdict-box{{padding:15px 30px;border-radius:8px;font-size:22px;font-weight:bold;
                display:inline-block;color:#fff;margin:10px 0;background:{gate_color}}}
  ul{{background:#fff;border-radius:8px;padding:15px 15px 15px 30px;
       box-shadow:0 2px 6px rgba(0,0,0,.08)}}
</style>
</head>
<body>
<h1>Advisor Agent — Release Decision & Prediction</h1>

<h2>Release Decision (Self-Consistency)</h2>
<div class="verdict-box">{verdict}</div>
<div>
  <div class="stat"><div class="stat-val" style="color:#2c3e50">{int(agreement*100)}%</div>Agreement</div>
  <div class="stat"><div class="stat-val" style="color:{risk_color}">{risk.upper()}</div>Risque</div>
</div>
<p>Votes : {votes_html}</p>

<h2>Prediction — Prochain Run</h2>
<div>
  <div class="stat"><div class="stat-val" style="color:{'#27ae60' if predict_result.get('gate_will_pass') else '#e74c3c'}">
    {'GO' if predict_result.get('gate_will_pass') else 'NO-GO'}</div>Gate prochainement</div>
  <div class="stat"><div class="stat-val" style="color:#3498db">
    {int(predict_result.get('confidence',0)*100)}%</div>Confiance</div>
</div>

{f'<h2>TCs probablement en échec</h2><ul>{failures_html}</ul>' if failures_html else ''}
{f'<h2>Actions recommandées</h2><ul>{actions_html}</ul>' if actions_html else ''}

<p style="color:#999;font-size:12px;margin-top:30px">
  Généré par Advisor Agent — Self-Consistency ({len(release_result.get("responses",[]))} votes) + Prediction
</p>
</body>
</html>"""

    out = os.path.join(DOCS_DIR, "advisor-report.html")
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n{G}  Rapport HTML : docs/advisor-report.html{E}")


# ── Main ───────────────────────────────────────────────────────────────────

def print_help():
    print(f"""
{W}ADVISOR AGENT — Release · Prédiction · Recommandations{E}

  python agents/advisor-agent.py release       Décision Go/No-Go (3 votes Self-Consistency)
  python agents/advisor-agent.py release 5     5 votes au lieu de 3
  python agents/advisor-agent.py predict       Prédit les défaillances du prochain run
  python agents/advisor-agent.py recommend     Recommandations d'amélioration (CoT)
  python agents/advisor-agent.py report        Rapport HTML complet (release + prediction)

{W}Patterns LLM utilisés :{E}
  Self-Consistency  → décision de release (N votes, vote majoritaire)
  Structured Output → prédiction structurée
  Chain of Thought  → recommandations raisonnées

{W}Modules absorbes :{E} release-advisor-agent · predictive-agent
""")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    n_arg = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 3

    if cmd == "release":
        go, _ = cmd_release(n_votes=n_arg)
        sys.exit(0 if go else 1)
    elif cmd == "predict":
        cmd_predict()
    elif cmd == "recommend":
        cmd_recommend()
    elif cmd == "report":
        cmd_report()
    else:
        print_help()
