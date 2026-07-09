# ============================================================
# Runner Agent — Exécution des tests API RestAssured (Maven)
# ============================================================
# Commandes :
#   python agents/runner-agent.py run [env]         → tous les tests
#   python agents/runner-agent.py smoke [env]       → @smoke uniquement
#   python agents/runner-agent.py critical [env]    → @critical
#   python agents/runner-agent.py regression [env]  → @regression
#   python agents/runner-agent.py flaky [--runs=3]  → détection flaky
#   python agents/runner-agent.py baseline          → sauvegarde baseline
#   python agents/runner-agent.py gono-go           → run + quality gate
# ============================================================

import sys, os, json, glob, subprocess, time, argparse
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm

FRAMEWORK  = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TARGET_DIR = os.path.join(FRAMEWORK, "target")
ALLURE_DIR = os.path.join(TARGET_DIR, "allure-results")
DOCS_DIR   = os.path.join(FRAMEWORK, "docs")
BASELINE   = os.path.join(DOCS_DIR, "baseline.json")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

QUALITY_GATE = {"pass_rate": 90.0, "fail_rate": 5.0}


# ── Maven ────────────────────────────────────────────────────────────────────

MVN = "mvn.cmd" if sys.platform == "win32" else "mvn"


def mvn(args: list, env_name: str = "local") -> int:
    cmd = [MVN, "clean", "test", f"-Denv={env_name}"] + args
    print(f"\n{C}  mvn {' '.join(args)}{E}")
    result = subprocess.run(cmd, cwd=FRAMEWORK)
    return result.returncode


def mvn_tag(tag: str, env_name: str = "local") -> int:
    return mvn([f'-Dcucumber.filter.tags={tag}'], env_name)


# ── Lecture résultats Allure ───────────────────────────────────────────────────

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
    return {
        "total": total, "passed": passed, "failed": failed,
        "broken": broken, "skipped": skipped,
        "pass_rate": pass_rate, "fail_rate": fail_rate,
    }


def print_stats(stats: dict):
    gate_ok = stats["pass_rate"] >= QUALITY_GATE["pass_rate"] and stats["fail_rate"] <= QUALITY_GATE["fail_rate"]
    color   = G if gate_ok else R
    print(f"\n  {W}Résultats :{E}")
    print(f"  Total   : {stats['total']}")
    print(f"  {G}Passés  : {stats['passed']}{E}")
    print(f"  {R}Échoués : {stats['failed']}{E}")
    print(f"  {Y}Brisés  : {stats['broken']}{E}")
    print(f"  {color}Pass rate : {stats['pass_rate']}%{E}  |  Fail rate : {stats['fail_rate']}%")
    print(f"  {color}Quality Gate : {'PASS ✓' if gate_ok else 'FAIL ✗'}{E}")


# ── Commandes ──────────────────────────────────────────────────────────────────

def cmd_run(env: str = "local"):
    print(f"\n{W}RUNNER — Tous les tests (env={env}){E}")
    rc = mvn([], env)
    results = load_results()
    if results:
        print_stats(parse_stats(results))
    return rc


def cmd_smoke(env: str = "local"):
    print(f"\n{W}RUNNER — Smoke tests @smoke (env={env}){E}")
    rc = mvn_tag("@smoke", env)
    results = load_results()
    if results:
        print_stats(parse_stats(results))
    return rc


def cmd_critical(env: str = "local"):
    print(f"\n{W}RUNNER — Tests critiques @critical (env={env}){E}")
    rc = mvn_tag("@critical", env)
    results = load_results()
    if results:
        print_stats(parse_stats(results))
    return rc


def cmd_regression(env: str = "local"):
    print(f"\n{W}RUNNER — Régression (env={env}){E}")
    rc = mvn([], env)
    results = load_results()
    if results:
        print_stats(parse_stats(results))
    return rc


def cmd_flaky(runs: int = 3, env: str = "local"):
    print(f"\n{W}RUNNER — Détection flaky ({runs} runs, env={env}){E}")
    history = {}
    for i in range(runs):
        print(f"\n  {C}Run {i+1}/{runs}{E}")
        mvn([], env)
        for r in load_results():
            name = r.get("name", "?")
            history.setdefault(name, []).append(r.get("status", "unknown"))

    flaky = {n: statuses for n, statuses in history.items() if len(set(statuses)) > 1}
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, "flaky-report.json"), "w", encoding="utf-8") as f:
        json.dump({"runs": runs, "flaky": flaky, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")}, f, indent=2, ensure_ascii=False)

    if flaky:
        print(f"\n  {R}{len(flaky)} test(s) flaky :{E}")
        for name, statuses in flaky.items():
            print(f"  {Y}[{'/'.join(statuses)}]{E} {name[:65]}")
        flaky_text = "\n".join(f"- {n}: {' / '.join(s)}" for n, s in list(flaky.items())[:10])
        messages = [{"role": "user", "content": (
            f"Ces tests API RestAssured sont flaky ({runs} runs) :\n{flaky_text}\n\n"
            f"En 3 points, explique les causes probables (API publique partagée, timing, données) "
            f"et propose des actions de stabilisation."
        )}]
        print(f"\n{W}  Analyse LLM :{E}")
        try:
            for line in llm.chat(messages).strip().split("\n"):
                print(f"  {line}")
        except Exception as e:
            print(f"  {Y}LLM indisponible : {e}{E}")
    else:
        print(f"  {G}Aucun test flaky détecté sur {runs} runs.{E}")
    return flaky


def cmd_baseline():
    print(f"\n{W}RUNNER — Sauvegarde baseline{E}")
    results = load_results()
    if not results:
        print(f"  {R}Aucun résultat Allure — lance d'abord un run.{E}")
        return
    stats = parse_stats(results)
    os.makedirs(DOCS_DIR, exist_ok=True)
    baseline = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "stats": stats,
        "tests": [{"name": r["name"], "status": r["status"]} for r in results],
    }
    with open(BASELINE, "w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2, ensure_ascii=False)
    print(f"  {G}Baseline sauvegardée ({stats['total']} tests, {stats['pass_rate']}% pass).{E}")
    print(f"  Fichier : docs/baseline.json")


def cmd_gonogo(env: str = "local"):
    print(f"\n{W}RUNNER — Go/No-Go (run + gate, env={env}){E}")
    cmd_run(env)
    results = load_results()
    if not results:
        print(f"  {R}Aucun résultat.{E}")
        return False
    stats = parse_stats(results)
    gate_ok = stats["pass_rate"] >= QUALITY_GATE["pass_rate"] and stats["fail_rate"] <= QUALITY_GATE["fail_rate"]
    if gate_ok:
        print(f"\n  {G}{W}GO — Déploiement autorisé{E}")
    else:
        print(f"\n  {R}{W}NO-GO — Déploiement bloqué{E}")
        if stats["pass_rate"] < QUALITY_GATE["pass_rate"]:
            print(f"  {R}Pass rate {stats['pass_rate']}% < 90%{E}")
        if stats["fail_rate"] > QUALITY_GATE["fail_rate"]:
            print(f"  {R}Fail rate {stats['fail_rate']}% > 5%{E}")
    return gate_ok


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Runner Agent — API RestAssured Maven")
    parser.add_argument("command", choices=["run", "smoke", "critical", "regression",
                                             "flaky", "baseline", "gono-go"])
    parser.add_argument("env", nargs="?", default="local",
                        choices=["local", "staging", "production"])
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()

    cmd = args.command
    env = args.env

    if cmd == "run":          cmd_run(env)
    elif cmd == "smoke":      cmd_smoke(env)
    elif cmd == "critical":   cmd_critical(env)
    elif cmd == "regression": cmd_regression(env)
    elif cmd == "flaky":      cmd_flaky(args.runs, env)
    elif cmd == "baseline":   cmd_baseline()
    elif cmd == "gono-go":    cmd_gonogo(env)
