# ============================================================
# Pipeline Agent — Orchestrateur maître ui_selenium_bdd
# ============================================================
# Commandes :
#   python agents/pipeline-agent.py full        → planning→codegen→run→quality→bug→report→advisor→ci
#   python agents/pipeline-agent.py quick       → run→triage→kpi→gate
#   python agents/pipeline-agent.py nightly     → full en mode regression
#   python agents/pipeline-agent.py smoke       → @smoke uniquement + gate
#   python agents/pipeline-agent.py gate        → quality gate seule
#   python agents/pipeline-agent.py status      → état rapide du framework
#   python agents/pipeline-agent.py report      → rapport complet sans run
# ============================================================

import sys, os, json, glob, time, subprocess
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

FRAMEWORK = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
B = "\033[34m"; M = "\033[35m"; W = "\033[1m";  E = "\033[0m"

AGENTS_DIR   = os.path.join(FRAMEWORK, "agents")
ALLURE_DIR   = os.path.join(FRAMEWORK, "target", "allure-results")
FEATURES_DIR = os.path.join(FRAMEWORK, "src", "test", "resources", "features")

QUALITY_GATE = {"pass_rate": 90.0, "fail_rate": 5.0, "confidence": 0.70}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _call(agent: str, *args, label: str = None, silent: bool = False):
    lbl = label or f"{agent} {' '.join(args)}"
    print(f"\n  {C}▶ {lbl}{E}")
    result = subprocess.run(
        [sys.executable, os.path.join(AGENTS_DIR, agent)] + list(args),
        cwd=FRAMEWORK, capture_output=silent, text=True
    )
    if not silent:
        return result.returncode
    if result.stdout:
        for line in result.stdout.strip().split("\n")[:5]:
            print(f"    {line}")
    return result.returncode


def _load_stats() -> dict:
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
    pass_rate = round(passed / total * 100, 1) if total else 0
    fail_rate = round((failed + broken) / total * 100, 1) if total else 0
    return dict(total=total, passed=passed, failed=failed, broken=broken,
                pass_rate=pass_rate, fail_rate=fail_rate)


def _gate_check(stats: dict) -> bool:
    ok = stats["pass_rate"] >= QUALITY_GATE["pass_rate"] and \
         stats["fail_rate"] <= QUALITY_GATE["fail_rate"]
    color = G if ok else R
    icon  = "✅" if ok else "❌"
    print(f"\n  {color}{W}{icon} QUALITY GATE : {'PASS' if ok else 'FAIL'}{E}")
    print(f"  Pass rate : {stats['pass_rate']}% (seuil ≥ {QUALITY_GATE['pass_rate']}%)")
    print(f"  Fail rate : {stats['fail_rate']}% (seuil ≤ {QUALITY_GATE['fail_rate']}%)")
    return ok


def _separator(title: str):
    print(f"\n{B}{'='*60}{E}")
    print(f"{B}  {title}{E}")
    print(f"{B}{'='*60}{E}")


# ── Pipelines ──────────────────────────────────────────────────────────────────

def cmd_full():
    _separator("PIPELINE FULL — ui_selenium_bdd")
    start = time.time()
    steps = [
        ("1/8  Planning    ", "planning-agent.py", ["coverage"]),
        ("2/8  Codegen     ", "codegen-agent.py",  ["list"]),
        ("3/8  Run tests   ", "runner-agent.py",   ["run"]),
        ("4/8  Quality     ", "quality-agent.py",  ["analyze"]),
        ("5/8  Bug triage  ", "bug-agent.py",      ["triage"]),
        ("6/8  Reporting   ", "reporting-agent.py",["publish"]),
        ("7/8  Advisor     ", "advisor-agent.py",  ["release"]),
        ("8/8  CI commit   ", "ci-agent.py",       ["commit"]),
    ]
    results = {}
    for label, agent, args in steps:
        print(f"\n{M}  ┌── {label}{E}")
        rc = _call(agent, *args, label=f"{agent} {' '.join(args)}")
        results[label] = "✓" if rc == 0 else "✗"
        print(f"{M}  └── {'OK' if rc == 0 else 'FAIL'}{E}")

    elapsed = round(time.time() - start, 1)
    _separator("PIPELINE RÉSULTAT")
    for label, status in results.items():
        color = G if status == "✓" else R
        print(f"  {color}{status}{E}  {label}")
    stats = _load_stats()
    gate_ok = _gate_check(stats)
    print(f"\n  Durée totale : {elapsed}s")
    return 0 if gate_ok else 1


def cmd_quick():
    _separator("PIPELINE QUICK — Run → Triage → KPI → Gate")
    start = time.time()
    _call("runner-agent.py", "run", label="Runner — mvn test")
    _call("bug-agent.py", "triage", label="Bug — triage auto")
    _call("quality-agent.py", "kpi", label="Quality — KPI")
    stats = _load_stats()
    gate_ok = _gate_check(stats)
    print(f"\n  Durée : {round(time.time() - start, 1)}s")
    return 0 if gate_ok else 1


def cmd_smoke():
    _separator("PIPELINE SMOKE — @smoke uniquement")
    start = time.time()
    _call("runner-agent.py", "smoke", label="Runner — smoke suite")
    stats = _load_stats()
    gate_ok = _gate_check(stats)
    if gate_ok:
        _call("reporting-agent.py", "notify", label="Notify — Slack")
    print(f"\n  Durée : {round(time.time() - start, 1)}s")
    return 0 if gate_ok else 1


def cmd_nightly():
    _separator("PIPELINE NIGHTLY — Regression complète")
    start = time.time()
    _call("runner-agent.py", "regression", label="Runner — regression")
    _call("quality-agent.py", "flaky", label="Quality — flaky analysis")
    _call("quality-agent.py", "analyze", label="Quality — analyze")
    _call("bug-agent.py", "triage", label="Bug — triage")
    _call("reporting-agent.py", "publish", label="Reporting — publish")
    _call("advisor-agent.py", "predict", label="Advisor — predict")
    stats = _load_stats()
    gate_ok = _gate_check(stats)
    _call("planning-agent.py", "sync", label="Planning — sync Jira")
    print(f"\n  Durée nightly : {round(time.time() - start, 1)}s")
    return 0 if gate_ok else 1


def cmd_gate():
    _separator("QUALITY GATE — Vérification")
    stats = _load_stats()
    if stats["total"] == 0:
        print(f"  {Y}Aucun résultat Allure. Lance d'abord : pipeline-agent.py quick{E}")
        return 1
    gate_ok = _gate_check(stats)
    if not gate_ok:
        _call("bug-agent.py", "triage", label="Bug — triage auto")
    return 0 if gate_ok else 1


def cmd_report():
    _separator("PIPELINE REPORT — Sans run")
    _call("quality-agent.py", "kpi", label="Quality — KPI")
    _call("quality-agent.py", "analyze", label="Quality — analyze")
    _call("reporting-agent.py", "dashboard", label="Reporting — dashboard")
    _call("observability-agent.py", "dashboard", label="Observability — dashboard")
    _call("advisor-agent.py", "report", label="Advisor — report")


def cmd_status():
    _separator("STATUS — Tableau de bord rapide")
    features = glob.glob(os.path.join(FEATURES_DIR, "*.feature"))
    stats = _load_stats()

    cb_state = "CLOSED"
    cb_file = os.path.join(FRAMEWORK, "logs", "circuit_breaker_state.json")
    if os.path.exists(cb_file):
        with open(cb_file, encoding="utf-8") as f:
            cb_state = json.load(f).get("state", "CLOSED")

    cb_color = G if cb_state == "CLOSED" else (Y if cb_state == "HALF_OPEN" else R)

    print(f"""
  {W}ui_selenium_bdd — automationexercise.com{E}
  ────────────────────────────────────────
  Features       : {G}{len(features)}{E} fichiers .feature
  Tests total    : {C}{stats['total']}{E}
  Passed         : {G}{stats['passed']}{E}
  Failed/Broken  : {R}{stats['failed'] + stats['broken']}{E}
  Pass rate      : {G if stats['pass_rate'] >= 90 else Y}{stats['pass_rate']}%{E}
  Fail rate      : {G if stats['fail_rate'] <= 5 else R}{stats['fail_rate']}%{E}
  Circuit Breaker: {cb_color}{cb_state}{E}
  ────────────────────────────────────────
  {C}Commandes rapides :{E}
    python agents/pipeline-agent.py smoke    → @smoke
    python agents/pipeline-agent.py quick    → run + triage + gate
    python agents/pipeline-agent.py full     → pipeline complet
    python agents/pipeline-agent.py nightly  → regression + rapport
""")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Pipeline Agent — Orchestrateur ui_selenium_bdd")
    parser.add_argument("command", nargs="?", default="status",
                        choices=["full", "quick", "nightly", "smoke", "gate", "report", "status"])
    args = parser.parse_args()

    if args.command == "full":     sys.exit(cmd_full())
    elif args.command == "quick":  sys.exit(cmd_quick())
    elif args.command == "nightly": sys.exit(cmd_nightly())
    elif args.command == "smoke":  sys.exit(cmd_smoke())
    elif args.command == "gate":   sys.exit(cmd_gate())
    elif args.command == "report": cmd_report()
    elif args.command == "status": cmd_status()
