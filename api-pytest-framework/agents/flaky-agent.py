# ============================================================
# Flaky Test Agent
# ============================================================
# Detecte les tests instables (flaky), calcule leur score
# d'instabilite et emet un verdict GO/NO-GO si un test
# critique est flaky.
#
# Usage:
#   python agents/flaky-agent.py detect [--runs=3]   → detecte les flaky tests
#   python agents/flaky-agent.py report              → rapport complet
#   python agents/flaky-agent.py quarantine HBAPI-42 → met en quarantaine dans Jira
#   python agents/flaky-agent.py gono-go [--runs=3]  → verdict prod (critical flaky?)
# ============================================================

import sys, os, subprocess, json, glob, time, requests, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

from jira_fetcher_agent import JiraClient, JIRA_BASE_URL
import llm

FRAMEWORK   = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS_DIR = os.path.join(FRAMEWORK, "allure-results")
FLAKY_FILE  = os.path.join(FRAMEWORK, "docs", "flaky-report.json")
DEFAULT_RUNS = 3
FLAKY_THRESHOLD = 0.34  # flaky si echec sur au moins 1/3 des runs

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

VERDICT_GO   = f"{G}{W}  GO  {E}"
VERDICT_NOGO = f"{R}{W} NO-GO {E}"


# ── Helpers ────────────────────────────────────────────────────────────────

def run_single_suite(run_index: int, marker: str = "") -> dict:
    tmp_dir = os.path.join(FRAMEWORK, f"allure-results-run{run_index}")
    os.makedirs(tmp_dir, exist_ok=True)

    ini_path = os.path.join(FRAMEWORK, "pytest.ini")
    cmd = [
        sys.executable, "-m", "pytest",
        f"--rootdir={FRAMEWORK}",
        f"-c", ini_path,
        "--override-ini=addopts=",
        "--alluredir", tmp_dir,
        "--ignore=tests/test_booking_bdd.py",
        "--tb=line", "-q",
        "tests/",
    ]
    if marker:
        cmd += ["-m", marker]

    proc = subprocess.run(cmd, cwd=FRAMEWORK, capture_output=True, text=True, encoding="utf-8", errors="replace")

    results = {}
    for f in glob.glob(os.path.join(tmp_dir, "*-result.json")):
        try:
            with open(f, encoding="utf-8") as fp:
                d = json.load(fp)
            name = d.get("name", "?")
            tc_tag = next(
                (lb["value"] for lb in d.get("labels", [])
                 if lb["name"] == "tag" and re.match(r"tc-\d+", lb["value"])),
                None
            )
            results[name] = {
                "status": d.get("status", "unknown"),
                "tc_tag": tc_tag,
                "message": (d.get("statusDetails") or {}).get("message", "")[:200],
            }
        except Exception:
            pass

    # Nettoyage du dossier temporaire
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return results


def compute_flakiness(runs_data: list) -> dict:
    all_tests = set()
    for run in runs_data:
        all_tests.update(run.keys())

    flaky = {}
    for test in all_tests:
        statuses = [run.get(test, {}).get("status", "unknown") for run in runs_data]
        failures  = sum(1 for s in statuses if s in ("failed", "broken"))
        passes    = sum(1 for s in statuses if s == "passed")
        total     = len(statuses)
        score     = failures / total if total else 0

        if 0 < score < 1.0:  # ni toujours OK ni toujours KO → flaky
            tc_tag = next((run.get(test, {}).get("tc_tag") for run in runs_data if run.get(test, {}).get("tc_tag")), None)
            flaky[test] = {
                "tc_tag":   tc_tag,
                "score":    round(score, 2),
                "failures": failures,
                "passes":   passes,
                "total":    total,
                "statuses": statuses,
            }
    return flaky


def load_flaky_report() -> dict:
    if os.path.exists(FLAKY_FILE):
        with open(FLAKY_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_flaky_report(data: dict):
    os.makedirs(os.path.dirname(FLAKY_FILE), exist_ok=True)
    with open(FLAKY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"{G}  [OK] Rapport flaky sauvegarde → docs/flaky-report.json{E}")


def score_bar(score: float) -> str:
    filled = int(score * 20)
    color  = R if score > 0.5 else Y
    return f"{color}{'#' * filled}{'.' * (20 - filled)}{E} {int(score*100)}%"


def is_critical_tag(tc_tag: str) -> bool:
    critical_tcs = {"tc-001", "tc-006", "tc-013", "tc-020", "tc-032", "tc-038", "tc-045", "tc-051"}
    return tc_tag in critical_tcs if tc_tag else False


# ── Commandes ──────────────────────────────────────────────────────────────

def cmd_detect(runs: int = DEFAULT_RUNS, marker: str = ""):
    print(f"\n{W}{'='*55}{E}")
    print(f"{W}  FLAKY DETECTION — {runs} executions{E}")
    print(f"{W}{'='*55}{E}")
    label = f"marker=@{marker}" if marker else "suite complete"
    print(f"{C}  Lancement de {runs} runs ({label})...{E}\n")

    runs_data = []
    for i in range(1, runs + 1):
        print(f"  {C}Run {i}/{runs}...{E}", end=" ", flush=True)
        result = run_single_suite(i, marker)
        runs_data.append(result)
        passed = sum(1 for v in result.values() if v["status"] == "passed")
        failed = sum(1 for v in result.values() if v["status"] in ("failed", "broken"))
        print(f"{G}{passed} pass{E}  {R}{failed} fail{E}")
        if i < runs:
            time.sleep(2)

    flaky = compute_flakiness(runs_data)

    print(f"\n{W}  Resultats ({len(flaky)} tests flaky detectes):{E}\n")
    if not flaky:
        print(f"{G}  Aucun test flaky detecte sur {runs} runs.{E}")
    else:
        for name, info in sorted(flaky.items(), key=lambda x: -x[1]["score"]):
            crit_marker = f" {R}[CRITICAL]{E}" if is_critical_tag(info["tc_tag"]) else ""
            print(f"  {Y}~{E} [{info['tc_tag'] or '?'}] {name[:55]}{crit_marker}")
            print(f"    Score : [{score_bar(info['score'])}]  ({info['failures']}/{info['total']} echecs)")
            statuses_str = " ".join([
                f"{G}P{E}" if s == "passed" else f"{R}F{E}"
                for s in info["statuses"]
            ])
            print(f"    Runs  : {statuses_str}\n")

    # Sauvegarder
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "runs": runs,
        "flaky_tests": flaky,
    }
    save_flaky_report(report)
    return flaky


def cmd_report():
    print(f"\n{W}{'='*55}{E}")
    print(f"{W}  FLAKY REPORT — Rapport du dernier detect{E}")
    print(f"{W}{'='*55}{E}")

    report = load_flaky_report()
    if not report:
        print(f"{Y}  Aucun rapport. Lance d'abord : flaky-agent.py detect{E}")
        return

    flaky = report.get("flaky_tests", {})
    print(f"\n  Genere le : {report.get('timestamp','?')}  |  Runs : {report.get('runs','?')}")
    print(f"  Tests flaky : {len(flaky)}\n")

    if not flaky:
        print(f"{G}  Suite stable — aucun test flaky.{E}")
        return

    critical_flaky = [n for n, i in flaky.items() if is_critical_tag(i["tc_tag"])]

    for name, info in sorted(flaky.items(), key=lambda x: -x[1]["score"]):
        crit = f" {R}[CRITICAL — bloquant GO/NO-GO]{E}" if is_critical_tag(info["tc_tag"]) else ""
        print(f"  {Y}[FLAKY]{E} [{info['tc_tag'] or '?'}] {name[:55]}{crit}")
        print(f"  Score flakiness : [{score_bar(info['score'])}]")
        print()

    if critical_flaky:
        print(f"{R}  ATTENTION : {len(critical_flaky)} test(s) critique(s) flaky !{E}")
        print(f"{R}  Ces tests peuvent masquer de vraies regressions.{E}")

    # Analyse LLM
    print(f"\n{C}  Analyse LLM des causes potentielles...{E}")
    flaky_list = "\n".join([f"- [{i['tc_tag']}] {n} (score {int(i['score']*100)}%)" for n, i in flaky.items()])
    analysis = llm.chat([{"role": "user", "content": (
        f"Tu es QA Lead. Ces tests API sont instables (flaky) :\n{flaky_list}\n\n"
        f"Donne 3 causes probables d'instabilite pour une API REST et 3 actions correctives concretes. Sois concis."
    )}])
    print(f"\n{Y}  Analyse :{E}")
    for line in analysis.strip().split("\n"):
        print(f"  {line}")
    print()


def cmd_quarantine(jira: JiraClient, issue_key: str):
    print(f"\n{W}[>] Mise en quarantaine : {issue_key}{E}")

    # Ajouter label "flaky" + commentaire
    resp = requests.put(
        f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}",
        json={"update": {"labels": [{"add": "flaky"}, {"add": "quarantine"}]}},
        auth=jira.auth, headers=jira.headers, verify=False
    )
    if resp.status_code == 204:
        print(f"{G}  [OK] Labels flaky + quarantine ajoutes sur {issue_key}{E}")
    else:
        print(f"{Y}  [WARN] Labels : HTTP {resp.status_code}{E}")

    # Commentaire
    comment = {
        "body": {
            "type": "doc", "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text":
                f"[FLAKY-AGENT] Ce test a ete mis en quarantaine automatiquement.\n"
                f"Il presente un comportement instable et ne doit pas bloquer le pipeline CI.\n"
                f"Action requise : analyser la cause racine avant de le re-activer."
            }]}]
        }
    }
    resp2 = requests.post(
        f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/comment",
        json=comment, auth=jira.auth, headers=jira.headers, verify=False
    )
    if resp2.status_code == 201:
        print(f"{G}  [OK] Commentaire quarantaine ajoute sur {issue_key}{E}")
    else:
        print(f"{Y}  [WARN] Commentaire : HTTP {resp2.status_code}{E}")


def cmd_gono_go(runs: int = DEFAULT_RUNS):
    print(f"\n{W}{'='*55}{E}")
    print(f"{W}  FLAKY GO / NO-GO — Tests critiques stables ?{E}")
    print(f"{W}{'='*55}{E}")
    print(f"{C}  Analyse flakiness sur les tests @critical ({runs} runs)...{E}")

    jira = JiraClient()
    flaky = cmd_detect(runs=runs, marker="critical")

    critical_flaky = {n: i for n, i in flaky.items() if is_critical_tag(i["tc_tag"]) and i["score"] >= FLAKY_THRESHOLD}

    print(f"\n{W}{'='*55}{E}")
    print(f"{W}  VERDICT FLAKY — GO / NO-GO PRODUCTION{E}")
    print(f"{W}{'='*55}{E}")

    if not critical_flaky:
        print(f"\n  {VERDICT_GO}")
        print(f"{G}  Aucun test critique flaky au-dessus du seuil ({int(FLAKY_THRESHOLD*100)}%).{E}")
        print(f"{G}  Les resultats CI sont fiables pour la production.{E}\n")
    else:
        print(f"\n  {VERDICT_NOGO}")
        print(f"{R}  {len(critical_flaky)} test(s) critique(s) instable(s) :{E}")
        for name, info in critical_flaky.items():
            print(f"  {R}~{E} [{info['tc_tag']}] {name[:55]}  score={int(info['score']*100)}%")
            # Mise en quarantaine automatique
            if info["tc_tag"]:
                tc_num = int(re.search(r"\d+", info["tc_tag"]).group())
                jira_key = f"HBAPI-{10 + tc_num}"
                cmd_quarantine(jira, jira_key)
        print(f"\n{R}  Tests critiques flaky = resultats CI non fiables.{E}")
        print(f"{R}  Deploiement BLOQUE jusqu'a stabilisation.{E}\n")

    return len(critical_flaky) == 0


# ── Main ──────────────────────────────────────────────────────────────────

def print_help():
    print(f"""
{W}FLAKY TEST AGENT{E}

  python agents/flaky-agent.py detect [--runs=N]   Detecte les flaky (defaut: 3 runs)
  python agents/flaky-agent.py report              Rapport du dernier detect
  python agents/flaky-agent.py quarantine HBAPI-42 Met en quarantaine dans Jira
  python agents/flaky-agent.py gono-go [--runs=N]  Verdict GO/NO-GO (tests critiques)

  Seuil flakiness : {int(FLAKY_THRESHOLD*100)}% (1 echec sur {int(1/FLAKY_THRESHOLD)} runs = flaky)
""")


if __name__ == "__main__":
    cmd  = sys.argv[1] if len(sys.argv) > 1 else "help"
    runs = int(next((a.split("=")[1] for a in sys.argv if a.startswith("--runs=")), DEFAULT_RUNS))

    if cmd == "detect":
        cmd_detect(runs=runs)
    elif cmd == "report":
        cmd_report()
    elif cmd == "quarantine":
        if len(sys.argv) < 3:
            print(f"{R}Usage: flaky-agent.py quarantine HBAPI-42{E}")
            sys.exit(1)
        cmd_quarantine(JiraClient(), sys.argv[2])
    elif cmd == "gono-go":
        go = cmd_gono_go(runs=runs)
        sys.exit(0 if go else 1)
    else:
        print_help()
