# ============================================================
# QA Agent — Analyse la qualité de la suite de tests BDD
# ============================================================
# Lit les résultats Allure (allure-results/*.json) et les
# features Gherkin pour évaluer la qualité de la suite :
#   - couverture (cas positifs, négatifs, edge cases)
#   - distribution des statuts (pass/fail/broken/skipped)
#   - tags manquants (@smoke, @critical, @regression)
#   - TCs sans assertions Gherkin (scénarios vides)
#   - cohérence entre features et résultats
#
# Usage:
#   python agents/qa-agent.py              → rapport complet
#   python agents/qa-agent.py coverage     → analyse couverture
#   python agents/qa-agent.py tags         → vérification des tags
#   python agents/qa-agent.py summary      → résumé console
#   python agents/qa-agent.py --dry-run    → aperçu sans écrire
# ============================================================

import sys, os, json, glob
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm

FRAMEWORK    = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS_DIR  = os.path.join(FRAMEWORK, "allure-results")
FEATURES_DIR = os.path.join(FRAMEWORK, "features")
DOCS_DIR     = os.path.join(FRAMEWORK, "docs")
DRY_RUN      = "--dry-run" in sys.argv
CMD          = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "report"

G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"; R = "\033[31m"; E = "\033[0m"; W = "\033[1m"

REQUIRED_TAGS = {"smoke", "critical", "regression"}

QA_SCHEMA = {
    "overall_score":     "integer 0-100 — score global de qualité",
    "coverage_score":    "integer 0-100 — couverture cas positifs/négatifs/edge",
    "tag_score":         "integer 0-100 — complétude des tags",
    "strengths":         ["string — point fort"],
    "issues":            [{"tc": "string", "issue": "string", "severity": "high|medium|low"}],
    "missing_scenarios": ["string — cas de test manquant recommandé"],
    "recommendations":   ["string — action prioritaire"],
    "summary":           "string — résumé exécutif en 2-3 phrases"
}


# ── Chargement des résultats Allure ───────────────────────────────────────────

def load_allure_results() -> list[dict]:
    results = []
    for path in glob.glob(os.path.join(RESULTS_DIR, "*-result.json")):
        try:
            with open(path, encoding="utf-8") as f:
                results.append(json.load(f))
        except Exception:
            pass
    return results


def load_features() -> dict[str, str]:
    features = {}
    for path in glob.glob(os.path.join(FEATURES_DIR, "*.feature")):
        try:
            with open(path, encoding="utf-8") as f:
                features[os.path.basename(path)] = f.read()
        except Exception:
            pass
    return features


# ── Calculs déterministes ─────────────────────────────────────────────────────

def compute_stats(results: list[dict]) -> dict:
    stats = {"passed": 0, "failed": 0, "broken": 0, "skipped": 0, "total": 0}
    for r in results:
        s = r.get("status", "unknown")
        if s in stats:
            stats[s] += 1
        stats["total"] += 1

    stats["pass_rate"] = round(stats["passed"] / stats["total"] * 100, 1) if stats["total"] else 0.0

    # Tags présents dans les résultats
    all_labels = [lbl.get("value", "") for r in results for lbl in r.get("labels", [])]
    found_tags = {t for t in REQUIRED_TAGS if any(t in v.lower() for v in all_labels)}
    stats["tags_found"]   = sorted(found_tags)
    stats["tags_missing"] = sorted(REQUIRED_TAGS - found_tags)

    # TCs sans étapes Gherkin
    stats["empty_tcs"] = [
        r.get("name", "?")
        for r in results
        if not r.get("steps") and r.get("status") != "skipped"
    ]

    return stats


def build_features_summary(features: dict[str, str]) -> str:
    lines = []
    for name, content in features.items():
        scenarios = [l.strip() for l in content.splitlines() if l.strip().startswith("Scenario:")]
        lines.append(f"{name} → {len(scenarios)} scénario(s)")
    return "\n".join(lines)


# ── Analyse LLM ───────────────────────────────────────────────────────────────

def analyze(results: list[dict], features: dict[str, str]) -> dict:
    stats = compute_stats(results)

    # Résumé des échecs pour le LLM
    failures = [
        {
            "name":    r.get("name", "?"),
            "status":  r.get("status"),
            "message": (r.get("statusDetails") or {}).get("message", "")[:200],
        }
        for r in results if r.get("status") in ("failed", "broken")
    ][:20]

    features_summary = build_features_summary(features)

    prompt = f"""Tu es un expert QA. Analyse cette suite de tests BDD API.

STATISTIQUES :
- Total TCs : {stats['total']}
- Pass rate : {stats['pass_rate']}%
- Passed: {stats['passed']} | Failed: {stats['failed']} | Broken: {stats['broken']} | Skipped: {stats['skipped']}
- Tags présents : {stats['tags_found']}
- Tags manquants : {stats['tags_missing']}
- TCs sans étapes : {stats['empty_tcs']}

FEATURES ({len(features)} fichiers) :
{features_summary}

ECHECS ({len(failures)}) :
{json.dumps(failures, ensure_ascii=False, indent=2)}

Évalue la qualité de cette suite : couverture cas positifs/négatifs/edge, organisation,
tags de priorisation (@smoke/@critical/@regression), cohérence des assertions.
"""
    return llm.chat_structured([{"role": "user", "content": prompt}], QA_SCHEMA)


# ── Commandes ─────────────────────────────────────────────────────────────────

def cmd_summary(results, features):
    stats = compute_stats(results)
    print(f"\n{W}=== QA AGENT — RÉSUMÉ ==={E}")
    print(f"  TCs total   : {stats['total']}")
    print(f"  Pass rate   : {G}{stats['pass_rate']}%{E}")
    print(f"  Failed      : {R}{stats['failed']}{E}  Broken: {R}{stats['broken']}{E}")
    print(f"  Tags OK     : {G}{stats['tags_found']}{E}")
    if stats['tags_missing']:
        print(f"  Tags absent : {Y}{stats['tags_missing']}{E}")
    if stats['empty_tcs']:
        print(f"  TCs vides   : {Y}{stats['empty_tcs']}{E}")
    print(f"  Features    : {len(features)} fichier(s)")


def cmd_coverage(results, features):
    stats = compute_stats(results)
    print(f"\n{W}=== COUVERTURE ==={E}")
    features_summary = build_features_summary(features)
    print(features_summary)
    print(f"\nPass rate global : {stats['pass_rate']}%")
    print(f"Tags de priorité manquants : {stats['tags_missing'] or 'aucun'}")


def cmd_tags(results, _features):
    stats = compute_stats(results)
    print(f"\n{W}=== TAGS ==={E}")
    print(f"  Trouvés  : {G}{stats['tags_found']}{E}")
    print(f"  Absents  : {R}{stats['tags_missing']}{E}")
    if stats['empty_tcs']:
        print(f"  TCs sans étapes : {Y}{stats['empty_tcs']}{E}")


def cmd_report(results, features):
    print(f"  {C}Analyse qualité (LLM)...{E}")
    analysis = analyze(results, features)

    os.makedirs(DOCS_DIR, exist_ok=True)
    out_html = os.path.join(DOCS_DIR, "qa-report.html")
    stats    = compute_stats(results)

    score_color = "#43e97b" if analysis.get("overall_score", 0) >= 75 else \
                  "#ffd700" if analysis.get("overall_score", 0) >= 50 else "#ef4444"

    issues_rows = "".join(
        f"<tr><td style='color:#f9a8d4'>{i.get('tc','')}</td>"
        f"<td style='color:#e2e8f0'>{i.get('issue','')}</td>"
        f"<td style='color:{'#ef4444' if i.get('severity')=='high' else '#fcd34d' if i.get('severity')=='medium' else '#86efac'}'>"
        f"{i.get('severity','').upper()}</td></tr>"
        for i in analysis.get("issues", [])
    )
    reco_items = "".join(f"<li>{r}</li>" for r in analysis.get("recommendations", []))
    missing_items = "".join(f"<li>{m}</li>" for m in analysis.get("missing_scenarios", []))
    strengths_items = "".join(f"<li>{s}</li>" for s in analysis.get("strengths", []))

    html = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<title>QA Report</title>
<style>
body{{font-family:'Segoe UI',sans-serif;background:#0f1117;color:#e2e8f0;margin:0;padding:32px;line-height:1.7}}
.hero{{background:linear-gradient(135deg,#1a1d27,#1e2130);border:1px solid #2a2d3e;border-radius:16px;padding:28px 32px;margin-bottom:28px;display:flex;align-items:center;gap:28px}}
.score-circle{{width:90px;height:90px;border-radius:50%;background:conic-gradient({score_color} {analysis.get('overall_score',0)}%, #2a2d3e 0);display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:900;color:{score_color};flex-shrink:0}}
.title h1{{font-size:24px;font-weight:800;margin:0 0 6px}}
.summary{{color:#94a3b8;font-size:14px;max-width:600px}}
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px}}
.stat-card{{background:#1a1d27;border:1px solid #2a2d3e;border-radius:12px;padding:16px;text-align:center}}
.stat-val{{font-size:28px;font-weight:900;display:block}}
.stat-lbl{{font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:1px}}
.section{{background:#1a1d27;border:1px solid #2a2d3e;border-radius:12px;padding:20px 24px;margin-bottom:18px}}
.section h2{{font-size:16px;font-weight:700;color:#a78bfa;margin:0 0 14px;padding-bottom:8px;border-bottom:1px solid #2a2d3e}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{background:#1e2130;padding:8px 12px;text-align:left;color:#7dd3fc;font-size:11px;letter-spacing:1px;text-transform:uppercase;border-bottom:1px solid #2a2d3e}}
td{{padding:8px 12px;border-bottom:1px solid rgba(255,255,255,.04)}}
ul{{margin:0;padding-left:18px;font-size:13px;color:#cbd5e1}}
li{{margin-bottom:4px}}
</style></head><body>
<div class="hero">
  <div class="score-circle">{analysis.get('overall_score',0)}</div>
  <div class="title">
    <h1>QA Report — Suite BDD API</h1>
    <div class="summary">{analysis.get('summary','')}</div>
  </div>
</div>
<div class="stats">
  <div class="stat-card"><span class="stat-val" style="color:#43e97b">{stats['passed']}</span><span class="stat-lbl">Passed</span></div>
  <div class="stat-card"><span class="stat-val" style="color:#ef4444">{stats['failed']}</span><span class="stat-lbl">Failed</span></div>
  <div class="stat-card"><span class="stat-val" style="color:#fcd34d">{stats['broken']}</span><span class="stat-lbl">Broken</span></div>
  <div class="stat-card"><span class="stat-val" style="color:#6c63ff">{stats['pass_rate']}%</span><span class="stat-lbl">Pass Rate</span></div>
</div>
{'<div class="section"><h2>⚠ Problèmes détectés</h2><table><thead><tr><th>TC</th><th>Problème</th><th>Sévérité</th></tr></thead><tbody>' + issues_rows + '</tbody></table></div>' if issues_rows else ''}
<div class="section"><h2>✅ Points forts</h2><ul>{strengths_items}</ul></div>
<div class="section"><h2>📋 Recommandations prioritaires</h2><ul>{reco_items}</ul></div>
{'<div class="section"><h2>➕ Scénarios manquants recommandés</h2><ul>' + missing_items + '</ul></div>' if missing_items else ''}
<div style="text-align:center;color:#475569;font-size:12px;margin-top:24px">Généré par qa-agent.py · {llm.MODEL}</div>
</body></html>"""

    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  {G}✓ Rapport HTML : {out_html}{E}")

    # Résumé console
    score = analysis.get("overall_score", 0)
    color = G if score >= 75 else Y if score >= 50 else R
    print(f"\n  Score qualité : {color}{score}/100{E}")
    print(f"  Couverture    : {analysis.get('coverage_score', 0)}/100")
    print(f"  Tags          : {analysis.get('tag_score', 0)}/100")
    if analysis.get("issues"):
        print(f"  Problèmes     : {R}{len(analysis['issues'])} détecté(s){E}")
    if analysis.get("recommendations"):
        print(f"\n  Top recommandation : {Y}{analysis['recommendations'][0]}{E}")


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    print(f"\n{W}=== QA AGENT [{llm.MODEL}] ==={E}")

    results = load_allure_results()
    features = load_features()

    if not results:
        print(f"  {Y}⚠  Aucun résultat Allure dans {RESULTS_DIR}{E}")
        print(f"     Lance d'abord : pytest tests/ --alluredir=allure-results")
        return

    print(f"  {C}{len(results)} résultats Allure · {len(features)} features{E}")

    if CMD == "summary":
        cmd_summary(results, features)
    elif CMD == "coverage":
        cmd_coverage(results, features)
    elif CMD == "tags":
        cmd_tags(results, features)
    else:
        if DRY_RUN:
            cmd_summary(results, features)
        else:
            cmd_report(results, features)


if __name__ == "__main__":
    run()
