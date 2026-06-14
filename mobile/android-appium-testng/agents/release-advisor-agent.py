# ============================================================
# Release Advisor Agent — Mobile (Self-Consistency Go/No-Go)
# ============================================================
# Règles mobiles spécifiques :
#   NO-GO immédiat si : app_crash détecté | pass_rate < 80%
#   NO-GO si          : fail_rate > 15% | smoke test échoué
#   GO avec warning   : pass_rate 80-90% | flaky détectés
#   GO clair          : pass_rate ≥ 90% | tous smoke passés
#
# Usage:
#   python agents/release-advisor-agent.py advise    → 3 votes
#   python agents/release-advisor-agent.py advise 5 → 5 votes
#   python agents/release-advisor-agent.py report   → rapport HTML
# ============================================================

import sys, os, json, glob, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm

FRAMEWORK   = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS_DIR = os.path.join(FRAMEWORK, "target", "allure-results")
ENV_FILE    = os.path.join(RESULTS_DIR, "environment.properties")
DOCS_DIR    = os.path.join(FRAMEWORK, "docs")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

VOTE_SCHEMA = {
    "verdict":   "GO | NO-GO",
    "risk":      "low | medium | high | critical",
    "blockers":  ["raisons bloquantes si NO-GO (liste vide si GO)"],
    "warnings":  ["points de vigilance même si GO"],
    "reasoning": "raisonnement en 2 phrases max"
}

APP_CRASH_PATTERNS = [
    "NoSuchSessionException",
    "WebDriverException",
    "Connection refused",
    "An unknown server-side error",
    "ADB connection",
]


# ── Collecte du contexte ───────────────────────────────────────────────────

def collect_release_context() -> dict:
    ctx = {
        "total": 0, "passed": 0, "failed": 0, "broken": 0,
        "pass_rate": 0.0, "fail_rate": 0.0,
        "failures":      [],
        "smoke_failed":  [],
        "app_crashes":   [],
        "quality_gate":  None,
        "gate_passed":   None,
    }

    for f in glob.glob(os.path.join(RESULTS_DIR, "*-result.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
            s = d.get("status", "")
            ctx["total"] += 1
            if s in ctx:
                ctx[s] += 1

            labels     = d.get("labels", [])
            test_class = next((lb["value"] for lb in labels if lb["name"] == "testClass"), "?")
            short_cls  = test_class.split(".")[-1] if "." in test_class else test_class
            groups     = [lb["value"] for lb in labels if lb["name"] == "tag"]
            detail     = d.get("statusDetails") or {}
            message    = detail.get("message", "")

            if s in ("failed", "broken"):
                entry = {
                    "test_class": short_cls,
                    "name":       d.get("name", "?")[:60],
                    "message":    message[:150],
                    "groups":     groups,
                }
                ctx["failures"].append(entry)

                if "smoke" in groups:
                    ctx["smoke_failed"].append(entry)

                for pattern in APP_CRASH_PATTERNS:
                    if pattern.lower() in message.lower():
                        ctx["app_crashes"].append({**entry, "pattern": pattern})
                        break
        except Exception:
            pass

    if ctx["total"]:
        ctx["pass_rate"] = round(ctx["passed"] / ctx["total"] * 100, 1)
        ctx["fail_rate"] = round(ctx["failed"] / ctx["total"] * 100, 1)

    if os.path.exists(ENV_FILE):
        for line in open(ENV_FILE, encoding="utf-8"):
            if "Quality.Gate=" in line:
                ctx["quality_gate"] = line.split("=", 1)[1].strip()
                ctx["gate_passed"]  = ctx["quality_gate"] == "PASSED"

    return ctx


def _build_prompt(ctx: dict) -> list:
    failures_str = "\n".join([
        f"  - [{f['test_class']}] {f['name']} [{', '.join(f['groups'])}]: {f['message'][:80]}"
        for f in ctx["failures"][:10]
    ]) or "  Aucun"

    smoke_str = "\n".join([
        f"  - {f['test_class']}.{f['name']}"
        for f in ctx["smoke_failed"]
    ]) or "  Tous passés"

    crash_str = "\n".join([
        f"  - {f['test_class']}.{f['name']} (pattern: {f.get('pattern','?')})"
        for f in ctx["app_crashes"]
    ]) or "  Aucun"

    gate_info = (
        f"Quality Gate : {ctx['quality_gate']}"
        if ctx["quality_gate"] else "Quality Gate : non disponible (lancer kpi-agent.py)"
    )

    return [{
        "role": "user",
        "content": (
            f"Analyse ces résultats de tests MOBILES (Appium/Android) et décide si on peut livrer l'app en production.\n\n"
            f"APP TESTÉE : QAcart-To-Do.apk (Android)\n\n"
            f"RÉSULTATS :\n"
            f"  Total      : {ctx['total']} tests\n"
            f"  Passés     : {ctx['passed']} ({ctx['pass_rate']}%)\n"
            f"  Échoués    : {ctx['failed']} ({ctx['fail_rate']}%)\n"
            f"  Broken     : {ctx['broken']}\n"
            f"  {gate_info}\n\n"
            f"TESTS SMOKE EN ÉCHEC :\n{smoke_str}\n\n"
            f"CRASHES APP DÉTECTÉS :\n{crash_str}\n\n"
            f"TOUS LES ÉCHECS :\n{failures_str}\n\n"
            f"Règles de décision MOBILE :\n"
            f"  NO-GO immédiat si : app crash détecté OU pass_rate < 80% OU smoke test échoué\n"
            f"  NO-GO si          : fail_rate > 15%\n"
            f"  GO avec warning   : pass_rate 80-90% OU tests flaky connus\n"
            f"  GO clair          : pass_rate ≥ 90% ET aucun crash ET aucun smoke échoué\n"
        )
    }]


# ── Affichage ──────────────────────────────────────────────────────────────

def print_votes(result: dict, ctx: dict):
    majority  = result["majority_verdict"]
    agreement = result["agreement_rate"]
    unanimous = result["is_unanimous"]
    responses = result["responses"]
    minority  = result["minority_reasons"]
    votes     = result["votes"]

    banner_color = G if majority == "GO" else R
    banner_icon  = "✓ GO — LIVRAISON AUTORISÉE" if majority == "GO" else "✗ NO-GO — LIVRAISON BLOQUÉE"

    # Alertes spécifiques mobile
    if ctx["app_crashes"]:
        print(f"\n  {R}{W}⚠  APP CRASH DÉTECTÉ — blocant automatique{E}")
        for c in ctx["app_crashes"][:3]:
            print(f"  {R}✗{E} {c['test_class']}.{c['name']} ({c.get('pattern','?')})")

    if ctx["smoke_failed"]:
        print(f"\n  {R}{W}⚠  TESTS SMOKE EN ÉCHEC{E}")
        for s in ctx["smoke_failed"][:3]:
            print(f"  {R}✗{E} {s['test_class']}.{s['name']}")

    print(f"\n  {banner_color}{W}{'━'*54}{E}")
    print(f"  {banner_color}{W}  {banner_icon}{E}")
    print(f"  {banner_color}{W}{'━'*54}{E}")

    agree_color = G if agreement >= 0.8 else Y if agreement >= 0.6 else R
    unani_label = f" {G}(UNANIME){E}" if unanimous else ""
    votes_str   = "  ".join([f"{v}×{n}" for v, n in sorted(votes.items())])
    print(f"\n  Accord : {agree_color}{W}{int(agreement*100)}%{E}{unani_label}")
    print(f"  Votes  : {C}{votes_str}{E}")

    print(f"\n  {W}Détail des {len(responses)} votes :{E}")
    for r in responses:
        v       = r.get("verdict", "?")
        risk    = r.get("risk", "?")
        call_n  = r.get("_call", "?")
        v_color = G if v == "GO" else R
        r_color = G if risk == "low" else Y if risk == "medium" else R
        print(f"\n  {W}Vote #{call_n}{E}  →  {v_color}{W}{v}{E}  risque={r_color}{risk}{E}")
        print(f"  {r.get('reasoning','')[:100]}")
        for b in r.get("blockers", [])[:3]:
            print(f"    {R}✗ BLOCKER :{E} {b}")
        for w in r.get("warnings", [])[:2]:
            print(f"    {Y}⚠ WARNING :{E} {w}")

    if minority:
        print(f"\n  {Y}{W}Voix minoritaire(s) :{E}")
        for m in minority[:2]:
            print(f"  {Y}→ {m[:120]}{E}")


# ── Commandes ──────────────────────────────────────────────────────────────

def cmd_advise(n: int = 3) -> dict:
    print(f"\n{W}RELEASE ADVISOR MOBILE — Self-Consistency ({n} votes){E}")
    print(f"{C}  App : QAcart-To-Do.apk · Source : target/allure-results/{E}\n")

    ctx = collect_release_context()
    if ctx["total"] == 0:
        print(f"{Y}  Aucun résultat dans target/allure-results/.{E}")
        return {}

    print(f"  Contexte : {ctx['total']} tests | "
          f"{G}{ctx['pass_rate']}% pass{E} | "
          f"{R}{ctx['fail_rate']}% fail{E} | "
          f"{len(ctx['smoke_failed'])} smoke échoués | "
          f"{R if ctx['app_crashes'] else G}{len(ctx['app_crashes'])} crashes{E}")

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

    print_votes(result, ctx)
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
        v  = r.get("verdict", "?")
        vc = "#27ae60" if v == "GO" else "#e74c3c"
        rc = {"low": "#27ae60", "medium": "#e67e22", "high": "#e74c3c", "critical": "#c0392b"}.get(r.get("risk","medium"), "#888")
        bl = "".join([f'<li style="color:#e74c3c">{b}</li>' for b in r.get("blockers", [])])
        wa = "".join([f'<li style="color:#e67e22">{w}</li>' for w in r.get("warnings", [])])
        vote_rows += f"""
        <tr>
          <td style="text-align:center;font-weight:bold">#{r.get('_call','?')}</td>
          <td style="text-align:center"><span style="background:{vc};color:#fff;padding:3px 10px;border-radius:4px;font-weight:bold">{v}</span></td>
          <td style="text-align:center"><span style="color:{rc};font-weight:bold">{r.get('risk','?')}</span></td>
          <td style="font-size:12px">{r.get('reasoning','')[:100]}</td>
          <td style="font-size:11px"><ul style="margin:0;padding-left:16px">{bl or '—'}</ul></td>
          <td style="font-size:11px"><ul style="margin:0;padding-left:16px">{wa or '—'}</ul></td>
        </tr>"""

    votes_chart = "  ".join([
        f'<span style="background:{"#27ae60" if v=="GO" else "#e74c3c"};color:#fff;'
        f'padding:4px 14px;border-radius:20px;font-weight:bold;font-size:16px">'
        f'{v} × {n}</span>'
        for v, n in votes.items()
    ])

    crash_alert = ""
    if ctx.get("app_crashes"):
        crash_alert = f'<div style="background:#ffeaea;border:1px solid #e74c3c;border-radius:8px;padding:12px 16px;margin:12px 0;color:#c0392b;font-weight:bold">⚠ APP CRASH DÉTECTÉ — Livraison bloquée indépendamment du vote LLM</div>'

    html = f"""<!DOCTYPE html>
<html lang="fr"><head>
<meta charset="utf-8">
<title>Release Advisor Mobile — Go/No-Go</title>
<style>
  body{{font-family:Arial,sans-serif;background:#f0f2f5;color:#333;margin:0;padding:20px}}
  h1{{color:#2c3e50}} h2{{color:#34495e;margin-top:30px}}
  .banner{{background:{gate_color};color:#fff;padding:25px;border-radius:12px;text-align:center;font-size:28px;font-weight:bold;margin:20px 0;box-shadow:0 4px 12px rgba(0,0,0,.2)}}
  .stat{{display:inline-block;background:#fff;border-radius:10px;padding:15px 25px;margin:8px;box-shadow:0 2px 8px rgba(0,0,0,.1);text-align:center}}
  .stat-val{{font-size:28px;font-weight:bold}}.stat-lbl{{font-size:12px;color:#888;margin-top:4px}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1);margin-top:12px}}
  th{{background:#2c3e50;color:#fff;padding:10px 12px;text-align:left;font-size:13px}}
  td{{padding:10px 12px;border-bottom:1px solid #ecf0f1;vertical-align:top}}
  tr:hover{{background:#f8f9fa}}
</style>
</head><body>
<h1>📱 Release Advisor — Mobile Self-Consistency Go/No-Go</h1>
<p style="color:#666">Self-Consistency : {len(responses)} votes avec températures différentes → vote majoritaire · App : QAcart-To-Do.apk</p>
{crash_alert}
<div class="banner">{'✓ GO — LIVRAISON AUTORISÉE' if majority=='GO' else '✗ NO-GO — LIVRAISON BLOQUÉE'}</div>
<div>
  <div class="stat"><div class="stat-val">{len(responses)}</div><div class="stat-lbl">Votes LLM</div></div>
  <div class="stat"><div class="stat-val" style="color:{gate_color}">{int(agreement*100)}%</div><div class="stat-lbl">Accord {'(unanime)' if result['is_unanimous'] else ''}</div></div>
  <div class="stat"><div class="stat-val" style="color:#27ae60">{ctx.get('pass_rate',0)}%</div><div class="stat-lbl">Pass Rate</div></div>
  <div class="stat"><div class="stat-val" style="color:#e74c3c">{len(ctx.get('smoke_failed',[]))}</div><div class="stat-lbl">Smoke échoués</div></div>
  <div class="stat"><div class="stat-val" style="color:#e74c3c">{len(ctx.get('app_crashes',[]))}</div><div class="stat-lbl">App Crashes</div></div>
</div>
<h2>Résultat du vote</h2>
<div style="margin:15px 0">{votes_chart}</div>
<h2>Détail des {len(responses)} votes</h2>
<table>
  <tr><th>Vote</th><th>Verdict</th><th>Risque</th><th>Raisonnement</th><th>Blockers</th><th>Warnings</th></tr>
  {vote_rows}
</table>
<p style="color:#999;font-size:12px;margin-top:30px">
  Release Advisor Mobile — Self-Consistency · App : QAcart-To-Do.apk
</p>
</body></html>"""

    out = os.path.join(DOCS_DIR, "release-report.html")
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n{G}  Rapport HTML : docs/release-report.html{E}")


def print_help():
    print(f"""
{W}RELEASE ADVISOR MOBILE — Self-Consistency Go/No-Go{E}
Source : target/allure-results/  |  App : QAcart-To-Do.apk

  python agents/release-advisor-agent.py advise      3 votes (défaut)
  python agents/release-advisor-agent.py advise 5    5 votes
  python agents/release-advisor-agent.py report      Rapport HTML

{W}Règles de décision MOBILE :{E}
  NO-GO immédiat  → app crash | pass_rate < 80% | smoke échoué
  NO-GO           → fail_rate > 15%
  GO avec warning → pass_rate 80-90% | flaky connus
  GO clair        → pass_rate ≥ 90% | aucun crash | aucun smoke échoué
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
