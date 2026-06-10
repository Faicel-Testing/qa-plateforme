# ============================================================
# Predictive Agent — Prédiction des défaillances futures
# ============================================================
# Combine analyse déterministe des tendances (épisodes passés)
# et LLM CoT + Structured Output pour prédire :
#   - Quels TCs vont échouer au prochain run
#   - Si le Quality Gate va passer
#   - Quels tests deviennent flaky
#   - La tendance de la pass rate
#
# Usage:
#   python agents/predictive-agent.py predict    → TCs à risque
#   python agents/predictive-agent.py gate        → Quality Gate prédit
#   python agents/predictive-agent.py flaky       → candidats flaky futurs
#   python agents/predictive-agent.py trends      → tendances KPI
#   python agents/predictive-agent.py report      → rapport HTML complet
# ============================================================

import sys, os, json, glob, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm
import memory_store as mem

FRAMEWORK   = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS_DIR = os.path.join(FRAMEWORK, "allure-results")
ENV_FILE    = os.path.join(RESULTS_DIR, "environment.properties")
DOCS_DIR    = os.path.join(FRAMEWORK, "docs")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

# Schéma Structured Output pour les prédictions
PREDICTION_SCHEMA = {
    "type": "object",
    "properties": {
        "predictions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tc_id":               {"type": "string"},
                    "failure_probability": {"type": "number", "description": "0.0 à 1.0"},
                    "trend":               {"type": "string", "enum": ["degrading","stable","improving","volatile"]},
                    "predicted_category":  {"type": "string", "enum": ["real_bug","flaky","env_issue","false_positive","pass"]},
                    "alert_level":         {"type": "string", "enum": ["critical","high","medium","low","none"]},
                    "reasoning":           {"type": "string"}
                },
                "required": ["tc_id","failure_probability","trend","predicted_category","alert_level","reasoning"]
            }
        }
    },
    "required": ["predictions"]
}

GATE_SCHEMA = {
    "type": "object",
    "properties": {
        "gate_prediction":   {"type": "string", "enum": ["PASSED","FAILED","UNCERTAIN"]},
        "pass_rate_forecast": {"type": "number", "description": "Pass rate estimée en %"},
        "confidence":        {"type": "number"},
        "risk_factors":      {"type": "array", "items": {"type": "string"}},
        "recommendations":   {"type": "array", "items": {"type": "string"}},
        "reasoning":         {"type": "string"}
    },
    "required": ["gate_prediction","pass_rate_forecast","confidence","risk_factors","recommendations"]
}


# ── Helpers ────────────────────────────────────────────────────────────────

def print_header(title: str):
    print(f"\n{W}{'='*60}{E}")
    print(f"{W}  {title}{E}")
    print(f"{W}{'='*60}{E}")

def prob_bar(p: float, width: int = 20) -> str:
    color  = R if p >= 0.7 else Y if p >= 0.4 else G
    filled = int(p * width)
    return f"{color}{'█'*filled}{'░'*(width-filled)}{E} {int(p*100)}%"

def trend_icon(t: str) -> str:
    return {
        "degrading":  f"{R}↓ dégradation{E}",
        "stable":     f"{G}→ stable{E}",
        "improving":  f"{G}↑ amélioration{E}",
        "volatile":   f"{Y}~ volatile{E}",
    }.get(t, t)

def alert_color(level: str) -> str:
    return {
        "critical": R, "high": R, "medium": Y, "low": G, "none": G
    }.get(level, Y)


# ── Collecte des données historiques ──────────────────────────────────────

def _build_tc_profiles() -> dict:
    """
    Construit un profil statistique par TC depuis les épisodes.
    {tc_id: {runs, failures, categories, confidences, failure_rate, trend}}
    """
    episodes = mem.load_all_episodes()
    profiles: dict = {}

    for ep in episodes:
        for r in ep.get("results", []):
            tc = r.get("tc")
            if not tc:
                continue
            if tc not in profiles:
                profiles[tc] = {
                    "runs":        0,
                    "failures":    0,
                    "categories":  {},
                    "confidences": [],
                    "timeline":    [],  # (ts, is_failure)
                }
            p = profiles[tc]
            p["runs"] += 1
            cat = r.get("category", r.get("verdict", "unknown"))
            p["categories"][cat] = p["categories"].get(cat, 0) + 1
            is_fail = cat not in ("pass", "false_positive", "VALID", "GO")
            if is_fail:
                p["failures"] += 1
            if r.get("confidence") is not None:
                p["confidences"].append(r["confidence"])
            p["timeline"].append((ep["ts"][:10], is_fail))

    # Calculer failure_rate et trend
    for tc, p in profiles.items():
        p["failure_rate"]    = p["failures"] / p["runs"] if p["runs"] else 0
        p["avg_confidence"]  = (sum(p["confidences"]) / len(p["confidences"])
                                 if p["confidences"] else None)
        p["dominant_category"] = (max(p["categories"], key=p["categories"].get)
                                   if p["categories"] else "unknown")

        # Tendance : comparer première moitié vs deuxième moitié
        timeline = p["timeline"]
        if len(timeline) >= 4:
            mid   = len(timeline) // 2
            r1    = sum(1 for _, f in timeline[:mid] if f) / mid
            r2    = sum(1 for _, f in timeline[mid:] if f) / (len(timeline) - mid)
            delta = r2 - r1
            if delta > 0.2:   p["trend"] = "degrading"
            elif delta < -0.2: p["trend"] = "improving"
            elif abs(r1 - r2) > 0.3: p["trend"] = "volatile"
            else:              p["trend"] = "stable"
        else:
            p["trend"] = "stable"

    return profiles


def _load_current_failures() -> list:
    """Charge les échecs actuels depuis allure-results."""
    failures = []
    for f in glob.glob(os.path.join(RESULTS_DIR, "*-result.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
            if d.get("status") in ("failed", "broken"):
                tags = [lb["value"] for lb in d.get("labels",[]) if lb["name"]=="tag"]
                tc   = next((t for t in tags if re.match(r"tc-\d+",t)), None)
                if tc:
                    failures.append(tc)
        except Exception:
            pass
    return failures


def _load_kpi_history() -> list:
    """Charge l'historique des KPIs depuis les épisodes de release-advisor."""
    episodes = mem.load_all_episodes(agent="release-advisor-agent")
    kpis = []
    for ep in episodes:
        for r in ep.get("results", []):
            if "verdict" in r:
                kpis.append({
                    "ts":      ep["ts"][:10],
                    "verdict": r.get("verdict"),
                    "conf":    r.get("confidence", 0)
                })
    return kpis


# ── Commande : Prédiction des TCs à risque ────────────────────────────────

def cmd_predict() -> list:
    print_header("PREDICTIVE ANALYTICS — TCs à risque au prochain run")

    profiles      = _build_tc_profiles()
    current_fails = _load_current_failures()

    if not profiles:
        print(f"{Y}  Aucun historique. Lance : python agents/memory-agent.py seed{E}")
        return []

    # Filtrer les TCs avec au moins 2 runs et failure_rate > 0
    at_risk = {tc: p for tc, p in profiles.items()
               if p["runs"] >= 2 and p["failure_rate"] > 0}

    if not at_risk:
        print(f"{G}  Aucun TC à risque détecté dans l'historique.{E}")
        return []

    print(f"  {len(profiles)} TCs en historique | {len(at_risk)} à risque\n")

    # Construire le résumé pour le LLM
    summary_lines = []
    for tc, p in sorted(at_risk.items(), key=lambda x: -x[1]["failure_rate"]):
        summary_lines.append(
            f"  {tc}: {p['runs']} runs, {int(p['failure_rate']*100)}% échec, "
            f"trend={p['trend']}, dominant={p['dominant_category']}, "
            f"conf_moy={int(p['avg_confidence']*100) if p['avg_confidence'] else '?'}%"
        )

    current_str = f"TCs en échec dans le run actuel : {', '.join(current_fails) or 'aucun'}"

    print(f"{C}  Appel LLM CoT + Structured Output pour les prédictions...{E}", flush=True)

    cot_messages = [{
        "role": "user",
        "content": (
            f"Voici l'historique de défaillance des TCs :\n"
            + "\n".join(summary_lines) +
            f"\n\n{current_str}\n\n"
            f"Pour chaque TC, prédit :\n"
            f"- failure_probability (0.0-1.0) au prochain run\n"
            f"- trend : degrading / stable / improving / volatile\n"
            f"- predicted_category : ce qu'il sera probablement\n"
            f"- alert_level : critical/high/medium/low/none\n"
            f"Bases-toi sur la tendance et la cohérence des catégories passées."
        )
    }]

    result = llm.chat_structured(cot_messages, PREDICTION_SCHEMA)
    predictions = result.get("predictions", [])

    # Affichage
    print(f"\n  {W}{'TC':<12} {'Probabilité':>22} {'Trend':<20} {'Catégorie prédite':<18} {'Alerte'}{E}")
    print(f"  {'-'*85}")

    for pred in sorted(predictions, key=lambda x: -x.get("failure_probability",0)):
        tc   = pred.get("tc_id","?")
        prob = pred.get("failure_probability", 0)
        trend = trend_icon(pred.get("trend","stable"))
        cat  = pred.get("predicted_category","?")
        alert = pred.get("alert_level","none")
        ac   = alert_color(alert)

        print(f"  {C}{tc:<12}{E} [{prob_bar(prob, 15)}]  {trend:<20}  "
              f"{cat:<18}  {ac}{alert.upper()}{E}")
        if pred.get("reasoning"):
            print(f"  {' '*12}  {Y}{pred['reasoning'][:80]}{E}")

    # Alerte sur les critiques
    critiques = [p for p in predictions if p.get("alert_level") in ("critical","high")]
    if critiques:
        print(f"\n  {R}{W}⚠ {len(critiques)} TC(s) à risque élevé avant le prochain run :{E}")
        for p in critiques:
            print(f"  {R}→ {p['tc_id']} ({int(p.get('failure_probability',0)*100)}%) — {p.get('reasoning','')[:70]}{E}")

    return predictions


# ── Commande : Prédiction du Quality Gate ─────────────────────────────────

def cmd_gate():
    print_header("PRÉDICTION QUALITY GATE — Prochain run")

    profiles = _build_tc_profiles()
    kpi_history = _load_kpi_history()

    # Calculer la pass rate prédite
    if not profiles:
        print(f"{Y}  Pas d'historique disponible.{E}")
        return

    total_tcs  = len(profiles)
    high_risk  = sum(1 for p in profiles.values()
                     if p["failure_rate"] >= 0.5 and p["trend"] in ("degrading","volatile"))
    predicted_pass_rate = max(0, min(100, round((1 - high_risk/total_tcs) * 100, 1)))

    # Tendance historique des gates
    gate_history_str = ""
    if kpi_history:
        recent = kpi_history[-5:]
        gate_history_str = "Historique gates récents : " + " | ".join(
            [f"{r['ts']} {r['verdict']}" for r in recent]
        )

    print(f"{C}  Pass rate prédite (déterministe) : {predicted_pass_rate}%{E}")
    print(f"{C}  Appel LLM Structured Output...{E}", flush=True)

    messages = [{
        "role": "user",
        "content": (
            f"Prédit si le Quality Gate va passer au prochain run.\n\n"
            f"Profils TCs ({total_tcs} total) :\n"
            + "\n".join([
                f"  {tc}: failure_rate={int(p['failure_rate']*100)}%, trend={p['trend']}"
                for tc, p in list(profiles.items())[:10]
            ]) +
            f"\n\nTCs à haut risque : {high_risk}\n"
            f"Pass rate prédite déterministe : {predicted_pass_rate}%\n"
            f"{gate_history_str}\n\n"
            f"Quality Gate = PASSED si pass_rate ≥ 90% ET fail_rate ≤ 5%"
        )
    }]

    result = llm.chat_structured(messages, GATE_SCHEMA)

    gate      = result.get("gate_prediction", "UNCERTAIN")
    forecast  = result.get("pass_rate_forecast", predicted_pass_rate)
    conf      = result.get("confidence", 0.5)
    risks     = result.get("risk_factors", [])
    recs      = result.get("recommendations", [])

    gate_color = G if gate == "PASSED" else R if gate == "FAILED" else Y
    print(f"\n  {gate_color}{W}Quality Gate prédit : {gate}{E}")
    print(f"  Pass rate estimée  : {forecast:.1f}%")
    print(f"  Confiance          : {int(conf*100)}%")

    if risks:
        print(f"\n  {R}Facteurs de risque :{E}")
        for r in risks[:4]:
            print(f"    {R}→{E} {r}")
    if recs:
        print(f"\n  {G}Recommandations :{E}")
        for r in recs[:3]:
            print(f"    {G}✓{E} {r}")

    return result


# ── Commande : Prédiction des tests flaky ─────────────────────────────────

def cmd_flaky():
    print_header("PRÉDICTION FLAKY — Tests en voie de devenir instables")

    profiles = _build_tc_profiles()
    if not profiles:
        print(f"{Y}  Pas d'historique.{E}")
        return

    # Détection déterministe : flaky = catégorie oscillante + confidence basse
    flaky_candidates = []
    for tc, p in profiles.items():
        cats = p["categories"]
        nb_cats = len([c for c, n in cats.items() if n > 0])
        failure_rate = p["failure_rate"]
        avg_conf = p["avg_confidence"] or 1.0
        trend = p["trend"]

        # Critères flaky : plusieurs catégories + conf basse + volatil
        flaky_score = 0
        if nb_cats >= 2:      flaky_score += 0.3
        if 0.3 < failure_rate < 0.8: flaky_score += 0.3
        if avg_conf < 0.75:   flaky_score += 0.2
        if trend == "volatile": flaky_score += 0.2

        if flaky_score >= 0.4:
            flaky_candidates.append({
                "tc":          tc,
                "flaky_score": round(flaky_score, 2),
                "categories":  cats,
                "failure_rate": failure_rate,
                "trend":       trend,
                "avg_conf":    avg_conf,
            })

    flaky_candidates.sort(key=lambda x: -x["flaky_score"])

    if not flaky_candidates:
        print(f"{G}  Aucun candidat flaky détecté.{E}")
        return

    print(f"  {len(flaky_candidates)} candidat(s) flaky identifié(s)\n")
    print(f"  {W}{'TC':<12} {'Score flaky':>14} {'Failure rate':>13} {'Trend':<18} {'Catégories'}{E}")
    print(f"  {'-'*75}")

    for c in flaky_candidates:
        score_color = R if c["flaky_score"] >= 0.7 else Y
        cats_str = ", ".join([f"{cat}×{n}" for cat, n in c["categories"].items()])
        print(f"  {C}{c['tc']:<12}{E} "
              f"{score_color}[{'█'*int(c['flaky_score']*10)}{'░'*(10-int(c['flaky_score']*10))}] "
              f"{int(c['flaky_score']*100)}%{E}  "
              f"{int(c['failure_rate']*100):>11}%  "
              f"{trend_icon(c['trend']):<18}  {cats_str}")

    # Recommandation LLM
    print(f"\n{C}  Recommandation LLM (CoT)...{E}", flush=True)
    context = "\n".join([
        f"{c['tc']}: score={c['flaky_score']}, cats={c['categories']}, trend={c['trend']}"
        for c in flaky_candidates[:5]
    ])
    messages = [{"role": "user", "content":
        f"Ces TCs semblent devenir flaky :\n{context}\n\n"
        f"Pour chacun, recommande : quarantaine / surveillance / correction immédiate. "
        f"Justifie brièvement."
    }]
    advice = llm.chat_cot(messages)
    print()
    for line in advice.split("\n"):
        if line.strip().startswith("ÉTAPE") or "CONCLUSION" in line:
            print(f"  {Y}{line}{E}")
        elif line.strip():
            print(f"  {line}")

    return flaky_candidates


# ── Commande : Tendances KPI ───────────────────────────────────────────────

def cmd_trends():
    print_header("TENDANCES KPI — Projection sur les prochains runs")

    episodes = mem.load_all_episodes()
    if len(episodes) < 3:
        print(f"{Y}  Pas assez d'épisodes (minimum 3). Lance : memory-agent.py seed{E}")
        return

    # Calculer pass_rate par run depuis les résultats triage
    run_stats = []
    for ep in mem.load_all_episodes(agent="triage-agent"):
        results   = ep.get("results", [])
        total     = len(results)
        failures  = sum(1 for r in results
                        if r.get("category") not in ("false_positive","pass"))
        if total > 0:
            pass_rate = round((1 - failures/total) * 100, 1)
            run_stats.append({"ts": ep["ts"][:10], "pass_rate": pass_rate,
                               "total": total, "failures": failures})

    if len(run_stats) < 2:
        print(f"{Y}  Pas assez de runs triage-agent pour calculer les tendances.{E}")
        return

    # Affichage sparkline
    print(f"\n  {W}Pass Rate par run :{E}")
    max_rate = max(r["pass_rate"] for r in run_stats) or 100
    for r in run_stats:
        filled = int(r["pass_rate"] / 5)
        color  = G if r["pass_rate"] >= 90 else Y if r["pass_rate"] >= 75 else R
        bar    = f"{color}{'█'*filled}{'░'*(20-filled)}{E}"
        print(f"  {r['ts']}  [{bar}] {r['pass_rate']}%  "
              f"({r['total']-r['failures']}/{r['total']} OK)")

    # Projection linéaire simple
    rates = [r["pass_rate"] for r in run_stats]
    if len(rates) >= 2:
        delta_per_run = (rates[-1] - rates[0]) / (len(rates) - 1)
        projected     = [round(rates[-1] + delta_per_run * i, 1) for i in range(1, 4)]
        proj_color    = G if projected[-1] >= 90 else Y if projected[-1] >= 75 else R

        print(f"\n  {W}Projection (3 prochains runs) :{E}")
        for i, proj in enumerate(projected, 1):
            trend_c = G if proj >= 90 else Y if proj >= 75 else R
            print(f"  Run +{i}  →  {trend_c}{proj}%{E}")

        gate_risk = "RISQUE ÉLEVÉ" if projected[-1] < 85 else \
                    "À SURVEILLER" if projected[-1] < 90 else "OK"
        gate_c = R if "RISQUE" in gate_risk else Y if "SURVEILLER" in gate_risk else G
        print(f"\n  Quality Gate à +3 runs : {gate_c}{W}{gate_risk}{E}")


# ── Rapport HTML ───────────────────────────────────────────────────────────

def cmd_report():
    predictions  = cmd_predict()
    gate_result  = cmd_gate()
    flaky        = cmd_flaky()

    gate      = gate_result.get("gate_prediction","UNCERTAIN") if gate_result else "?"
    forecast  = gate_result.get("pass_rate_forecast", 0) if gate_result else 0
    gate_color = {"PASSED":"#27ae60","FAILED":"#e74c3c","UNCERTAIN":"#e67e22"}.get(gate,"#888")

    pred_rows = ""
    for p in (predictions or []):
        prob   = p.get("failure_probability",0)
        pct    = int(prob * 100)
        pcolor = "#e74c3c" if pct>=70 else "#e67e22" if pct>=40 else "#27ae60"
        ac     = {"critical":"#e74c3c","high":"#e67e22","medium":"#3498db",
                  "low":"#27ae60","none":"#888"}.get(p.get("alert_level","none"),"#888")
        bar_w  = pct
        pred_rows += f"""
        <tr>
          <td style="font-family:monospace;font-weight:bold">{p.get('tc_id','?')}</td>
          <td>
            <div style="background:#eee;border-radius:4px;height:14px;width:150px;display:inline-block">
              <div style="background:{pcolor};width:{bar_w}%;height:100%;border-radius:4px"></div>
            </div> {pct}%
          </td>
          <td>{p.get('trend','?')}</td>
          <td>{p.get('predicted_category','?')}</td>
          <td><span style="background:{ac};color:#fff;padding:2px 8px;border-radius:3px;font-size:11px">{p.get('alert_level','?').upper()}</span></td>
          <td style="font-size:11px;color:#555">{p.get('reasoning','')[:70]}</td>
        </tr>"""

    flaky_rows = ""
    for c in (flaky or []):
        score = c.get("flaky_score",0)
        sc    = "#e74c3c" if score>=0.7 else "#e67e22" if score>=0.4 else "#27ae60"
        flaky_rows += f"""
        <tr>
          <td style="font-family:monospace">{c['tc']}</td>
          <td style="color:{sc};font-weight:bold">{int(score*100)}%</td>
          <td>{int(c['failure_rate']*100)}%</td>
          <td>{c['trend']}</td>
          <td style="font-size:11px">{', '.join([f"{k}×{v}" for k,v in c['categories'].items()])}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Predictive Agent — Analytics</title>
<style>
  body{{font-family:Arial,sans-serif;background:#f0f2f5;color:#333;margin:0;padding:20px}}
  h1{{color:#2c3e50}} h2{{color:#34495e;margin-top:30px}}
  .banner{{background:{gate_color};color:#fff;padding:20px;border-radius:10px;
           text-align:center;font-size:22px;font-weight:bold;margin:15px 0}}
  .stat{{display:inline-block;background:#fff;border-radius:10px;padding:15px 25px;
         margin:8px;box-shadow:0 2px 8px rgba(0,0,0,.1);text-align:center}}
  .stat-val{{font-size:28px;font-weight:bold}} .stat-lbl{{font-size:12px;color:#888}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;
         overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1);margin-top:12px}}
  th{{background:#2c3e50;color:#fff;padding:10px 12px;text-align:left;font-size:12px}}
  td{{padding:9px 12px;border-bottom:1px solid #ecf0f1;vertical-align:middle}}
  tr:hover{{background:#f8f9fa}}
</style>
</head>
<body>
<h1>Predictive Agent — Analytics QA</h1>
<p style="color:#666">Prédictions basées sur l'historique épisodique + LLM CoT + Structured Output</p>

<div class="banner">Quality Gate prédit : {gate} | Pass Rate estimée : {forecast:.1f}%</div>

<div>
  <div class="stat"><div class="stat-val" style="color:#e74c3c">{len([p for p in (predictions or []) if p.get('alert_level') in ('critical','high')])}</div><div class="stat-lbl">TCs à risque élevé</div></div>
  <div class="stat"><div class="stat-val" style="color:#e67e22">{len(flaky or [])}</div><div class="stat-lbl">Candidats flaky</div></div>
  <div class="stat"><div class="stat-val" style="color:{gate_color}">{forecast:.0f}%</div><div class="stat-lbl">Pass Rate prédite</div></div>
</div>

<h2>Prédictions par TC</h2>
<table>
  <tr><th>TC</th><th>Probabilité d'échec</th><th>Tendance</th><th>Catégorie prédite</th><th>Alerte</th><th>Raisonnement</th></tr>
  {pred_rows or '<tr><td colspan="6" style="text-align:center;color:#888">Aucune prédiction</td></tr>'}
</table>

<h2>Candidats Flaky</h2>
<table>
  <tr><th>TC</th><th>Score flaky</th><th>Failure rate hist.</th><th>Tendance</th><th>Catégories</th></tr>
  {flaky_rows or '<tr><td colspan="5" style="text-align:center;color:#888">Aucun candidat flaky</td></tr>'}
</table>

<p style="color:#999;font-size:12px;margin-top:30px">
  Généré par Predictive Agent | Sources : memory/episodes.jsonl + allure-results/
</p>
</body>
</html>"""

    out = os.path.join(DOCS_DIR, "predictive-report.html")
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n{G}  Rapport HTML : docs/predictive-report.html{E}")


def print_help():
    print(f"""
{W}PREDICTIVE AGENT — Analytics QA{E}

  python agents/predictive-agent.py predict   TCs à risque au prochain run
  python agents/predictive-agent.py gate       Quality Gate prédit
  python agents/predictive-agent.py flaky      Candidats flaky futurs
  python agents/predictive-agent.py trends     Projection KPI sur 3 runs
  python agents/predictive-agent.py report     Rapport HTML complet

{W}Prérequis :{E}
  Des épisodes en mémoire : python agents/memory-agent.py seed

{W}Méthode :{E}
  Analyse déterministe des tendances (failure_rate, trend, volatilité)
  + LLM CoT + Structured Output pour les prédictions complexes
""")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "predict":  cmd_predict()
    elif cmd == "gate":   cmd_gate()
    elif cmd == "flaky":  cmd_flaky()
    elif cmd == "trends": cmd_trends()
    elif cmd == "report": cmd_report()
    else:                 print_help()
