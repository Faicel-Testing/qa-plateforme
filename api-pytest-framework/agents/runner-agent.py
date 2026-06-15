# ============================================================
# Runner Agent — Exécution des tests API (pytest)
# ============================================================
# Absorbe : api-execute-agent · smoke-regression-agent
#
# Commandes :
#   python agents/runner-agent.py run                → suite complète
#   python agents/runner-agent.py smoke              → 5 TCs smoke
#   python agents/runner-agent.py critical           → 9 TCs critiques
#   python agents/runner-agent.py regression         → suite vs baseline
#   python agents/runner-agent.py gono-go            → verdict production
#   python agents/runner-agent.py baseline           → enregistre la baseline
# ============================================================

import sys, os, subprocess, json, glob, time, requests, tempfile
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

from jira_fetcher_agent import JiraClient, JIRA_BASE_URL
import llm

FRAMEWORK    = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS_DIR  = os.path.join(FRAMEWORK, "allure-results")
BASELINE_FILE = os.path.join(FRAMEWORK, "docs", "baseline.json")
INI_PATH     = os.path.join(FRAMEWORK, "pytest.ini")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

VERDICT_GO   = f"{G}{W}  GO  {E}"
VERDICT_NOGO = f"{R}{W} NO-GO {E}"


# ── Helpers ────────────────────────────────────────────────────────────────

def run_pytest(marker: str, label: str, extra_args: list = None) -> tuple:
    """Retourne (returncode, result_dir) avec répertoire isolé."""
    print(f"\n{C}[>] Execution : {label}{E}")
    result_dir = tempfile.mkdtemp(prefix="api_results_")
    cmd = [
        sys.executable, "-m", "pytest",
        f"--rootdir={FRAMEWORK}",
        "-c", INI_PATH,
        "--override-ini=addopts=",
        "--alluredir", result_dir,
        "--ignore=tests/test_booking_bdd.py",
        "--tb=short", "-q",
        "tests/",
    ]
    if marker:
        cmd += ["-m", marker]
    if extra_args:
        cmd += extra_args
    proc = subprocess.run(cmd, cwd=FRAMEWORK, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return proc.returncode, result_dir


def parse_results(results_dir: str) -> dict:
    stats    = {"passed": 0, "failed": 0, "broken": 0, "skipped": 0, "total": 0}
    failures = []
    for f in glob.glob(os.path.join(results_dir, "*-result.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
            s = d.get("status", "unknown")
            if s in stats:
                stats[s] += 1
            stats["total"] += 1
            if s in ("failed", "broken"):
                tags   = [lb["value"] for lb in d.get("labels", []) if lb["name"] == "tag"]
                tc_tag = next((t for t in tags if t.startswith("tc-")), None)
                failures.append({
                    "name":    d.get("name", "?"),
                    "tc_tag":  tc_tag,
                    "message": (d.get("statusDetails") or {}).get("message", "")[:200],
                    "status":  s,
                })
        except Exception:
            pass
    return {"stats": stats, "failures": failures}


def print_result(label: str, data: dict):
    s   = data["stats"]
    tot = s["total"] or 1
    pct = round(s["passed"] / tot * 100)
    bar_ok = "#" * (pct // 5)
    bar_ko = "." * (20 - pct // 5)
    color  = G if s["failed"] == 0 and s["broken"] == 0 else R
    print(f"\n{W}  {label}{E}")
    print(f"  [{color}{bar_ok}{E}{bar_ko}] {pct}%  |  Total:{s['total']}  "
          f"PASS:{G}{s['passed']}{E}  FAIL:{R}{s['failed']}{E}  BROKEN:{Y}{s['broken']}{E}")
    if data["failures"]:
        print(f"\n{R}  Echecs :{E}")
        for f in data["failures"]:
            print(f"  {R}x{E} [{f['tc_tag'] or '?'}] {f['name'][:65]}")
            if f["message"]:
                print(f"    {Y}-> {f['message'][:100]}{E}")


def load_baseline() -> dict:
    if os.path.exists(BASELINE_FILE):
        with open(BASELINE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_baseline(data: dict):
    os.makedirs(os.path.dirname(BASELINE_FILE), exist_ok=True)
    with open(BASELINE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"{G}  [OK] Baseline -> docs/baseline.json{E}")


def detect_regressions(current: dict, baseline: dict) -> list:
    current_fails = {f["name"] for f in current.get("failures", [])}
    baseline_passed = baseline.get("passed_tests", [])
    return [n for n in baseline_passed if n in current_fails]


def create_jira_bug(jira: JiraClient, tc_tag: str, test_name: str, message: str, verdict_type: str):
    summary = f"[{verdict_type.upper()}] Regression : {test_name[:60]}"
    description = {
        "type": "doc", "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": (
            f"Test : {test_name}\nTag  : {tc_tag or 'N/A'}\nType : {verdict_type}\n\n"
            f"Erreur :\n{message}\n\n-> BLOQUE GO/NO-GO PRODUCTION"
        )}]}]
    }
    payload = {
        "fields": {
            "project": {"key": "HBAPI"},
            "summary": summary,
            "description": description,
            "issuetype": {"name": "Bug"},
            "priority": {"name": "Highest"},
            "labels": ["regression", "gono-go", "production-blocker"],
        }
    }
    resp = requests.post(
        f"{JIRA_BASE_URL}/rest/api/3/issue",
        json=payload, auth=jira.auth, headers=jira.headers, verify=False
    )
    if resp.status_code == 201:
        key = resp.json()["key"]
        print(f"{R}  [BUG] Jira : {key}{E}")
        return key
    return None


# ── Commandes ──────────────────────────────────────────────────────────────

def cmd_run():
    """Suite complète sans filtrage."""
    print(f"\n{W}{'='*55}{E}\n{W}  RUNNER — Suite complete{E}\n{W}{'='*55}{E}")
    rc, rdir = run_pytest("", "Suite complete")
    data = parse_results(rdir)
    print_result("Resultats", data)
    s = data["stats"]
    ok = s["failed"] == 0 and s["broken"] == 0
    print(f"\n  Verdict : {VERDICT_GO if ok else VERDICT_NOGO}")
    return ok, data


def cmd_smoke():
    print(f"\n{W}{'='*55}{E}\n{W}  SMOKE TESTS{E}\n{W}{'='*55}{E}")
    rc, rdir = run_pytest("smoke", "Smoke (5 TCs)")
    data = parse_results(rdir)
    print_result("Resultats Smoke", data)
    ok = data["stats"]["failed"] == 0 and data["stats"]["broken"] == 0
    print(f"\n  Verdict Smoke : {VERDICT_GO if ok else VERDICT_NOGO}")
    if not ok:
        print(f"{R}  -> API instable. Ne pas poursuivre vers production.{E}")
    return ok, data


def cmd_critical():
    print(f"\n{W}{'='*55}{E}\n{W}  CRITICAL TESTS{E}\n{W}{'='*55}{E}")
    rc, rdir = run_pytest("critical", "Critical (9 TCs)")
    data = parse_results(rdir)
    print_result("Resultats Critical", data)
    ok = data["stats"]["failed"] == 0 and data["stats"]["broken"] == 0
    print(f"\n  Verdict Critical : {VERDICT_GO if ok else VERDICT_NOGO}")
    return ok, data


def cmd_regression():
    print(f"\n{W}{'='*55}{E}\n{W}  REGRESSION{E}\n{W}{'='*55}{E}")
    baseline = load_baseline()
    if not baseline:
        print(f"{Y}  [WARN] Pas de baseline — run initial.{E}")

    rc, rdir = run_pytest("not flaky", "Regression complete")
    data = parse_results(rdir)
    print_result("Resultats Regression", data)

    regressions = detect_regressions(data, baseline) if baseline else []
    if regressions:
        print(f"\n{R}  REGRESSIONS ({len(regressions)}) :{E}")
        for name in regressions:
            print(f"  {R}!{E} {name[:65]}")
    else:
        print(f"\n{G}  Aucune regression vs baseline.{E}")

    # Mettre à jour la baseline
    passed_tests = []
    for fpath in glob.glob(os.path.join(RESULTS_DIR, "*-result.json")):
        try:
            d = json.load(open(fpath, encoding="utf-8"))
            if d.get("status") == "passed":
                passed_tests.append(d.get("name", ""))
        except Exception:
            pass
    save_baseline({"passed_tests": passed_tests, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")})
    return len(regressions) == 0, data, regressions


def cmd_gono_go():
    print(f"\n{W}{'='*55}{E}\n{W}  GO / NO-GO — Qualification Production{E}\n{W}{'='*55}{E}")
    jira    = JiraClient()
    blockers = []

    smoke_ok, smoke_data = cmd_smoke()
    if not smoke_ok:
        for f in smoke_data["failures"]:
            key = create_jira_bug(jira, f["tc_tag"], f["name"], f["message"], "smoke")
            blockers.append({"type": "smoke", "test": f["name"], "jira": key})

    crit_ok, crit_data = cmd_critical()
    if not crit_ok:
        for f in crit_data["failures"]:
            key = create_jira_bug(jira, f["tc_tag"], f["name"], f["message"], "critical")
            blockers.append({"type": "critical", "test": f["name"], "jira": key})

    print(f"\n{W}{'='*55}{E}\n{W}  VERDICT FINAL — GO / NO-GO PRODUCTION{E}\n{W}{'='*55}{E}")

    if not blockers:
        print(f"\n  {VERDICT_GO}")
        print(f"{G}  Smoke + Critical : OK. Deploiement autorise.{E}\n")
    else:
        print(f"\n  {VERDICT_NOGO}")
        print(f"{R}  {len(blockers)} bloqueur(s) :{E}")
        for b in blockers:
            jira_info = f"-> {b['jira']}" if b["jira"] else ""
            print(f"  {R}x{E} [{b['type'].upper()}] {b['test'][:55]} {jira_info}")

        # Analyse LLM des blockers
        print(f"\n{C}  Analyse LLM...{E}")
        failures_text = "\n".join([f"- [{b['type']}] {b['test']}" for b in blockers])
        analysis = llm.chat([{"role": "user", "content": (
            f"Tu es QA Lead. Ces tests ont echoue avant un deploiement production:\n{failures_text}\n\n"
            f"En 3-4 lignes max, explique le risque metier et recommande l'action immediate."
        )}])
        print(f"\n{Y}  Analyse :{E}")
        for line in analysis.strip().split("\n"):
            print(f"  {line}")
        print()

    return len(blockers) == 0


def cmd_baseline():
    """Enregistre la baseline depuis allure-results courants."""
    print(f"\n{W}  BASELINE — Enregistrement{E}")
    passed_tests = []
    for fpath in glob.glob(os.path.join(RESULTS_DIR, "*-result.json")):
        try:
            d = json.load(open(fpath, encoding="utf-8"))
            if d.get("status") == "passed":
                passed_tests.append(d.get("name", ""))
        except Exception:
            pass
    if not passed_tests:
        print(f"{Y}  [WARN] Aucun test passe dans allure-results.{E}")
        return
    save_baseline({"passed_tests": passed_tests, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "count": len(passed_tests)})
    print(f"{G}  {len(passed_tests)} tests enregistres en baseline.{E}")


# ── Main ───────────────────────────────────────────────────────────────────

def print_help():
    print(f"""
{W}RUNNER AGENT — Exécution des tests API{E}

  python agents/runner-agent.py run          Suite complète (tous les tests)
  python agents/runner-agent.py smoke        5 TCs smoke (@smoke)
  python agents/runner-agent.py critical     9 TCs critiques (@critical)
  python agents/runner-agent.py regression   Suite complète vs baseline (detection regressions)
  python agents/runner-agent.py gono-go      Verdict GO/NO-GO production
  python agents/runner-agent.py baseline     Enregistre la baseline depuis allure-results

{W}Modules absorbés :{E} api-execute-agent · smoke-regression-agent
""")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "run":
        cmd_run()
    elif cmd == "smoke":
        cmd_smoke()
    elif cmd == "critical":
        cmd_critical()
    elif cmd == "regression":
        cmd_regression()
    elif cmd == "gono-go":
        go = cmd_gono_go()
        sys.exit(0 if go else 1)
    elif cmd == "baseline":
        cmd_baseline()
    else:
        print_help()
