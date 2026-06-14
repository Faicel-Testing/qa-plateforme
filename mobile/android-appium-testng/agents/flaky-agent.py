# ============================================================
# Flaky Agent — Mobile (Appium / Android)
# ============================================================
# Détecte les tests instables en analysant :
#   1. Les patterns d'erreur dans target/allure-results/
#      (TimeoutException, StaleElementException, WebDriverException)
#   2. Les retries consommés (TestNG RetryAnalyzer)
#
# Note : contrairement au framework API, on ne re-run PAS Maven
# automatiquement (trop lent, nécessite un device/émulateur actif).
# Le agent analyse les résultats existants et utilise le LLM
# pour identifier les tests potentiellement flaky.
#
# Usage:
#   python agents/flaky-agent.py detect   → analyse les résultats actuels
#   python agents/flaky-agent.py report   → rapport détaillé avec LLM
#   python agents/flaky-agent.py gono-go  → verdict production
# ============================================================

import sys, os, json, glob, time, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm

FRAMEWORK   = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS_DIR = os.path.join(FRAMEWORK, "target", "allure-results")
DOCS_DIR    = os.path.join(FRAMEWORK, "docs")
FLAKY_FILE  = os.path.join(DOCS_DIR, "flaky-report.json")

FLAKY_THRESHOLD = 0.40  # score > 40% → considéré flaky

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

# Patterns d'erreur = indicateurs de flakiness sur mobile
FLAKY_PATTERNS = [
    (r"TimeoutException",              "timeout",    0.80),
    (r"StaleElementReferenceException", "stale",     0.85),
    (r"WebDriverException",            "webdriver",  0.65),
    (r"NoSuchSessionException",        "session",    0.70),
    (r"ElementNotInteractableException","interact",  0.70),
    (r"ElementClickInterceptedException","intercept", 0.60),
    (r"Connection refused",            "connection", 0.75),
    (r"ADB connection",                "adb",        0.80),
    (r"An unknown server-side error",  "server",     0.60),
    (r"Original error: Error",         "driver",     0.55),
]

# Tests dans les groupes "quarantine" = déjà marqués flaky
QUARANTINE_TESTS = {"Test08_SignupNegative", "Test14_SignupWeakPassword"}


# ── Chargement des résultats ───────────────────────────────────────────────

def load_all_results() -> list:
    results = []
    for f in glob.glob(os.path.join(RESULTS_DIR, "*-result.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
            labels     = d.get("labels", [])
            test_class = next((lb["value"] for lb in labels if lb["name"] == "testClass"), "?")
            short_cls  = test_class.split(".")[-1] if "." in test_class else test_class
            groups     = [lb["value"] for lb in labels if lb["name"] == "tag"]
            detail     = d.get("statusDetails") or {}
            results.append({
                "name":       d.get("name", "?"),
                "test_class": short_cls,
                "status":     d.get("status", "unknown"),
                "groups":     groups,
                "message":    detail.get("message", ""),
                "trace":      detail.get("trace",   ""),
            })
        except Exception:
            pass
    return results


def score_flakiness(result: dict) -> tuple:
    """Retourne (score 0.0-1.0, pattern_hit) basé sur les patterns d'erreur."""
    text = (result.get("message", "") + " " + result.get("trace", "")).lower()
    if result["status"] == "passed":
        return 0.0, None
    if result["status"] in ("failed", "broken"):
        for pattern, name, score in FLAKY_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return score, name
    return 0.0, None


# ── Analyse LLM ───────────────────────────────────────────────────────────

def llm_analyse_flaky(candidates: list) -> str:
    if not candidates:
        return "Aucun test flaky suspect détecté sur la session courante."
    items = "\n".join([
        f"- {r['test_class']}.{r['name']} — pattern={r['_pattern']} score={int(r['_score']*100)}%\n"
        f"  Erreur: {r['message'][:120]}"
        for r in candidates
    ])
    return llm.chat([{"role": "user", "content": (
        f"Tu es QA Lead Mobile (Appium/Android). Ces tests présentent des patterns d'instabilité :\n{items}\n\n"
        f"Pour chaque test :\n"
        f"1. Confirme si c'est vraiment flaky ou un vrai bug\n"
        f"2. Donne la cause principale (device, locator, timing, réseau)\n"
        f"3. Propose une action corrective concrète (ex: augmenter le wait, ajouter retry, stabiliser le locator)\n"
        f"Sois concis et actionnable."
    )}])


# ── Commandes ──────────────────────────────────────────────────────────────

def cmd_detect() -> list:
    print(f"\n{W}FLAKY AGENT MOBILE — Détection par patterns d'erreur{E}")
    print(f"{C}Source : target/allure-results/{E}")
    print(f"{Y}Seuil flakiness : {int(FLAKY_THRESHOLD*100)}%{E}\n")

    all_results = load_all_results()
    if not all_results:
        print(f"{Y}  Aucun résultat dans target/allure-results/.{E}")
        return []

    total   = len(all_results)
    passed  = sum(1 for r in all_results if r["status"] == "passed")
    failed  = sum(1 for r in all_results if r["status"] in ("failed", "broken"))
    print(f"  {total} tests analysés : {G}{passed} passés{E} · {R}{failed} échoués{E}\n")

    candidates = []
    for r in all_results:
        score, pattern = score_flakiness(r)
        if score >= FLAKY_THRESHOLD:
            r["_score"]   = score
            r["_pattern"] = pattern
            candidates.append(r)

    # Tests en quarantaine = flaky par définition
    quarantined = [r for r in all_results
                   if r["test_class"] in QUARANTINE_TESTS and r not in candidates]
    for r in quarantined:
        r["_score"]   = 1.0
        r["_pattern"] = "quarantine"
        candidates.append(r)

    if not candidates:
        print(f"{G}  Aucun test flaky suspect détecté.{E}")
        return []

    print(f"  {Y}{len(candidates)} test(s) suspect(s) :{E}\n")
    for r in sorted(candidates, key=lambda x: -x["_score"]):
        crit = f" {R}[QUARANTINE]{E}" if r["_pattern"] == "quarantine" else ""
        print(f"  {Y}~{E} {r['test_class']}.{r['name'][:40]}{crit}")
        print(f"    Pattern : {C}{r['_pattern']}{E}  |  Score : {int(r['_score']*100)}%")
        if r.get("message"):
            print(f"    Erreur  : {r['message'][:90]}")
        print()

    report = {
        "timestamp":   time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total":       total,
        "flaky_tests": {
            f"{r['test_class']}.{r['name']}": {
                "score":   r["_score"],
                "pattern": r["_pattern"],
                "message": r.get("message","")[:200],
                "groups":  r.get("groups", []),
            } for r in candidates
        }
    }
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(FLAKY_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"{G}  Rapport sauvegardé → docs/flaky-report.json{E}")
    return candidates


def cmd_report():
    print(f"\n{W}FLAKY REPORT MOBILE — Analyse LLM{E}\n")

    candidates = cmd_detect()
    if not candidates:
        return

    print(f"\n{C}  Analyse LLM des causes et actions correctives...{E}\n")
    analysis = llm_analyse_flaky(candidates)
    print(f"{Y}  Analyse :{E}")
    for line in analysis.strip().split("\n"):
        print(f"  {line}")

    # Rapport HTML
    rows = ""
    for r in sorted(candidates, key=lambda x: -x["_score"]):
        score_pct = int(r["_score"] * 100)
        color     = "#e74c3c" if score_pct >= 75 else "#e67e22"
        quar      = '<span style="background:#e74c3c;color:#fff;padding:1px 6px;border-radius:3px;font-size:11px">QUARANTINE</span>' if r["_pattern"] == "quarantine" else ""
        rows += f"""
        <tr>
          <td style="font-family:monospace;font-size:12px">{r['test_class']}</td>
          <td style="font-size:12px">{r['name']}</td>
          <td><span style="background:{color};color:#fff;padding:2px 7px;border-radius:3px;font-size:12px">{r['_pattern']}</span></td>
          <td><div style="background:#eee;border-radius:4px;height:10px;width:100px;display:inline-block;overflow:hidden;vertical-align:middle"><div style="background:{color};width:{score_pct}%;height:100%"></div></div> {score_pct}%</td>
          <td style="font-size:11px;color:#666">{r.get('message','')[:80]}</td>
          <td>{quar}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="fr"><head>
<meta charset="utf-8">
<title>Flaky Agent Mobile</title>
<style>
  body{{font-family:Arial,sans-serif;background:#f5f5f5;color:#333;margin:0;padding:20px}}
  h1{{color:#2c3e50}} h2{{color:#34495e;margin-top:30px}}
  .stat{{display:inline-block;background:#fff;border-radius:8px;padding:15px 25px;margin:8px;box-shadow:0 2px 6px rgba(0,0,0,.1);text-align:center}}
  .stat-val{{font-size:28px;font-weight:bold}}
  .analysis{{background:#fff;border-radius:8px;padding:20px;box-shadow:0 2px 6px rgba(0,0,0,.1);margin:20px 0;white-space:pre-wrap;font-size:13px;line-height:1.6}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1);margin-top:15px}}
  th{{background:#2c3e50;color:#fff;padding:10px;text-align:left;font-size:13px}}
  td{{padding:9px 10px;border-bottom:1px solid #ecf0f1;vertical-align:middle}}
  tr:hover{{background:#f8f9fa}}
</style>
</head><body>
<h1>🔀 Flaky Agent — Mobile (Appium/Android)</h1>
<p style="color:#666">Détection par patterns d'erreur · Seuil : {int(FLAKY_THRESHOLD*100)}% · Source : target/allure-results/</p>
<div>
  <div class="stat"><div class="stat-val">{len(candidates)}</div>Tests suspects</div>
  <div class="stat"><div class="stat-val" style="color:#e74c3c">{sum(1 for r in candidates if r['_pattern'] == 'quarantine')}</div>En quarantaine</div>
  <div class="stat"><div class="stat-val" style="color:#e67e22">{sum(1 for r in candidates if r['_pattern'] == 'timeout')}</div>Timeout</div>
</div>
<h2>Analyse LLM</h2>
<div class="analysis">{analysis.replace('<','&lt;').replace('>','&gt;')}</div>
<h2>Tests suspects ({len(candidates)})</h2>
<table>
  <tr><th>Classe</th><th>Méthode</th><th>Pattern détecté</th><th>Score instabilité</th><th>Erreur</th><th>Statut</th></tr>
  {rows}
</table>
<p style="color:#999;font-size:12px;margin-top:30px">Flaky Agent Mobile · {time.strftime('%Y-%m-%d %H:%M')}</p>
</body></html>"""

    out = os.path.join(DOCS_DIR, "flaky-report.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n{G}  Rapport HTML : docs/flaky-report.html{E}")


def cmd_gono_go() -> bool:
    print(f"\n{W}FLAKY AGENT — GO / NO-GO PRODUCTION{E}")
    candidates = cmd_detect()

    critical_flaky = [r for r in candidates
                      if r["_score"] >= FLAKY_THRESHOLD and r["_pattern"] != "quarantine"
                      and "smoke" in r.get("groups", [])]

    print(f"\n{W}{'='*54}{E}")
    print(f"{W}  VERDICT FLAKY — GO / NO-GO PRODUCTION{E}")
    print(f"{W}{'='*54}{E}")

    if not critical_flaky:
        print(f"\n  {G}{W}  GO  {E}")
        print(f"{G}  Aucun test smoke flaky au-dessus du seuil ({int(FLAKY_THRESHOLD*100)}%).{E}")
        print(f"{G}  Résultats CI fiables pour la production.{E}\n")
        return True
    else:
        print(f"\n  {R}{W} NO-GO {E}")
        print(f"{R}  {len(critical_flaky)} test(s) smoke instable(s) — CI peu fiable :{E}")
        for r in critical_flaky:
            print(f"  {R}~{E} {r['test_class']}.{r['name']}  score={int(r['_score']*100)}%")
        print(f"\n{R}  Tests smoke flaky = résultats CI non fiables.{E}")
        print(f"{R}  Stabiliser ces tests avant déploiement.{E}\n")
        return False


def print_help():
    print(f"""
{W}FLAKY AGENT MOBILE{E}
Source : target/allure-results/

  python agents/flaky-agent.py detect    Détecte les tests instables par patterns
  python agents/flaky-agent.py report    Rapport complet avec analyse LLM
  python agents/flaky-agent.py gono-go   Verdict GO/NO-GO (tests smoke)

{W}Patterns détectés :{E}
  TimeoutException, StaleElementReferenceException, WebDriverException,
  NoSuchSessionException, ElementNotInteractableException, ADB errors

{W}Seuil :{E} {int(FLAKY_THRESHOLD*100)}% — si l'erreur correspond à un pattern = suspect flaky
""")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "detect":
        cmd_detect()
    elif cmd == "report":
        cmd_report()
    elif cmd == "gono-go":
        go = cmd_gono_go()
        sys.exit(0 if go else 1)
    else:
        print_help()
