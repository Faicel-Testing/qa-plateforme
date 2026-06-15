# ============================================================
# Quality Agent — Analyse · KPI · Flaky · Vérification
# ============================================================
# Absorbe : qa-agent · kpi-agent · flaky-agent · verifier-agent
#
# Commandes :
#   python agents/quality-agent.py analyze        → analyse qualité de la suite BDD
#   python agents/quality-agent.py kpi            → tableau de bord KPI (HTML + env props)
#   python agents/quality-agent.py flaky [--runs=3]  → détection des tests instables
#   python agents/quality-agent.py verify gherkin → vérifie les features .feature
#   python agents/quality-agent.py gate           → quality gate Go/No-Go
# ============================================================

import sys, os, json, glob, re, subprocess, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm
from jira_fetcher_agent import JiraClient, JIRA_BASE_URL

FRAMEWORK   = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS_DIR = os.path.join(FRAMEWORK, "allure-results")
FEATURES_DIR = os.path.join(FRAMEWORK, "features")
DOCS_DIR    = os.path.join(FRAMEWORK, "docs")
FLAKY_FILE  = os.path.join(DOCS_DIR, "flaky-report.json")
BASELINE    = os.path.join(DOCS_DIR, "baseline.json")
TREND_FILE  = os.path.join(FRAMEWORK, "allure-report", "history", "history-trend.json")
ENV_FILE    = os.path.join(RESULTS_DIR, "environment.properties")
KPI_FILE    = os.path.join(DOCS_DIR, "kpi-dashboard.html")
INI_PATH    = os.path.join(FRAMEWORK, "pytest.ini")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

FLAKY_THRESHOLD    = 0.34   # flaky si échec ≥ 1/3 des runs
DEFAULT_RUNS       = 3
PASS_RATE_TARGET   = 90.0
FAIL_RATE_MAX      = 5.0
CONFIDENCE_TARGET  = 0.70


# ── Helpers partagés ────────────────────────────────────────────────────────

def collect_results(results_dir: str = None) -> dict:
    dir_ = results_dir or RESULTS_DIR
    stats    = {"passed": 0, "failed": 0, "broken": 0, "skipped": 0, "total": 0}
    failures = []
    suites   = {}
    durations = []
    tc_tags   = set()

    for f in glob.glob(os.path.join(dir_, "*-result.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
            s = d.get("status", "unknown")
            if s in stats:
                stats[s] += 1
            stats["total"] += 1

            start = d.get("start", 0); stop = d.get("stop", 0)
            if start and stop:
                durations.append(stop - start)

            labels = d.get("labels", [])
            suite  = next((lb["value"] for lb in labels if lb["name"] == "tag" and lb["value"].startswith("us-")), "other")
            suites.setdefault(suite, {"passed": 0, "failed": 0, "broken": 0, "total": 0})
            suites[suite]["total"] += 1
            if s in suites[suite]:
                suites[suite][s] += 1

            tc = next((lb["value"] for lb in labels if lb["name"] == "tag" and re.match(r"tc-\d+", lb["value"])), None)
            if tc:
                tc_tags.add(tc)

            if s in ("failed", "broken"):
                msg = (d.get("statusDetails") or {}).get("message", "")[:120]
                failures.append({"name": d.get("name", "?"), "status": s, "message": msg, "tc": tc})
        except Exception:
            pass

    total = stats["total"] or 1
    return {
        "stats": stats,
        "failures": failures,
        "suites": suites,
        "tc_count": len(tc_tags),
        "pass_rate": round(stats["passed"] / total * 100, 1),
        "fail_rate": round((stats["failed"] + stats["broken"]) / total * 100, 1),
        "avg_duration_ms": round(sum(durations) / len(durations)) if durations else 0,
    }


def run_pytest_suite(run_index: int, marker: str = "") -> dict:
    tmp_dir = os.path.join(FRAMEWORK, f"allure-tmp-run{run_index}")
    os.makedirs(tmp_dir, exist_ok=True)
    cmd = [
        sys.executable, "-m", "pytest",
        f"--rootdir={FRAMEWORK}", "-c", INI_PATH,
        "--override-ini=addopts=",
        "--alluredir", tmp_dir,
        "--ignore=tests/test_booking_bdd.py",
        "--tb=line", "-q", "tests/",
    ]
    if marker:
        cmd += ["-m", marker]
    subprocess.run(cmd, cwd=FRAMEWORK, capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
    results = {}
    for f in glob.glob(os.path.join(tmp_dir, "*-result.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
            name = d.get("name", "?")
            results[name] = d.get("status", "unknown")
        except Exception:
            pass
    return results


# ── Analyze — Qualité de la suite ─────────────────────────────────────────

def cmd_analyze():
    print(f"\n{W}QUALITY AGENT — Suite Analysis{E}\n")
    data = collect_results()
    s = data["stats"]

    # Affichage
    tot  = s["total"] or 1
    pct  = data["pass_rate"]
    color = G if pct >= PASS_RATE_TARGET else Y if pct >= 70 else R
    print(f"  Total    : {s['total']}")
    print(f"  Pass     : {G}{s['passed']}{E}  ({color}{pct}%{E})")
    print(f"  Fail     : {R}{s['failed']}{E}")
    print(f"  Broken   : {Y}{s['broken']}{E}")
    print(f"  Skipped  : {s['skipped']}")
    print(f"  Duree    : {data['avg_duration_ms']}ms/test")

    # Analyse LLM via CoT
    print(f"\n{C}  Analyse CoT de la qualite...{E}")
    failures_text = "\n".join([f"- [{f['tc'] or '?'}] {f['name']}: {f['message'][:60]}"
                                for f in data["failures"][:10]])
    messages = [{"role": "user", "content": (
        f"Analyse la qualite de cette suite de tests API BDD :\n\n"
        f"Total : {s['total']} | Pass : {s['passed']} ({pct}%) | "
        f"Fail : {s['failed']} | Broken : {s['broken']}\n\n"
        f"Echecs :\n{failures_text or 'Aucun'}\n\n"
        f"En 5 points, evalue :\n"
        f"1. La stabilite de la suite\n"
        f"2. Les patterns d'echec\n"
        f"3. La couverture (TC count: {data['tc_count']})\n"
        f"4. Les risques identifies\n"
        f"5. Les 2 actions prioritaires"
    )}]
    analysis = llm.chat_cot(messages)
    print(f"\n{W}  Analyse :{E}")
    for line in analysis.strip().split("\n"):
        if re.match(r"\s*ÉTAPE\s*\d", line, re.IGNORECASE):
            print(f"  {Y}{line}{E}")
        elif re.match(r"\s*CONCLUSION", line, re.IGNORECASE):
            print(f"  {G}{line}{E}")
        elif line.strip():
            print(f"  {line}")
    return data


# ── KPI — Tableau de bord ─────────────────────────────────────────────────

def cmd_kpi(mode: str = "all"):
    print(f"\n{W}QUALITY AGENT — KPI Dashboard{E}\n")
    data  = collect_results()
    s     = data["stats"]
    tot   = s["total"] or 1
    pct   = data["pass_rate"]

    # Trend depuis historique Allure
    trend = []
    if os.path.exists(TREND_FILE):
        try:
            trend = json.load(open(TREND_FILE, encoding="utf-8"))
        except Exception:
            pass

    # Flaky data
    flaky_data = {}
    if os.path.exists(FLAKY_FILE):
        try:
            flaky_data = json.load(open(FLAKY_FILE, encoding="utf-8")).get("flaky_tests", {})
        except Exception:
            pass

    if mode in ("all", "env"):
        # environment.properties pour Allure
        os.makedirs(RESULTS_DIR, exist_ok=True)
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.write(f"Total_Tests={s['total']}\n")
            f.write(f"Pass_Rate={pct}%\n")
            f.write(f"Failed={s['failed']}\n")
            f.write(f"Broken={s['broken']}\n")
            f.write(f"Flaky_Count={len(flaky_data)}\n")
            f.write(f"TC_Count={data['tc_count']}\n")
        print(f"  {G}environment.properties -> allure-results/{E}")

    if mode in ("all", "dashboard"):
        # Dashboard HTML
        trend_rows = ""
        for t in trend[-10:]:
            dt = t.get("buildOrder", 0)
            tp = t.get("data", {}).get("passed", 0)
            tf = t.get("data", {}).get("failed", 0) + t.get("data", {}).get("broken", 0)
            color = G if tf == 0 else R
            trend_rows += f"<tr><td>#{dt}</td><td style='color:{('green' if tf==0 else 'red')}'>{tp}</td><td>{tf}</td></tr>"

        failures_html = "".join(
            f"<li style='color:#e74c3c'>[{f['tc'] or '?'}] {f['name'][:60]}</li>"
            for f in data["failures"][:10]
        )
        pass_color = "#27ae60" if pct >= PASS_RATE_TARGET else "#e67e22" if pct >= 70 else "#e74c3c"

        html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>KPI Dashboard — API Tests</title>
<style>
  body{{font-family:Arial,sans-serif;background:#f5f5f5;color:#333;margin:0;padding:20px}}
  h1{{color:#2c3e50}} h2{{color:#34495e;margin-top:25px}}
  .stat{{display:inline-block;background:#fff;border-radius:8px;padding:18px 28px;margin:8px;
         box-shadow:0 2px 6px rgba(0,0,0,.1);text-align:center;min-width:100px}}
  .stat-val{{font-size:32px;font-weight:bold}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;
         box-shadow:0 2px 8px rgba(0,0,0,.1);margin-top:10px}}
  th{{background:#2c3e50;color:#fff;padding:9px 12px;text-align:left}}
  td{{padding:8px 12px;border-bottom:1px solid #ecf0f1}}
  .gate{{padding:12px 24px;border-radius:8px;font-size:18px;font-weight:bold;display:inline-block;margin:8px 0}}
</style>
</head>
<body>
<h1>KPI Dashboard — API Test Suite</h1>
<div class="gate" style="background:{'#27ae60' if pct >= PASS_RATE_TARGET else '#e74c3c'};color:#fff">
  {'GO — Quality Gate PASSED' if pct >= PASS_RATE_TARGET else 'NO-GO — Quality Gate FAILED'}
</div>
<div>
  <div class="stat"><div class="stat-val" style="color:#2c3e50">{s['total']}</div>Tests</div>
  <div class="stat"><div class="stat-val" style="color:{pass_color}">{pct}%</div>Pass Rate</div>
  <div class="stat"><div class="stat-val" style="color:#27ae60">{s['passed']}</div>Passed</div>
  <div class="stat"><div class="stat-val" style="color:#e74c3c">{s['failed']}</div>Failed</div>
  <div class="stat"><div class="stat-val" style="color:#e67e22">{s['broken']}</div>Broken</div>
  <div class="stat"><div class="stat-val" style="color:#3498db">{data['tc_count']}</div>TCs</div>
  <div class="stat"><div class="stat-val" style="color:#9b59b6">{len(flaky_data)}</div>Flaky</div>
  <div class="stat"><div class="stat-val" style="color:#95a5a6">{data['avg_duration_ms']}ms</div>Moy/test</div>
</div>
{f'<h2>Echecs ({len(data["failures"])})</h2><ul>{failures_html}</ul>' if data["failures"] else ''}
{f'<h2>Tendance (derniers runs)</h2><table><tr><th>Run</th><th>Pass</th><th>Fail</th></tr>{trend_rows}</table>' if trend_rows else ''}
<p style="color:#999;font-size:12px;margin-top:30px">
  Cible : Pass ≥ {PASS_RATE_TARGET}% | Fail ≤ {FAIL_RATE_MAX}% — Généré par Quality Agent
</p>
</body>
</html>"""
        os.makedirs(DOCS_DIR, exist_ok=True)
        with open(KPI_FILE, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  {G}KPI Dashboard -> docs/kpi-dashboard.html{E}")

    if mode == "summary":
        gate = pct >= PASS_RATE_TARGET and data["fail_rate"] <= FAIL_RATE_MAX
        print(f"\n  Pass Rate  : {G if pct >= PASS_RATE_TARGET else R}{pct}%{E} (cible {PASS_RATE_TARGET}%)")
        print(f"  Fail Rate  : {G if data['fail_rate'] <= FAIL_RATE_MAX else R}{data['fail_rate']}%{E} (max {FAIL_RATE_MAX}%)")
        print(f"  Quality Gate : {'✓ PASSED' if gate else '✗ FAILED'}")

    return data


# ── Flaky — Détection des tests instables ─────────────────────────────────

def cmd_flaky(runs: int = DEFAULT_RUNS):
    print(f"\n{W}QUALITY AGENT — Flaky Detection ({runs} runs){E}\n")
    all_runs = []
    for i in range(1, runs + 1):
        print(f"  {C}Run {i}/{runs}{E}...", end=" ", flush=True)
        results = run_pytest_suite(i)
        all_runs.append(results)
        total = len(results)
        passed = sum(1 for s in results.values() if s == "passed")
        print(f"{G if passed == total else Y}{passed}/{total}{E}")

    # Analyser les instabilités
    all_tests = set()
    for r in all_runs:
        all_tests.update(r.keys())

    flaky = {}
    for test in all_tests:
        statuses = [r.get(test, "missing") for r in all_runs]
        fail_count = sum(1 for s in statuses if s in ("failed", "broken", "missing"))
        pass_count = sum(1 for s in statuses if s == "passed")
        if 0 < fail_count < runs and pass_count > 0:  # Passe ET échoue = flaky
            fail_rate = fail_count / runs
            tags       = []  # Tags récupérés depuis allure si disponible
            flaky[test] = {
                "fail_rate":  round(fail_rate, 2),
                "fail_count": fail_count,
                "pass_count": pass_count,
                "runs":       runs,
                "statuses":   statuses,
                "is_critical": fail_rate >= FLAKY_THRESHOLD,
            }

    # Rapport console
    if not flaky:
        print(f"\n{G}  Aucun test flaky detecte sur {runs} runs.{E}")
    else:
        critical_flaky = [t for t, d in flaky.items() if d["is_critical"]]
        print(f"\n  {R}{len(flaky)} test(s) flaky{E} | {R}{len(critical_flaky)} critique(s){E}")
        for name, d in sorted(flaky.items(), key=lambda x: -x[1]["fail_rate"]):
            color = R if d["is_critical"] else Y
            print(f"  {color}[{int(d['fail_rate']*100)}%]{E} {name[:65]}")

    # Analyse LLM + sauvegarde
    if flaky:
        flaky_text = "\n".join([f"- {name} ({int(d['fail_rate']*100)}% fail)" for name, d in list(flaky.items())[:10]])
        messages = [{"role": "user", "content": (
            f"Ces tests API sont flaky (passent parfois, echouent parfois) :\n{flaky_text}\n\n"
            f"En 3 points, explique les causes probables et propose des actions de stabilisation."
        )}]
        analysis = llm.chat(messages)
        print(f"\n{W}  Analyse :{E}")
        for line in analysis.strip().split("\n"):
            print(f"  {line}")

    # Sauvegarde
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(FLAKY_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "flaky_tests": flaky,
            "runs": runs,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }, f, indent=2, ensure_ascii=False)
    print(f"\n{G}  Rapport : docs/flaky-report.json{E}")
    return flaky


# ── Verify — Vérification adversariale ─────────────────────────────────────

def cmd_verify(target: str = "gherkin"):
    print(f"\n{W}QUALITY AGENT — Verify [{target}]{E}\n")

    if target == "gherkin":
        features = glob.glob(os.path.join(FEATURES_DIR, "*.feature"))
        if not features:
            print(f"{Y}  Aucun fichier .feature.{E}")
            return

        issues = []
        for fpath in features:
            content = open(fpath, encoding="utf-8").read()
            fname   = os.path.basename(fpath)
            scenarios = re.findall(r"Scenario(?:\s+Outline)?:\s*(.+)", content)
            tags      = re.findall(r"@(\w[\w-]*)", content)

            # Vérifications déterministes
            if not re.search(r"Feature:", content):
                issues.append(f"{fname}: manque un titre Feature")
            for sc in scenarios:
                if len(sc.strip()) < 5:
                    issues.append(f"{fname}: scenario trop court — '{sc}'")
            if not any(t in tags for t in ["smoke", "critical", "regression"]):
                issues.append(f"{fname}: aucun tag de priorite (@smoke/@critical/@regression)")

        # Vérification adversariale LLM
        sample = open(features[0], encoding="utf-8").read()[:2000]
        messages = [{"role": "user", "content": (
            f"Voici un fichier .feature BDD. Cherche TOUS les problemes :\n\n{sample}\n\n"
            f"Problemes courants a chercher :\n"
            f"- Steps vagues ou non testables\n"
            f"- Pas de Given/When/Then structure\n"
            f"- Data de test hardcoded sans exemple\n"
            f"- Scenarios trop longs (> 10 steps)\n"
            f"- Scenarios sans assertion claire\n"
            f"Soit strict."
        )}]
        adv_result = llm.chat_adversarial(sample, sample, domain="QA BDD")

        verdict = adv_result.get("verdict", "UNKNOWN")
        color   = G if verdict == "VALID" else R if verdict == "INVALID" else Y
        print(f"  Verdict adversarial : {color}{W}{verdict}{E} "
              f"(confidence: {int(adv_result.get('confidence',0)*100)}%)")
        print(f"  {adv_result.get('summary','')[:120]}")

        if adv_result.get("issues"):
            print(f"\n{R}  Problemes detectes :{E}")
            for issue in adv_result["issues"]:
                print(f"  {R}x{E} {issue}")

        if issues:
            print(f"\n{Y}  Verifications deterministes ({len(issues)}) :{E}")
            for issue in issues:
                print(f"  {Y}!{E} {issue}")
        else:
            print(f"\n{G}  Verifications deterministes : OK{E}")

    elif target == "results":
        # Vérifier que les résultats Allure sont cohérents
        data = collect_results()
        print(f"  {data['stats']['total']} resultats | Pass: {data['pass_rate']}%")
        if data["stats"]["total"] == 0:
            print(f"{R}  [ERR] Aucun resultat Allure — suite non executee ?{E}")
        elif data["fail_rate"] > 50:
            print(f"{R}  [ERR] Taux d'echec anormalement eleve : {data['fail_rate']}%{E}")
        else:
            print(f"{G}  Resultats coherents.{E}")


# ── Gate — Quality Gate Go/No-Go ──────────────────────────────────────────

def cmd_gate():
    print(f"\n{W}QUALITY AGENT — Quality Gate{E}")
    print(f"{Y}  Criteres : Pass ≥ {PASS_RATE_TARGET}% | Fail ≤ {FAIL_RATE_MAX}%{E}\n")

    data = collect_results()
    s    = data["stats"]
    pass_ok = data["pass_rate"] >= PASS_RATE_TARGET
    fail_ok = data["fail_rate"] <= FAIL_RATE_MAX

    print(f"  Pass Rate : {G if pass_ok else R}{data['pass_rate']}%{E}  (cible ≥ {PASS_RATE_TARGET}%)  {'✓' if pass_ok else '✗'}")
    print(f"  Fail Rate : {G if fail_ok else R}{data['fail_rate']}%{E}  (max ≤ {FAIL_RATE_MAX}%)      {'✓' if fail_ok else '✗'}")

    gate_passed = pass_ok and fail_ok

    if gate_passed:
        print(f"\n  {G}{W}  QUALITY GATE PASSED  {E}")
        print(f"{G}  Deploiement autorise selon les criteres qualite.{E}")
    else:
        print(f"\n  {R}{W}  QUALITY GATE FAILED  {E}")
        if not pass_ok:
            print(f"{R}  -> Pass Rate insuffisant ({data['pass_rate']}% < {PASS_RATE_TARGET}%){E}")
        if not fail_ok:
            print(f"{R}  -> Trop d'echecs ({data['fail_rate']}% > {FAIL_RATE_MAX}%){E}")
        print(f"\n{Y}  {len(s['failed'] if isinstance(s['failed'], list) else [None] * s['failed'])} test(s) en echec bloquant le gate.{E}")

    return gate_passed


# ── Main ───────────────────────────────────────────────────────────────────

def print_help():
    print(f"""
{W}QUALITY AGENT — Analyse · KPI · Flaky · Vérification{E}

  python agents/quality-agent.py analyze          Analyse de la qualite de la suite (CoT)
  python agents/quality-agent.py kpi              Dashboard KPI complet (HTML + env.properties)
  python agents/quality-agent.py kpi summary      Resume console uniquement
  python agents/quality-agent.py flaky            Detection des tests instables (3 runs)
  python agents/quality-agent.py flaky --runs=5   Detection sur 5 runs
  python agents/quality-agent.py verify gherkin   Verification adversariale des .feature
  python agents/quality-agent.py verify results   Verification des resultats Allure
  python agents/quality-agent.py gate             Quality Gate Go/No-Go

{W}Seuils quality gate :{E}
  Pass Rate ≥ {PASS_RATE_TARGET}% · Fail Rate ≤ {FAIL_RATE_MAX}%

{W}Modules absorbes :{E} qa-agent · kpi-agent · flaky-agent · verifier-agent
""")


if __name__ == "__main__":
    runs_arg = int(next((a.split("=")[1] for a in sys.argv if a.startswith("--runs=")), str(DEFAULT_RUNS)))
    cmd  = sys.argv[1] if len(sys.argv) > 1 else "help"
    sub  = sys.argv[2] if len(sys.argv) > 2 else None

    if cmd == "analyze":
        cmd_analyze()
    elif cmd == "kpi":
        mode = sub if sub in ("all", "dashboard", "env", "summary") else "all"
        cmd_kpi(mode)
    elif cmd == "flaky":
        cmd_flaky(runs=runs_arg)
    elif cmd == "verify":
        cmd_verify(sub or "gherkin")
    elif cmd == "gate":
        passed = cmd_gate()
        sys.exit(0 if passed else 1)
    else:
        print_help()
