# ============================================================
# Release Advisor Agent — Décision Go/No-Go avec Self-Consistency
# ============================================================
# Pose la question "peut-on déployer ?" N fois au LLM avec des
# températures différentes et prend le vote majoritaire.
#
# Pourquoi Self-Consistency ici ?
# Une décision de déploiement est trop critique pour reposer
# sur un seul appel LLM — un seul appel peut halluciner "GO"
# même quand les tests montrent des blockers évidents.
#
# Usage:
#   python agents/release-advisor-agent.py advise    → décision go/no-go (3 votes)
#   python agents/release-advisor-agent.py advise 5 → 5 votes au lieu de 3
#   python agents/release-advisor-agent.py report   → rapport HTML complet
# ============================================================

import sys, os, json, glob, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm

FRAMEWORK   = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS_DIR = os.path.join(FRAMEWORK, "allure-results")
ENV_FILE    = os.path.join(RESULTS_DIR, "environment.properties")
DOCS_DIR    = os.path.join(FRAMEWORK, "docs")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

# Schéma de chaque vote individuel
VOTE_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict":   {"type": "string", "enum": ["GO", "NO-GO"],
                      "description": "GO = déploiement autorisé, NO-GO = bloqué"},
        "risk":      {"type": "string", "enum": ["low", "medium", "high", "critical"]},
        "blockers":  {"type": "array",  "items": {"type": "string"},
                      "description": "Raisons bloquantes si NO-GO (vide si GO)"},
        "warnings":  {"type": "array",  "items": {"type": "string"},
                      "description": "Points de vigilance même si GO"},
        "reasoning": {"type": "string", "description": "Raisonnement en 2 phrases max"}
    },
    "required": ["verdict", "risk", "blockers", "warnings", "reasoning"]
}


# ── Collecte du contexte de release ───────────────────────────────────────

def collect_release_context() -> dict:
    """Rassemble tout ce qui est pertinent pour la décision de release."""
    ctx = {
        "total": 0, "passed": 0, "failed": 0, "broken": 0,
        "pass_rate": 0.0, "fail_rate": 0.0,
        "failures": [], "quality_gate": None,
        "gate_passed": None,
    }

    # Stats depuis allure-results
    for f in glob.glob(os.path.join(RESULTS_DIR, "*-result.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
            s = d.get("status", "")
            ctx["total"] += 1
            if s in ctx: ctx[s] += 1
            if s in ("failed", "broken"):
                tags   = [lb["value"] for lb in d.get("labels",[]) if lb["name"]=="tag"]
                tc     = next((t for t in tags if re.match(r"tc-\d+", t)), None)
                detail = d.get("statusDetails") or {}
                ctx["failures"].append({
                    "tc":      tc or "?",
                    "name":    d.get("name","?")[:60],
                    "message": detail.get("message","")[:150],
                    "tags":    tags,
                })
        except Exception:
            pass

    if ctx["total"]:
        ctx["pass_rate"] = round(ctx["passed"] / ctx["total"] * 100, 1)
        ctx["fail_rate"] = round(ctx["failed"] / ctx["total"] * 100, 1)

    # Quality Gate depuis environment.properties
    if os.path.exists(ENV_FILE):
        for line in open(ENV_FILE, encoding="utf-8"):
            if "Quality.Gate=" in line:
                ctx["quality_gate"] = line.split("=",1)[1].strip()
                ctx["gate_passed"]  = ctx["quality_gate"] == "PASSED"

    return ctx


def _build_prompt(ctx: dict) -> list:
    """Construit le prompt de décision de release."""
    failures_str = "\n".join([
        f"  - [{f['tc']}] {f['name']}: {f['message'][:80]}"
        for f in ctx["failures"][:10]
    ]) or "  Aucun"

    gate_info = (
        f"Quality Gate Allure : {ctx['quality_gate']}"
        if ctx["quality_gate"] else "Quality Gate : non disponible"
    )

    return [{
        "role": "user",
        "content": (
            f"Analyse ces résultats de tests et décide si on peut déployer en production.\n\n"
            f"RÉSULTATS DE TESTS :\n"
            f"  Total       : {ctx['total']} tests\n"
            f"  Passés      : {ctx['passed']} ({ctx['pass_rate']}%)\n"
            f"  Échoués     : {ctx['failed']} ({ctx['fail_rate']}%)\n"
            f"  Cassés      : {ctx['broken']}\n"
            f"  {gate_info}\n\n"
            f"TESTS EN ÉCHEC :\n{failures_str}\n\n"
            f"Règles de décision :\n"
            f"  NO-GO immédiat si : pass_rate < 85% OU fail_rate > 10% OU blocker critique\n"
            f"  GO avec warning si : pass_rate 85-90% OU tests flaky connus\n"
            f"  GO clair si        : pass_rate ≥ 90% ET aucun blocker\n"
        )
    }]


# ── Affichage du résultat Self-Consistency ─────────────────────────────────

def print_votes(result: dict):
    votes      = result["votes"]
    majority   = result["majority_verdict"]
    agreement  = result["agreement_rate"]
    unanimous  = result["is_unanimous"]
    responses  = result["responses"]
    minority   = result["minority_reasons"]

    # Bandeau final
    if majority == "GO":
        banner_color = G
        banner_icon  = "✓ GO — DÉPLOIEMENT AUTORISÉ"
    else:
        banner_color = R
        banner_icon  = "✗ NO-GO — DÉPLOIEMENT BLOQUÉ"

    print(f"\n  {banner_color}{W}{'━'*54}{E}")
    print(f"  {banner_color}{W}  {banner_icon}{E}")
    print(f"  {banner_color}{W}{'━'*54}{E}")

    # Score d'accord
    agree_color = G if agreement >= 0.8 else Y if agreement >= 0.6 else R
    unani_label = f" {G}(UNANIME){E}" if unanimous else ""
    votes_str   = "  ".join([f"{v}×{n}" for v, n in sorted(votes.items())])
    print(f"\n  Accord     : {agree_color}{W}{int(agreement*100)}%{E}{unani_label}")
    print(f"  Votes      : {C}{votes_str}{E}")

    # Détail de chaque vote
    print(f"\n  {W}Détail des {len(responses)} votes :{E}")
    for r in responses:
        v      = r.get("verdict","?")
        risk   = r.get("risk","?")
        call_n = r.get("_call","?")
        temp   = r.get("_temp","?")
        v_color = G if v == "GO" else R
        r_color = G if risk=="low" else Y if risk=="medium" else R

        print(f"\n  {W}Vote #{call_n}{E} (temp={temp})  →  {v_color}{W}{v}{E}  "
              f"risque={r_color}{risk}{E}")
        print(f"  {r.get('reasoning','')[:100]}")

        blockers = r.get("blockers",[])
        warnings = r.get("warnings",[])
        for b in blockers[:3]:
            print(f"    {R}✗ BLOCKER :{E} {b}")
        for w in warnings[:2]:
            print(f"    {Y}⚠ WARNING :{E} {w}")

    # Raisons minoritaires
    if minority:
        print(f"\n  {Y}{W}Voix minoritaire(s) :{E}")
        for m in minority[:2]:
            print(f"  {Y}→ {m[:120]}{E}")


# ── Commandes ──────────────────────────────────────────────────────────────

def cmd_advise(n: int = 3) -> dict:
    print(f"\n{W}RELEASE ADVISOR — Self-Consistency ({n} votes){E}")
    print(f"{C}  Même question posée {n}× — vote majoritaire = décision finale{E}\n")

    ctx = collect_release_context()
    if ctx["total"] == 0:
        print(f"{Y}  Aucun résultat de test dans allure-results.{E}")
        return {}

    print(f"  Contexte : {ctx['total']} tests | "
          f"{G}{ctx['pass_rate']}% pass{E} | "
          f"{R}{ctx['fail_rate']}% fail{E} | "
          f"{len(ctx['failures'])} échec(s)")
    if ctx["quality_gate"]:
        gate_color = G if ctx["gate_passed"] else R
        print(f"  Quality Gate : {gate_color}{W}{ctx['quality_gate']}{E}")

    messages = _build_prompt(ctx)

    print(f"\n{C}  {n} appels LLM en cours...{E}", flush=True)
    result = llm.chat_self_consistent(
        messages    = messages,
        schema      = VOTE_SCHEMA,
        verdict_key = "verdict",
        n           = n,
    )

    print_votes(result)
    result["context"] = ctx
    return result


def cmd_report(n: int = 3):
    result = cmd_advise(n)
    if not result:
        return

    ctx       = result.get("context", {})
    majority  = result["majority_verdict"]
    agreement = result["agreement_rate"]
    votes     = result["votes"]
    responses = result["responses"]

    gate_color = "#27ae60" if majority == "GO" else "#e74c3c"
    vote_rows  = ""
    for r in responses:
        v  = r.get("verdict","?")
        vc = "#27ae60" if v=="GO" else "#e74c3c"
        rc = {"low":"#27ae60","medium":"#e67e22","high":"#e74c3c","critical":"#c0392b"}.get(r.get("risk","medium"),"#888")
        blockers_html = "".join([f'<li style="color:#e74c3c">{b}</li>' for b in r.get("blockers",[])])
        warnings_html = "".join([f'<li style="color:#e67e22">{w}</li>' for w in r.get("warnings",[])])
        vote_rows += f"""
        <tr>
          <td style="text-align:center;font-weight:bold">#{r.get('_call','?')}</td>
          <td style="text-align:center"><span style="background:{vc};color:#fff;padding:3px 10px;border-radius:4px;font-weight:bold">{v}</span></td>
          <td style="text-align:center"><span style="color:{rc};font-weight:bold">{r.get('risk','?')}</span></td>
          <td style="font-size:12px">{r.get('reasoning','')[:100]}</td>
          <td style="font-size:11px"><ul style="margin:0;padding-left:16px">{blockers_html or '—'}</ul></td>
          <td style="font-size:11px"><ul style="margin:0;padding-left:16px">{warnings_html or '—'}</ul></td>
        </tr>"""

    votes_chart = "  ".join([
        f'<span style="background:{"#27ae60" if v=="GO" else "#e74c3c"};color:#fff;'
        f'padding:4px 14px;border-radius:20px;font-weight:bold;font-size:16px">'
        f'{v} × {n}</span>'
        for v, n in votes.items()
    ])

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Release Advisor — Go/No-Go</title>
<style>
  body{{font-family:Arial,sans-serif;background:#f0f2f5;color:#333;margin:0;padding:20px}}
  h1{{color:#2c3e50}} h2{{color:#34495e;margin-top:30px}}
  .banner{{background:{gate_color};color:#fff;padding:25px;border-radius:12px;
           text-align:center;font-size:28px;font-weight:bold;margin:20px 0;
           box-shadow:0 4px 12px rgba(0,0,0,.2)}}
  .stat{{display:inline-block;background:#fff;border-radius:10px;padding:15px 25px;
         margin:8px;box-shadow:0 2px 8px rgba(0,0,0,.1);text-align:center}}
  .stat-val{{font-size:28px;font-weight:bold}}
  .stat-lbl{{font-size:12px;color:#888;margin-top:4px}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;
         overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1);margin-top:12px}}
  th{{background:#2c3e50;color:#fff;padding:10px 12px;text-align:left;font-size:13px}}
  td{{padding:10px 12px;border-bottom:1px solid #ecf0f1;vertical-align:top}}
  tr:hover{{background:#f8f9fa}}
</style>
</head>
<body>
<h1>Release Advisor — Self-Consistency Go/No-Go</h1>
<p style="color:#666">
  Self-Consistency : la même question est posée {len(responses)}× avec des températures différentes.
  La décision finale est le vote majoritaire — plus fiable qu'un seul appel LLM.
</p>

<div class="banner">{'✓ GO — DÉPLOIEMENT AUTORISÉ' if majority=='GO' else '✗ NO-GO — DÉPLOIEMENT BLOQUÉ'}</div>

<div>
  <div class="stat"><div class="stat-val">{len(responses)}</div><div class="stat-lbl">Votes LLM</div></div>
  <div class="stat"><div class="stat-val" style="color:{gate_color}">{int(agreement*100)}%</div><div class="stat-lbl">Accord {'(unanime)' if result['is_unanimous'] else ''}</div></div>
  <div class="stat"><div class="stat-val" style="color:#27ae60">{ctx.get('pass_rate',0)}%</div><div class="stat-lbl">Pass Rate</div></div>
  <div class="stat"><div class="stat-val" style="color:#e74c3c">{ctx.get('fail_rate',0)}%</div><div class="stat-lbl">Fail Rate</div></div>
  <div class="stat"><div class="stat-val" style="color:#e67e22">{len(ctx.get('failures',[]))}</div><div class="stat-lbl">Tests en échec</div></div>
</div>

<h2>Résultat du vote</h2>
<div style="margin:15px 0">{votes_chart}</div>

<h2>Détail des {len(responses)} votes</h2>
<table>
  <tr><th>Vote</th><th>Verdict</th><th>Risque</th><th>Raisonnement</th><th>Blockers</th><th>Warnings</th></tr>
  {vote_rows}
</table>

<p style="color:#999;font-size:12px;margin-top:30px">
  Généré par Release Advisor Agent — Self-Consistency
  (verdict_key="verdict", n={len(responses)})
</p>
</body>
</html>"""

    out = os.path.join(DOCS_DIR, "release-report.html")
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n{G}  Rapport HTML : docs/release-report.html{E}")


def print_help():
    print(f"""
{W}RELEASE ADVISOR — Self-Consistency Go/No-Go{E}

  python agents/release-advisor-agent.py advise      3 votes (défaut)
  python agents/release-advisor-agent.py advise 5    5 votes
  python agents/release-advisor-agent.py report      Rapport HTML

{W}Self-Consistency — pourquoi :{E}
  1 seul appel LLM peut halluciner "GO" même avec des blockers évidents.
  3 appels avec températures différentes → vote majoritaire → fiable.

  accord 100% (3/3) → décision très fiable
  accord  67% (2/3) → décision probable, surveiller
  accord  33% (1/3) → LLM incertain → escalader à l'humain
""")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    n   = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 3

    if cmd == "advise":
        cmd_advise(n)
    elif cmd == "report":
        cmd_report(n)
    else:
        print_help()
