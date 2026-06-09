# ============================================================
# Smoke / Regression / Go-No-Go Agent
# ============================================================
# Lance les tests smoke ou critiques, detecte les regressions
# et emet un verdict GO / NO-GO pour la mise en production.
#
# Usage:
#   python agents/smoke-regression-agent.py smoke      → 5 TCs smoke
#   python agents/smoke-regression-agent.py critical   → 9 TCs critiques
#   python agents/smoke-regression-agent.py regression → suite complete
#   python agents/smoke-regression-agent.py gono-go    → verdict prod
# ============================================================

import sys, os, subprocess, json, glob, time, requests
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

from jira_fetcher_agent import JiraClient, JIRA_BASE_URL
import llm

FRAMEWORK = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS_DIR = os.path.join(FRAMEWORK, "allure-results")
BASELINE_FILE = os.path.join(FRAMEWORK, "docs", "baseline.json")

# Couleurs
R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; B = "\033[34m"
C = "\033[36m"; W = "\033[1m";  E = "\033[0m"

VERDICT_GO    = f"{G}{W}  GO  {E}"
VERDICT_NOGO  = f"{R}{W} NO-GO {E}"

# ── Helpers ────────────────────────────────────────────────────────────────

def run_pytest(marker: str, label: str) -> tuple:
    """Retourne (returncode, result_dir) avec un répertoire isolé."""
    import tempfile
    print(f"\n{C}[>] Execution : {label} ({marker}){E}")
    result_dir = tempfile.mkdtemp(prefix="smoke_results_")
    ini_path   = os.path.join(FRAMEWORK, "pytest.ini")

    cmd = [
        sys.executable, "-m", "pytest",
        f"--rootdir={FRAMEWORK}",
        f"-c", ini_path,
        "--override-ini=addopts=",
        "-m", marker,
        "--alluredir", result_dir,
        "--ignore=tests/test_booking_bdd.py",
        "--tb=short", "-q",
        "tests/",
    ]
    proc = subprocess.run(cmd, cwd=FRAMEWORK, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return proc.returncode, result_dir


def parse_allure_results(results_dir: str) -> dict:
    stats = {"passed": 0, "failed": 0, "broken": 0, "skipped": 0, "total": 0}
    failures = []
    for f in glob.glob(os.path.join(results_dir, "*-result.json")):
        try:
            with open(f, encoding="utf-8") as fp:
                d = json.load(fp)
            s = d.get("status", "unknown")
            if s in stats:
                stats[s] += 1
            stats["total"] += 1
            if s in ("failed", "broken"):
                labels = {lb["name"]: lb["value"] for lb in d.get("labels", [])}
                tc_tag = next((lb["value"] for lb in d.get("labels", []) if lb["name"] == "tag" and lb["value"].startswith("tc-")), None)
                failures.append({
                    "name": d.get("name", "?"),
                    "tc_tag": tc_tag,
                    "message": (d.get("statusDetails") or {}).get("message", "")[:200],
                    "status": s,
                })
        except Exception:
            pass
    return {"stats": stats, "failures": failures}


def load_baseline() -> dict:
    if os.path.exists(BASELINE_FILE):
        with open(BASELINE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_baseline(data: dict):
    os.makedirs(os.path.dirname(BASELINE_FILE), exist_ok=True)
    with open(BASELINE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"{G}  [OK] Baseline sauvegardee → docs/baseline.json{E}")


def detect_regressions(current: dict, baseline: dict) -> list:
    regressions = []
    current_by_name = {f["name"]: f for f in current.get("failures", [])}
    baseline_passed = baseline.get("passed_tests", [])
    for name in baseline_passed:
        if name in current_by_name:
            regressions.append({"name": name, "status": current_by_name[name]["status"]})
    return regressions


def create_jira_bug(jira: JiraClient, tc_tag: str, test_name: str, message: str, verdict_type: str):
    summary = f"[{verdict_type.upper()}] Regression detectee : {test_name[:60]}"
    description = {
        "type": "doc", "version": 1,
        "content": [{
            "type": "paragraph",
            "content": [{"type": "text", "text": (
                f"Test : {test_name}\n"
                f"Tag  : {tc_tag or 'N/A'}\n"
                f"Type : {verdict_type}\n\n"
                f"Erreur :\n{message}\n\n"
                f"-> BLOQUE GO/NO-GO PRODUCTION"
            )}]
        }]
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
        print(f"{R}  [BUG] Jira cree : {key} — {summary}{E}")
        return key
    else:
        print(f"{Y}  [WARN] Jira bug non cree : {resp.status_code}{E}")
        return None


def print_result(label: str, data: dict):
    s = data["stats"]
    pct = round(s["passed"] / s["total"] * 100) if s["total"] else 0
    bar_ok  = "#" * (pct // 5)
    bar_ko  = "." * (20 - pct // 5)
    color   = G if s["failed"] == 0 and s["broken"] == 0 else R
    print(f"\n{W}  {label}{E}")
    print(f"  [{color}{bar_ok}{E}{bar_ko}] {pct}%  |  Total:{s['total']}  PASS:{G}{s['passed']}{E}  FAIL:{R}{s['failed']}{E}  BROKEN:{Y}{s['broken']}{E}")
    if data["failures"]:
        print(f"\n{R}  Tests en echec :{E}")
        for f in data["failures"]:
            print(f"  {R}x{E} [{f['tc_tag'] or '?'}] {f['name'][:65]}")
            if f["message"]:
                print(f"    {Y}→ {f['message'][:100]}{E}")


# ── Commandes ──────────────────────────────────────────────────────────────

def cmd_smoke():
    print(f"\n{W}{'='*55}{E}")
    print(f"{W}  SMOKE TESTS — Verification rapide API{E}")
    print(f"{W}{'='*55}{E}")
    rc, rdir = run_pytest("smoke", "Smoke (5 TCs)")
    data = parse_allure_results(rdir)
    print_result("Resultats Smoke", data)

    ok = data["stats"]["failed"] == 0 and data["stats"]["broken"] == 0
    print(f"\n  Verdict Smoke : {VERDICT_GO if ok else VERDICT_NOGO}")
    if not ok:
        print(f"{R}  -> API instable. Ne pas poursuivre vers production.{E}")
    return ok, data


def cmd_critical():
    print(f"\n{W}{'='*55}{E}")
    print(f"{W}  CRITICAL TESTS — Flux metier essentiels{E}")
    print(f"{W}{'='*55}{E}")
    rc, rdir = run_pytest("critical", "Critical (9 TCs)")
    data = parse_allure_results(rdir)
    print_result("Resultats Critical", data)

    ok = data["stats"]["failed"] == 0 and data["stats"]["broken"] == 0
    print(f"\n  Verdict Critical : {VERDICT_GO if ok else VERDICT_NOGO}")
    if not ok:
        print(f"{R}  -> Flux metier en echec. Bloquant pour la production.{E}")
    return ok, data


def cmd_regression():
    print(f"\n{W}{'='*55}{E}")
    print(f"{W}  REGRESSION — Suite complete vs baseline{E}")
    print(f"{W}{'='*55}{E}")

    baseline = load_baseline()
    if not baseline:
        print(f"{Y}  [WARN] Pas de baseline. Lancement en mode initial...{E}")

    rc, rdir = run_pytest("not flaky", "Regression complete")
    data = parse_allure_results(rdir)
    print_result("Resultats Regression", data)

    # Detecter les regressions vs baseline
    regressions = detect_regressions(data, baseline) if baseline else []
    if regressions:
        print(f"\n{R}  REGRESSIONS DETECTEES ({len(regressions)}) :{E}")
        for reg in regressions:
            print(f"  {R}!{E} {reg['name'][:65]} → {reg['status']}")
    else:
        print(f"\n{G}  Aucune regression vs baseline.{E}")

    # Sauvegarder la nouvelle baseline
    passed_tests = [
        f["name"] for f in []  # on ne garde que les passes
    ]
    for fpath in glob.glob(os.path.join(RESULTS_DIR, "*-result.json")):
        try:
            with open(fpath, encoding="utf-8") as fp:
                d = json.load(fp)
            if d.get("status") == "passed":
                passed_tests.append(d.get("name", ""))
        except Exception:
            pass
    save_baseline({"passed_tests": passed_tests, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")})

    return len(regressions) == 0, data, regressions


def cmd_gono_go():
    print(f"\n{W}{'='*55}{E}")
    print(f"{W}  GO / NO-GO — Qualification Production{E}")
    print(f"{W}{'='*55}{E}")
    print(f"{C}  Execution des smoke + critical tests...{E}\n")

    jira = JiraClient()
    blockers = []

    # 1. Smoke
    smoke_ok, smoke_data = cmd_smoke()
    if not smoke_ok:
        for f in smoke_data["failures"]:
            key = create_jira_bug(jira, f["tc_tag"], f["name"], f["message"], "smoke")
            blockers.append({"type": "smoke", "test": f["name"], "jira": key})

    # 2. Critical
    crit_ok, crit_data = cmd_critical()
    if not crit_ok:
        for f in crit_data["failures"]:
            key = create_jira_bug(jira, f["tc_tag"], f["name"], f["message"], "critical")
            blockers.append({"type": "critical", "test": f["name"], "jira": key})

    # 3. Verdict final
    print(f"\n{W}{'='*55}{E}")
    print(f"{W}  VERDICT FINAL — GO / NO-GO PRODUCTION{E}")
    print(f"{W}{'='*55}{E}")

    if not blockers:
        print(f"\n  {VERDICT_GO}")
        print(f"{G}  Tous les smoke et critical tests sont verts.{E}")
        print(f"{G}  Deploiement en production autorise.{E}\n")
    else:
        print(f"\n  {VERDICT_NOGO}")
        print(f"{R}  {len(blockers)} bloqueur(s) detecte(s) :{E}")
        for b in blockers:
            jira_info = f"→ {b['jira']}" if b['jira'] else ""
            print(f"  {R}x{E} [{b['type'].upper()}] {b['test'][:55]} {jira_info}")
        print(f"\n{R}  Deploiement BLOQUE. Corriger les bugs avant production.{E}")

        # Analyse LLM
        print(f"\n{C}  Analyse des blockers via LLM...{E}")
        failures_text = "\n".join([
            f"- [{b['type']}] {b['test']}" for b in blockers
        ])
        analysis = llm.chat([{"role": "user", "content": (
            f"Tu es QA Lead. Ces tests ont echoue avant un deploiement production:\n{failures_text}\n\n"
            f"En 3-4 lignes maximum, explique le risque metier et recommande l'action immediate."
        )}])
        print(f"\n{Y}  Analyse :{E}")
        for line in analysis.strip().split("\n"):
            print(f"  {line}")
        print()

    return len(blockers) == 0


# ── Main ──────────────────────────────────────────────────────────────────

def print_help():
    print(f"""
{W}SMOKE / REGRESSION / GO-NO-GO AGENT{E}

  python agents/smoke-regression-agent.py smoke      5 TCs smoke (@smoke)
  python agents/smoke-regression-agent.py critical   9 TCs critiques (@critical)
  python agents/smoke-regression-agent.py regression Suite complete + detection regressions
  python agents/smoke-regression-agent.py gono-go    Verdict GO/NO-GO production
""")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "smoke":
        cmd_smoke()
    elif cmd == "critical":
        cmd_critical()
    elif cmd == "regression":
        cmd_regression()
    elif cmd == "gono-go":
        go = cmd_gono_go()
        sys.exit(0 if go else 1)
    else:
        print_help()
