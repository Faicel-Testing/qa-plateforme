# ============================================================
# Verifier Agent — Contrôle qualité des autres agents
# ============================================================
# Vérifie le travail des agents IA pour éviter les hallucinations.
# Chaque vérification = checks déterministes + LLM adversarial.
#
# Usage:
#   python agents/verifier-agent.py gherkin   → vérifie features/*.feature
#   python agents/verifier-agent.py bug       → vérifie analyse des échecs
#   python agents/verifier-agent.py kpi       → vérifie calculs KPI
#   python agents/verifier-agent.py sync      → vérifie cohérence Allure ↔ Jira
#   python agents/verifier-agent.py tc        → vérifie les cas de test
#   python agents/verifier-agent.py all       → tout vérifier en séquence
# ============================================================

import sys, os, json, glob, re, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm
from jira_fetcher_agent import JiraClient, JIRA_BASE_URL
import requests

FRAMEWORK    = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FEATURES_DIR = os.path.join(FRAMEWORK, "features")
RESULTS_DIR  = os.path.join(FRAMEWORK, "allure-results")
DOCS_DIR     = os.path.join(FRAMEWORK, "docs")
ENV_FILE     = os.path.join(RESULTS_DIR, "environment.properties")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

VERDICT_OK   = f"{G}{W} VALID   {E}"
VERDICT_WARN = f"{Y}{W} WARNING {E}"
VERDICT_KO   = f"{R}{W} INVALID {E}"


# ── Helpers ────────────────────────────────────────────────────────────────

def print_header(title: str):
    print(f"\n{W}{'='*58}{E}")
    print(f"{W}  {title}{E}")
    print(f"{W}{'='*58}{E}")

def print_check(label: str, ok: bool, detail: str = ""):
    sym = f"{G}✓{E}" if ok else f"{R}✗{E}"
    det = f"  {Y}→ {detail}{E}" if detail and not ok else (f"  {C}→ {detail}{E}" if detail else "")
    print(f"  {sym}  {label}{det}")

def verdict_color(v: str) -> str:
    return {
        "VALID":   VERDICT_OK,
        "WARNING": VERDICT_WARN,
        "INVALID": VERDICT_KO,
    }.get(v, VERDICT_KO)

def confidence_bar(score: float) -> str:
    filled = int(score * 20)
    color  = G if score >= 0.8 else Y if score >= 0.6 else R
    return f"{color}{'█' * filled}{'░' * (20 - filled)}{E} {int(score * 100)}%"


# ── 1. Vérification GHERKIN ────────────────────────────────────────────────

def verify_gherkin() -> dict:
    print_header("VÉRIFICATION GHERKIN — features/*.feature")

    feature_files = glob.glob(os.path.join(FEATURES_DIR, "*.feature"))
    if not feature_files:
        print(f"{R}  Aucun fichier .feature trouvé dans features/{E}")
        return {"verdict": "INVALID", "confidence": 1.0, "issues": ["Aucun fichier feature"]}

    issues  = []
    details = []
    total_scenarios = 0

    for fpath in sorted(feature_files):
        fname = os.path.basename(fpath)
        text  = open(fpath, encoding="utf-8").read()
        lines = text.splitlines()

        has_feature  = any(l.strip().startswith("Feature:") for l in lines)
        has_scenario = any(l.strip().startswith("Scenario:") for l in lines)
        has_given    = any(re.match(r"\s+(Given|Étant)", l) for l in lines)
        has_when     = any(re.match(r"\s+(When|Quand)", l) for l in lines)
        has_then     = any(re.match(r"\s+(Then|Alors)", l) for l in lines)
        tc_tags      = re.findall(r"@TC-\d+", text)
        smoke_tags   = re.findall(r"@smoke", text)
        critical_tags = re.findall(r"@critical", text)
        scenarios    = [l for l in lines if l.strip().startswith("Scenario:")]
        total_scenarios += len(scenarios)

        print(f"\n  {C}[{fname}]{E}")
        print_check("Feature: présent",         has_feature)
        print_check("Scenario: présent",        has_scenario)
        print_check("Given/When/Then présents", has_given and has_when and has_then)
        print_check(f"Tags @TC-xxx ({len(tc_tags)} trouvés)", len(tc_tags) >= len(scenarios) - 1,
                    f"{len(tc_tags)} tags TC pour {len(scenarios)} scénarios")
        print_check(f"Tags @smoke ({len(smoke_tags)})",   len(smoke_tags) > 0)
        print_check(f"Tags @critical ({len(critical_tags)})", len(critical_tags) > 0)

        if not has_feature:  issues.append(f"{fname}: Feature: manquant")
        if not has_scenario: issues.append(f"{fname}: Aucun Scenario:")
        if not (has_given and has_when and has_then):
            issues.append(f"{fname}: Structure BDD incomplète (Given/When/Then)")
        if len(tc_tags) < len(scenarios) - 1:
            issues.append(f"{fname}: {len(scenarios) - len(tc_tags)} scénarios sans @TC-xxx")

        details.append(text[:1500])  # pour LLM

    # Analyse LLM adversariale
    print(f"\n{C}  Analyse LLM adversariale des features...{E}")
    sample = "\n\n---\n".join(details[:3])  # max 3 fichiers
    result = llm.chat_adversarial(
        original_output=f"Features Gherkin générées ({total_scenarios} scénarios)",
        context=f"Contenu des features :\n{sample}",
        domain="BDD / Gherkin QA"
    )

    # Merge avec les issues déterministes
    if issues:
        result["issues"] = issues + result.get("issues", [])
        if result["verdict"] == "VALID":
            result["verdict"] = "WARNING"

    _print_result(result)
    return result


# ── 2. Vérification BUG ANALYSIS ──────────────────────────────────────────

def verify_bug() -> dict:
    print_header("VÉRIFICATION ANALYSE DES BUGS — Allure résultats")

    failures = []
    for f in glob.glob(os.path.join(RESULTS_DIR, "*-result.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
            if d.get("status") in ("failed", "broken"):
                failures.append({
                    "name":    d.get("name", "?"),
                    "status":  d.get("status"),
                    "message": (d.get("statusDetails") or {}).get("message", "")[:300],
                    "tc":      next((lb["value"] for lb in d.get("labels", [])
                                     if lb["name"] == "tag" and re.match(r"tc-\d+", lb["value"])), None)
                })
        except Exception:
            pass

    if not failures:
        print(f"{G}  Aucun test en échec dans allure-results — rien à vérifier.{E}")
        return {"verdict": "VALID", "confidence": 1.0, "issues": [],
                "summary": "Aucun test en échec."}

    print(f"  {Y}{len(failures)} test(s) en échec détectés{E}")
    for f in failures[:5]:
        print(f"  {R}✗{E}  [{f['tc'] or '?'}] {f['name'][:60]}")
        if f["message"]:
            print(f"       {Y}→ {f['message'][:80]}{E}")

    # LLM : première analyse (générateur)
    print(f"\n{C}  Analyse LLM (agent générateur)...{E}")
    analysis_prompt = [{
        "role": "user",
        "content": (
            f"Analyse ces {len(failures)} tests en échec et donne une cause racine pour chacun :\n"
            + "\n".join([f"- [{f['tc']}] {f['name']}: {f['message'][:150]}" for f in failures])
        )
    }]
    analysis = llm.chat_cot(analysis_prompt)

    # LLM : vérification adversariale
    print(f"{C}  Vérification adversariale (agent vérificateur)...{E}")
    context = "\n".join([
        f"[{f['tc']}] {f['name']} | {f['status']} | {f['message'][:200]}"
        for f in failures
    ])
    result = llm.chat_adversarial(
        original_output=analysis,
        context=f"Données brutes des échecs :\n{context}",
        domain="QA / Test Failure Analysis"
    )

    _print_result(result)
    return result


# ── 3. Vérification KPI ────────────────────────────────────────────────────

def verify_kpi() -> dict:
    print_header("VÉRIFICATION KPI — Cohérence kpi-agent ↔ allure-results")

    # Lire environment.properties (généré par kpi-agent)
    if not os.path.exists(ENV_FILE):
        print(f"{Y}  environment.properties introuvable — lance kpi-agent.py d'abord.{E}")
        return {"verdict": "WARNING", "confidence": 0.5,
                "issues": ["environment.properties manquant"],
                "summary": "Impossible de vérifier sans environment.properties"}

    env = {}
    for line in open(ENV_FILE, encoding="utf-8"):
        if "=" in line:
            k, v = line.strip().split("=", 1)
            env[k.strip()] = v.strip()

    # Recalculer depuis les données brutes
    stats = {"passed": 0, "failed": 0, "broken": 0, "total": 0}
    for f in glob.glob(os.path.join(RESULTS_DIR, "*-result.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
            s = d.get("status", "unknown")
            if s in stats:
                stats[s] += 1
            stats["total"] += 1
        except Exception:
            pass

    total = stats["total"] or 1
    real_pass_rate = round(stats["passed"] / total * 100, 1)
    real_fail_rate = round(stats["failed"] / total * 100, 1)

    issues = []
    declared_pass = float(env.get("Pass.Rate", "0").replace("%", ""))
    declared_fail = float(env.get("Fail.Rate", "0").replace("%", ""))

    diff_pass = abs(real_pass_rate - declared_pass)
    diff_fail = abs(real_fail_rate - declared_fail)
    THRESHOLD = 1.0  # tolérance 1%

    print(f"\n  {'KPI':<25} {'kpi-agent':>12} {'Recalculé':>12} {'Écart':>8} {'Statut':>8}")
    print(f"  {'-'*67}")

    def kpi_row(label, declared, real, diff):
        ok = diff <= THRESHOLD
        sym = f"{G}✓{E}" if ok else f"{R}✗{E}"
        status = "OK" if ok else f"ÉCART {diff:.1f}%"
        print(f"  {sym}  {label:<23} {declared:>11.1f}% {real:>11.1f}% {diff:>7.1f}% {status:>8}")
        return ok

    ok_pass = kpi_row("Pass Rate", declared_pass, real_pass_rate, diff_pass)
    ok_fail = kpi_row("Fail Rate", declared_fail, real_fail_rate, diff_fail)

    if not ok_pass: issues.append(f"Pass Rate déclarée {declared_pass}% ≠ calculée {real_pass_rate}%")
    if not ok_fail: issues.append(f"Fail Rate déclarée {declared_fail}% ≠ calculée {real_fail_rate}%")

    verdict   = "VALID" if not issues else "INVALID"
    confidence = 0.98 if not issues else 0.95
    result = {"verdict": verdict, "confidence": confidence,
              "issues": issues,
              "summary": f"KPIs vérifiés — {len(issues)} incohérence(s) détectée(s)"}
    _print_result(result)
    return result


# ── 4. Vérification SYNC Allure ↔ Jira ────────────────────────────────────

def verify_sync() -> dict:
    print_header("VÉRIFICATION SYNC — Allure résultats ↔ Jira statuts")

    # Statuts Allure
    allure_statuses = {}
    for f in glob.glob(os.path.join(RESULTS_DIR, "*-result.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
            tc = next((lb["value"] for lb in d.get("labels", [])
                        if lb["name"] == "tag" and re.match(r"tc-\d+", lb["value"])), None)
            if tc:
                allure_statuses[tc] = d.get("status", "unknown")
        except Exception:
            pass

    if not allure_statuses:
        print(f"{Y}  Aucun TC trouvé dans allure-results.{E}")
        return {"verdict": "WARNING", "confidence": 0.5,
                "issues": ["Aucun TC dans allure-results"],
                "summary": "Impossible de vérifier la synchronisation"}

    # Statuts Jira
    jira = JiraClient()
    issues_list = []
    discrepancies = []

    try:
        resp = requests.get(
            f"{JIRA_BASE_URL}/rest/api/3/search",
            params={"jql": "project=HBAPI AND issuetype='Test Case'", "maxResults": 100,
                    "fields": "summary,status,labels"},
            auth=jira.auth, headers=jira.headers, verify=False
        )
        if resp.status_code == 200:
            issues_list = resp.json().get("issues", [])
    except Exception as e:
        print(f"{Y}  Jira inaccessible : {e}{E}")

    print(f"\n  Allure : {len(allure_statuses)} TCs | Jira : {len(issues_list)} issues")

    # Mapping Jira : "Terminé" → passed, "En cours" → failed/broken
    JIRA_TO_ALLURE = {"Terminé": "passed", "Done": "passed",
                       "En cours": "failed", "In Progress": "failed",
                       "À faire": "failed", "To Do": "failed"}

    checked = 0
    for issue in issues_list[:20]:
        summary = issue["fields"]["summary"]
        jira_status = issue["fields"]["status"]["name"]
        tc_match = re.search(r"TC-(\d+)", summary, re.IGNORECASE)
        if not tc_match:
            continue
        tc_key = f"tc-{int(tc_match.group(1)):03d}"
        allure_status = allure_statuses.get(tc_key)
        if not allure_status:
            continue

        expected_allure = JIRA_TO_ALLURE.get(jira_status)
        ok = (expected_allure == allure_status)
        checked += 1
        print_check(
            f"{tc_key} : Jira={jira_status} ↔ Allure={allure_status}",
            ok,
            "DÉSYNCHRONISÉ" if not ok else ""
        )
        if not ok:
            discrepancies.append(
                f"{tc_key}: Jira='{jira_status}' mais Allure='{allure_status}'"
            )

    if checked == 0:
        print(f"{Y}  Aucun TC matchable entre Allure et Jira.{E}")

    verdict    = "VALID" if not discrepancies else "WARNING" if len(discrepancies) < 3 else "INVALID"
    confidence = 0.95 if not discrepancies else 0.7
    result = {
        "verdict": verdict,
        "confidence": confidence,
        "issues": discrepancies,
        "summary": f"{checked} TCs vérifiés — {len(discrepancies)} désynchronisation(s)"
    }
    _print_result(result)
    return result


# ── 5. Vérification TC (cas de test) ──────────────────────────────────────

def verify_tc() -> dict:
    print_header("VÉRIFICATION TCs — Qualité & complétude des cas de test")

    feature_files = glob.glob(os.path.join(FEATURES_DIR, "*.feature"))
    issues = []
    all_tc_numbers = []
    all_scenarios_text = []

    for fpath in sorted(feature_files):
        fname = os.path.basename(fpath)
        text  = open(fpath, encoding="utf-8").read()
        scenarios = re.findall(r"Scenario:.*?(?=Scenario:|$)", text, re.DOTALL)
        tc_nums   = [int(m) for m in re.findall(r"TC-(\d+)", text)]
        all_tc_numbers.extend(tc_nums)
        all_scenarios_text.append(f"# {fname}\n{text[:800]}")

        # Checks déterministes
        no_tc = [s.strip()[:60] for s in scenarios if not re.search(r"TC-\d+", s)]
        if no_tc:
            issues.append(f"{fname}: {len(no_tc)} scénario(s) sans numéro TC")

        no_type = [s.strip()[:60] for s in scenarios
                   if not any(tag in s for tag in ["positif", "negatif", "securite", "limite"])]
        if no_type:
            issues.append(f"{fname}: {len(no_type)} scénario(s) sans tag de type (positif/negatif/securite)")

    # Vérifier les doublons de TC
    duplicates = [n for n in all_tc_numbers if all_tc_numbers.count(n) > 1]
    duplicates = list(set(duplicates))
    if duplicates:
        issues.append(f"TCs dupliqués : {sorted(duplicates)}")

    print(f"\n  TCs trouvés : {len(all_tc_numbers)} | Doublons : {len(duplicates)}")
    print_check("Tous les TCs ont un numéro unique",  not duplicates,
                f"Doublons : {duplicates}" if duplicates else "")
    print_check("Tous les scénarios ont un @TC-xxx",
                not any("sans numéro TC" in i for i in issues))
    print_check("Tous les scénarios ont un tag de type",
                not any("sans tag de type" in i for i in issues))

    # LLM : analyse adversariale qualité des TCs
    print(f"\n{C}  Analyse LLM adversariale — qualité et complétude...{E}")
    sample = "\n\n".join(all_scenarios_text[:3])
    result = llm.chat_adversarial(
        original_output=f"{len(all_tc_numbers)} cas de test BDD générés",
        context=f"Extraits des features :\n{sample}",
        domain="QA / Test Cases BDD"
    )

    if issues:
        result["issues"] = issues + result.get("issues", [])
        if result["verdict"] == "VALID":
            result["verdict"] = "WARNING"

    _print_result(result)
    return result


# ── Affichage du résultat ──────────────────────────────────────────────────

def _print_result(result: dict):
    verdict    = result.get("verdict", "INVALID")
    confidence = result.get("confidence", 0.0)
    issues     = result.get("issues", [])
    summary    = result.get("summary", "")

    print(f"\n  Verdict    : {verdict_color(verdict)}")
    print(f"  Confiance  : [{confidence_bar(confidence)}]")
    if summary:
        print(f"  Résumé     : {summary}")
    if issues:
        print(f"\n  {R}Problèmes détectés ({len(issues)}) :{E}")
        for issue in issues[:5]:
            print(f"    {R}→{E} {issue}")
    elif verdict == "VALID":
        print(f"  {G}Aucun problème détecté.{E}")
    if result.get("needs_human_review"):
        print(f"\n  {Y}⚠ Révision humaine recommandée (confiance < 70%){E}")


# ── Rapport final ──────────────────────────────────────────────────────────

def print_final_report(results: dict):
    print(f"\n{W}{'='*58}{E}")
    print(f"{W}  RAPPORT FINAL — VERIFIER AGENT{E}")
    print(f"{W}{'='*58}{E}\n")
    print(f"  {'Vérification':<20} {'Verdict':>10} {'Confiance':>12} {'Problèmes':>10}")
    print(f"  {'-'*54}")

    total_issues = 0
    for name, r in results.items():
        v  = r.get("verdict", "?")
        c  = r.get("confidence", 0.0)
        nb = len(r.get("issues", []))
        total_issues += nb
        vc = G if v == "VALID" else Y if v == "WARNING" else R
        print(f"  {name:<20} {vc}{v:>10}{E} {int(c*100):>11}% {nb:>10}")

    print(f"\n  Total problèmes détectés : {R if total_issues else G}{total_issues}{E}")
    gate = "PASSED" if total_issues == 0 else "FAILED"
    color = G if gate == "PASSED" else R
    print(f"  Quality Gate Verifier    : {color}{W} {gate} {E}\n")


# ── Main ───────────────────────────────────────────────────────────────────

def print_help():
    print(f"""
{W}VERIFIER AGENT — Contrôle qualité des autres agents{E}

  python agents/verifier-agent.py gherkin   Vérifie features/*.feature
  python agents/verifier-agent.py bug       Vérifie l'analyse des échecs Allure
  python agents/verifier-agent.py kpi       Vérifie les calculs KPI
  python agents/verifier-agent.py sync      Vérifie cohérence Allure ↔ Jira
  python agents/verifier-agent.py tc        Vérifie la qualité des TCs
  python agents/verifier-agent.py all       Toutes les vérifications

  Techniques : Checks déterministes + LLM adversarial + Confidence scoring
""")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    VERIFICATIONS = {
        "gherkin": verify_gherkin,
        "bug":     verify_bug,
        "kpi":     verify_kpi,
        "sync":    verify_sync,
        "tc":      verify_tc,
    }

    if cmd == "all":
        results = {}
        for name, fn in VERIFICATIONS.items():
            results[name] = fn()
        print_final_report(results)

    elif cmd in VERIFICATIONS:
        VERIFICATIONS[cmd]()

    else:
        print_help()
