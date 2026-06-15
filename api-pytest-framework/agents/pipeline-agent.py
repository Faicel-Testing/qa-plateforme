# ============================================================
# Pipeline Agent — Orchestrateur Maître
# ============================================================
# Commandes :
#   python agents/pipeline-agent.py full       → pipeline complet (plan + run + bug + report + gate)
#   python agents/pipeline-agent.py quick      → smoke + quality gate + notify
#   python agents/pipeline-agent.py nightly    → regression + report + predict + tickets
#   python agents/pipeline-agent.py report     → run + report + notify sans gate bloquant
#   python agents/pipeline-agent.py status     → état actuel des agents (santé du pipeline)
#   python agents/pipeline-agent.py gate       → quality gate uniquement (CI/CD check)
# ============================================================

import sys, os, json, time, subprocess
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

FRAMEWORK = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

PYTHON = sys.executable
AGENTS = os.path.dirname(__file__)


# ── Runner helper ──────────────────────────────────────────────────────────

def run_agent(agent: str, *args, label: str = None) -> tuple[bool, str]:
    """Lance un sous-agent et retourne (ok, output)."""
    tag = label or f"{agent} {' '.join(args)}"
    print(f"  {C}>>>{E} {tag}...", flush=True)

    script = os.path.join(AGENTS, f"{agent}.py")
    cmd    = [PYTHON, script] + list(args)
    result = subprocess.run(cmd, cwd=FRAMEWORK, capture_output=True, text=True, encoding="utf-8", errors="replace")

    out  = (result.stdout or "").strip()
    ok   = result.returncode == 0
    icon = f"{G}OK{E}" if ok else f"{R}FAIL{E}"
    print(f"  {icon}  {tag}")
    if not ok and result.stderr:
        print(f"    {Y}{result.stderr[:200]}{E}")
    return ok, out


def section(title: str):
    width = 60
    print(f"\n{W}{'─'*width}{E}")
    print(f"{W}  {title}{E}")
    print(f"{W}{'─'*width}{E}")


def step(n: int, total: int, label: str):
    print(f"\n{C}[{n}/{total}]{E} {W}{label}{E}")


# ── Pipeline: FULL ─────────────────────────────────────────────────────────
# Ordre : sync jira → smoke → regression → triage/rca → report → gate → predict

def cmd_full():
    t0 = time.time()
    section("PIPELINE COMPLET — FULL")
    print(f"  Démarré à {time.strftime('%H:%M:%S')}")

    results = {}
    TOTAL = 8

    step(1, TOTAL, "Synchronisation Jira")
    ok, _ = run_agent("planning-agent", "sync", label="planning-agent sync")
    results["jira_sync"] = ok

    step(2, TOTAL, "Smoke Tests")
    ok, _ = run_agent("runner-agent", "smoke", label="runner-agent smoke")
    results["smoke"] = ok

    step(3, TOTAL, "Regression Tests")
    ok, _ = run_agent("runner-agent", "regression", label="runner-agent regression")
    results["regression"] = ok

    step(4, TOTAL, "Triage & RCA")
    ok, _ = run_agent("bug-agent", "loop", label="bug-agent loop")
    results["bug_loop"] = ok  # non bloquant

    step(5, TOTAL, "KPI & Quality Gate")
    ok, _ = run_agent("quality-agent", "kpi", label="quality-agent kpi")
    results["kpi"] = ok
    ok, _ = run_agent("quality-agent", "gate", label="quality-agent gate")
    results["gate"] = ok

    step(6, TOTAL, "Rapport Allure + Notification")
    ok, _ = run_agent("reporting-agent", "publish", label="reporting-agent publish")
    results["report"] = ok

    step(7, TOTAL, "Prédiction & Adviseur Release")
    ok, _ = run_agent("advisor-agent", "predict", label="advisor-agent predict")
    results["predict"] = ok

    step(8, TOTAL, "Tickets Jira depuis échecs")
    ok, _ = run_agent("planning-agent", "tickets", label="planning-agent tickets")
    results["tickets"] = ok

    elapsed = round(time.time() - t0, 1)
    _print_summary(results, elapsed)

    gate_ok = results.get("gate", False)
    sys.exit(0 if gate_ok else 1)


# ── Pipeline: QUICK ─────────────────────────────────────────────────────────

def cmd_quick():
    t0 = time.time()
    section("PIPELINE RAPIDE — QUICK")
    print(f"  Démarré à {time.strftime('%H:%M:%S')}")

    results = {}
    TOTAL = 3

    step(1, TOTAL, "Smoke Tests")
    ok, _ = run_agent("runner-agent", "smoke", label="runner-agent smoke")
    results["smoke"] = ok

    step(2, TOTAL, "Quality Gate")
    ok, _ = run_agent("quality-agent", "gate", label="quality-agent gate")
    results["gate"] = ok

    step(3, TOTAL, "Notification")
    run_agent("reporting-agent", "notify", label="reporting-agent notify")

    elapsed = round(time.time() - t0, 1)
    _print_summary(results, elapsed)

    sys.exit(0 if results.get("gate") else 1)


# ── Pipeline: NIGHTLY ──────────────────────────────────────────────────────

def cmd_nightly():
    t0 = time.time()
    section("PIPELINE NIGHTLY — REGRESSION COMPLETE")
    print(f"  Démarré à {time.strftime('%H:%M:%S')}")

    results = {}
    TOTAL = 7

    step(1, TOTAL, "Tests Critiques")
    ok, _ = run_agent("runner-agent", "critical", label="runner-agent critical")
    results["critical"] = ok

    step(2, TOTAL, "Tests Regression complet")
    ok, _ = run_agent("runner-agent", "regression", label="runner-agent regression")
    results["regression"] = ok

    step(3, TOTAL, "Flaky Detection (3 runs)")
    ok, _ = run_agent("quality-agent", "flaky", "--runs=3", label="quality-agent flaky")
    results["flaky"] = ok

    step(4, TOTAL, "Triage & Agentic Loop")
    ok, _ = run_agent("bug-agent", "loop", label="bug-agent loop")
    results["bug_loop"] = ok

    step(5, TOTAL, "Rapport HTML")
    ok, _ = run_agent("reporting-agent", "generate", label="reporting-agent generate")
    results["report"] = ok

    step(6, TOTAL, "Prédiction & Recommandations")
    ok, _ = run_agent("advisor-agent", "recommend", label="advisor-agent recommend")
    results["predict"] = ok

    step(7, TOTAL, "Tickets Jira depuis échecs")
    ok, _ = run_agent("planning-agent", "tickets", label="planning-agent tickets")
    results["tickets"] = ok

    elapsed = round(time.time() - t0, 1)
    _print_summary(results, elapsed)

    sys.exit(0 if results.get("regression") else 1)


# ── Pipeline: REPORT ───────────────────────────────────────────────────────

def cmd_report():
    t0 = time.time()
    section("PIPELINE REPORT — Run + Rapport + Notify")

    results = {}
    TOTAL = 3

    step(1, TOTAL, "Smoke Tests")
    ok, _ = run_agent("runner-agent", "smoke", label="runner-agent smoke")
    results["smoke"] = ok

    step(2, TOTAL, "KPI Dashboard")
    ok, _ = run_agent("quality-agent", "kpi", label="quality-agent kpi")
    results["kpi"] = ok

    step(3, TOTAL, "Publish Rapport + Notification")
    ok, _ = run_agent("reporting-agent", "publish", label="reporting-agent publish")
    results["publish"] = ok

    elapsed = round(time.time() - t0, 1)
    _print_summary(results, elapsed)


# ── Pipeline: GATE ─────────────────────────────────────────────────────────

def cmd_gate():
    section("QUALITY GATE — CI/CD Check")
    ok, out = run_agent("quality-agent", "gate", label="quality-agent gate")
    print(f"\n  {G if ok else R}Gate : {'PASSED' if ok else 'FAILED'}{E}")
    sys.exit(0 if ok else 1)


# ── Status — Santé du pipeline ─────────────────────────────────────────────

def cmd_status():
    section("PIPELINE STATUS")

    agents = [
        ("runner-agent",       "run --help"),
        ("bug-agent",          "--help"),
        ("codegen-agent",      "--help"),
        ("quality-agent",      "--help"),
        ("reporting-agent",    "--help"),
        ("advisor-agent",      "--help"),
        ("observability-agent","--help"),
        ("ci-agent",           "--help"),
        ("planning-agent",     "--help"),
        ("pipeline-agent",     "status"),
    ]

    import glob as _glob
    agents_dir = AGENTS

    print(f"\n  {'Agent':<28} {'Fichier':<10} {'Statut'}")
    print(f"  {'─'*28} {'─'*10} {'─'*20}")

    for agent_name, _ in agents:
        if agent_name == "pipeline-agent":
            present = True
        else:
            path = os.path.join(agents_dir, f"{agent_name}.py")
            present = os.path.exists(path)

        size = ""
        if present and agent_name != "pipeline-agent":
            size = f"{os.path.getsize(os.path.join(agents_dir, f'{agent_name}.py'))//1024}KB"

        icon = f"{G}OK{E}" if present else f"{R}MANQUANT{E}"
        print(f"  {agent_name:<28} {size:<10} {icon}")

    # État circuit breaker
    cb_file = os.path.join(FRAMEWORK, "logs", "circuit_breaker_state.json")
    if os.path.exists(cb_file):
        try:
            cb = json.load(open(cb_file, encoding="utf-8"))
            state = cb.get("state", "?")
            color = G if state == "CLOSED" else R
            print(f"\n  Circuit Breaker : {color}{state}{E}")
        except Exception:
            pass

    # Allure results count
    import glob as _g
    n_results = len(_g.glob(os.path.join(FRAMEWORK, "allure-results", "*-result.json")))
    print(f"  Allure results  : {C}{n_results} fichier(s){E}")

    # Traces
    traces_file = os.path.join(FRAMEWORK, "logs", "traces.jsonl")
    if os.path.exists(traces_file):
        n_traces = sum(1 for _ in open(traces_file, encoding="utf-8", errors="replace"))
        print(f"  Traces LLM      : {C}{n_traces} appel(s){E}")


# ── Summary printer ────────────────────────────────────────────────────────

def _print_summary(results: dict, elapsed: float):
    section("RÉSUMÉ DU PIPELINE")
    total   = len(results)
    success = sum(1 for v in results.values() if v)
    failed  = total - success

    for step_name, ok in results.items():
        icon = f"{G}PASS{E}" if ok else f"{R}FAIL{E}"
        print(f"  {icon}  {step_name}")

    print(f"\n  {G if not failed else Y}{success}/{total} étapes réussies{E}  |  {elapsed}s")
    if failed:
        print(f"  {R}{failed} étape(s) en échec — voir les logs ci-dessus.{E}")
    else:
        print(f"  {G}Pipeline terminé avec succès.{E}")


# ── Main ───────────────────────────────────────────────────────────────────

def print_help():
    print(f"""
{W}PIPELINE AGENT — Orchestrateur Maître{E}

  python agents/pipeline-agent.py full      Pipeline complet  (sync→smoke→regression→bug→report→gate→predict→tickets)
  python agents/pipeline-agent.py quick     Pipeline rapide   (smoke→gate→notify)
  python agents/pipeline-agent.py nightly   Pipeline nightly  (critical→regression→flaky→bug→report→predict→tickets)
  python agents/pipeline-agent.py report    Run + rapport     (smoke→kpi→publish)
  python agents/pipeline-agent.py gate      Quality gate CI   (gate uniquement → exit 0/1)
  python agents/pipeline-agent.py status    État du pipeline  (agents + circuit breaker + traces)

{W}Agents orchestrés :{E}
  runner-agent · bug-agent · codegen-agent · quality-agent
  reporting-agent · advisor-agent · observability-agent
  ci-agent · planning-agent
""")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "full":
        cmd_full()
    elif cmd == "quick":
        cmd_quick()
    elif cmd == "nightly":
        cmd_nightly()
    elif cmd == "report":
        cmd_report()
    elif cmd == "gate":
        cmd_gate()
    elif cmd == "status":
        cmd_status()
    else:
        print_help()
