# ============================================================
# Triage Agent — Classification des échecs avec Confidence Scoring
# ============================================================
# Lit les résultats Allure, classe chaque échec en :
#   real_bug / flaky / env_issue / false_positive
# avec un score de confiance 0.0→1.0.
# Si confidence < 0.7 → signale une révision humaine nécessaire.
#
# Usage:
#   python agents/triage-agent.py triage      → classe tous les échecs
#   python agents/triage-agent.py review      → affiche uniquement les cas incertains
#   python agents/triage-agent.py report      → rapport HTML complet
#   python agents/triage-agent.py summary     → résumé chiffré
# ============================================================

import sys, os, json, glob, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm

FRAMEWORK   = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS_DIR = os.path.join(FRAMEWORK, "allure-results")
DOCS_DIR    = os.path.join(FRAMEWORK, "docs")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

CONFIDENCE_THRESHOLD = 0.70  # en dessous → révision humaine

# Couleurs par catégorie
CATEGORY_COLORS = {
    "real_bug":      R,
    "flaky":         Y,
    "env_issue":     C,
    "false_positive": G,
    "unknown":       Y,
}

CATEGORY_LABELS = {
    "real_bug":       "VRAI BUG",
    "flaky":          "FLAKY   ",
    "env_issue":      "ENV     ",
    "false_positive": "FAUX POS",
    "unknown":        "INCONNU ",
}


# ── Chargement des résultats Allure ───────────────────────────────────────

def load_failures() -> list:
    failures = []
    for f in glob.glob(os.path.join(RESULTS_DIR, "*-result.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
            if d.get("status") not in ("failed", "broken"):
                continue

            labels = {lb["name"]: lb["value"] for lb in d.get("labels", [])}
            tags   = [lb["value"] for lb in d.get("labels", []) if lb["name"] == "tag"]
            tc     = next((t for t in tags if re.match(r"tc-\d+", t)), None)
            us     = next((t for t in tags if re.match(r"us-\d+", t)), None)
            detail = d.get("statusDetails") or {}

            failures.append({
                "name":    d.get("name", "?"),
                "status":  d.get("status"),
                "tc":      tc,
                "us":      us,
                "suite":   labels.get("suite", "?"),
                "message": detail.get("message", "")[:400],
                "trace":   detail.get("trace",   "")[:300],
                "tags":    tags,
            })
        except Exception:
            pass
    return failures


# ── Classification via Confidence Scoring ─────────────────────────────────

def classify_failure(failure: dict) -> dict:
    """
    Utilise chat_confident() pour classifier un échec.
    Retourne : {category, confidence, reasoning, needs_human_review}
    """
    messages = [{
        "role": "user",
        "content": (
            f"Analyse cet échec de test API et classe-le dans UNE seule catégorie :\n\n"
            f"Test     : {failure['name']}\n"
            f"TC       : {failure['tc'] or '?'} | US : {failure['us'] or '?'}\n"
            f"Statut   : {failure['status']}\n"
            f"Message  : {failure['message'] or 'aucun message'}\n"
            f"Trace    : {failure['trace'][:200] or 'aucune trace'}\n\n"
            f"Catégories possibles :\n"
            f"  real_bug       → Bug dans le code applicatif (assertion échouée, mauvais status HTTP)\n"
            f"  flaky          → Test instable, passe parfois (timeout, race condition, données variables)\n"
            f"  env_issue      → Problème d'infrastructure (connexion, service indisponible, config)\n"
            f"  false_positive → Le test lui-même est incorrect (mauvaise assertion, données de test erronées)\n\n"
            f"Ta réponse doit être la catégorie choisie, avec un score de confiance entre 0.0 et 1.0\n"
            f"et le raisonnement qui justifie ton choix."
        )
    }]

    raw = llm.chat_confident(messages)

    # Extraire la catégorie depuis la réponse texte
    response_text = str(raw.get("response", "")).lower()
    category = "unknown"
    for cat in ("real_bug", "flaky", "env_issue", "false_positive"):
        if cat in response_text:
            category = cat
            break

    return {
        **failure,
        "category":          category,
        "confidence":        float(raw.get("confidence", 0.5)),
        "reasoning":         raw.get("reasoning", ""),
        "needs_human_review": raw.get("needs_human_review", True),
    }


# ── Affichage ──────────────────────────────────────────────────────────────

def confidence_bar(score: float) -> str:
    filled = int(score * 20)
    color  = G if score >= 0.8 else Y if score >= 0.6 else R
    return f"{color}{'█' * filled}{'░' * (20 - filled)}{E} {int(score * 100)}%"

def print_result(r: dict, show_reasoning: bool = True):
    cat   = r["category"]
    color = CATEGORY_COLORS.get(cat, Y)
    label = CATEGORY_LABELS.get(cat, cat)
    flag  = f" {R}⚠ RÉVISION HUMAINE{E}" if r["needs_human_review"] else ""

    print(f"\n  {color}{W}[{label}]{E}  {r['tc'] or '?':>7}  {r['name'][:55]}{flag}")
    print(f"  Confiance : [{confidence_bar(r['confidence'])}]")
    if r["message"]:
        print(f"  Erreur    : {Y}{r['message'][:90]}{E}")
    if show_reasoning and r.get("reasoning"):
        print(f"  Raison    : {r['reasoning'][:120]}")


# ── Commandes ──────────────────────────────────────────────────────────────

def cmd_triage() -> list:
    print(f"\n{W}TRIAGE AGENT — Confidence Scoring{E}")
    print(f"{Y}Seuil révision humaine : confidence < {int(CONFIDENCE_THRESHOLD*100)}%{E}\n")

    failures = load_failures()
    if not failures:
        print(f"{G}  Aucun échec dans allure-results — rien à trier.{E}")
        return []

    print(f"  {len(failures)} échec(s) détecté(s)\n")
    results = []

    for i, f in enumerate(failures, 1):
        print(f"  {C}[{i}/{len(failures)}]{E} Classification de {f['tc'] or f['name'][:40]}...", end=" ", flush=True)
        r = classify_failure(f)
        results.append(r)
        cat   = r["category"]
        color = CATEGORY_COLORS.get(cat, Y)
        flag  = f" {R}⚠{E}" if r["needs_human_review"] else f" {G}✓{E}"
        print(f"{color}{CATEGORY_LABELS[cat]}{E} {int(r['confidence']*100)}%{flag}")

    _print_triage_summary(results)
    return results


def cmd_review(results: list = None) -> list:
    if results is None:
        results = cmd_triage()

    uncertain = [r for r in results if r["needs_human_review"]]
    print(f"\n{W}{'='*58}{E}")
    print(f"{W}  CAS NÉCESSITANT RÉVISION HUMAINE ({len(uncertain)}){E}")
    print(f"{W}{'='*58}{E}")

    if not uncertain:
        print(f"{G}  Tous les cas ont une confiance ≥ {int(CONFIDENCE_THRESHOLD*100)}% — aucune révision requise.{E}")
        return []

    for r in uncertain:
        print_result(r, show_reasoning=True)

    return uncertain


def cmd_summary(results: list = None):
    if results is None:
        results = cmd_triage()
        if not results:
            return

    print(f"\n{W}{'='*58}{E}")
    print(f"{W}  RÉSUMÉ TRIAGE{E}")
    print(f"{W}{'='*58}{E}\n")

    by_cat = {}
    for r in results:
        by_cat.setdefault(r["category"], []).append(r)

    print(f"  {'Catégorie':<20} {'Nb':>4} {'Conf. moy.':>12} {'Révision':>10}")
    print(f"  {'-'*50}")

    total_review = 0
    for cat in ("real_bug", "flaky", "env_issue", "false_positive", "unknown"):
        items = by_cat.get(cat, [])
        if not items:
            continue
        avg_conf = sum(r["confidence"] for r in items) / len(items)
        nb_review = sum(1 for r in items if r["needs_human_review"])
        total_review += nb_review
        color = CATEGORY_COLORS.get(cat, Y)
        label = CATEGORY_LABELS.get(cat, cat)
        print(f"  {color}{label:<20}{E} {len(items):>4} {int(avg_conf*100):>11}% {nb_review:>10}")

    avg_global = sum(r["confidence"] for r in results) / len(results) if results else 0
    print(f"\n  Confiance moyenne globale : {int(avg_global*100)}%")
    print(f"  Cas nécessitant révision  : {R if total_review else G}{total_review}/{len(results)}{E}")


# ── Rapport HTML ───────────────────────────────────────────────────────────

def cmd_report(results: list = None):
    if results is None:
        results = cmd_triage()
        if not results:
            return

    by_cat = {}
    for r in results:
        by_cat.setdefault(r["category"], []).append(r)

    CAT_COLORS_HTML = {
        "real_bug":       "#e74c3c",
        "flaky":          "#e67e22",
        "env_issue":      "#3498db",
        "false_positive": "#27ae60",
        "unknown":        "#95a5a6",
    }

    rows = ""
    for r in sorted(results, key=lambda x: x["confidence"]):
        cat   = r["category"]
        color = CAT_COLORS_HTML.get(cat, "#95a5a6")
        pct   = int(r["confidence"] * 100)
        bar   = f'<div style="background:#eee;border-radius:4px;height:14px;width:120px;display:inline-block"><div style="background:{color};width:{pct}%;height:100%;border-radius:4px"></div></div>'
        flag  = '<span style="background:#e74c3c;color:#fff;padding:1px 6px;border-radius:3px;font-size:11px">⚠ RÉVISION</span>' if r["needs_human_review"] else ''
        rows += f"""
        <tr>
          <td style="font-family:monospace;font-size:12px">{r['tc'] or '—'}</td>
          <td style="font-size:12px">{r['name'][:60]}</td>
          <td><span style="background:{color};color:#fff;padding:2px 8px;border-radius:3px;font-size:12px">{CATEGORY_LABELS.get(cat, cat).strip()}</span></td>
          <td>{bar} {pct}%</td>
          <td style="font-size:11px;color:#666">{r.get('reasoning','')[:80]}</td>
          <td>{flag}</td>
        </tr>"""

    nb_review = sum(1 for r in results if r["needs_human_review"])
    avg_conf  = int(sum(r["confidence"] for r in results) / len(results) * 100) if results else 0

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Triage Agent — Rapport de confiance</title>
<style>
  body{{font-family:Arial,sans-serif;background:#f5f5f5;color:#333;margin:0;padding:20px}}
  h1{{color:#2c3e50}} h2{{color:#34495e;margin-top:30px}}
  .stat{{display:inline-block;background:#fff;border-radius:8px;padding:15px 25px;margin:8px;box-shadow:0 2px 6px rgba(0,0,0,.1);text-align:center}}
  .stat-val{{font-size:28px;font-weight:bold}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1);margin-top:15px}}
  th{{background:#2c3e50;color:#fff;padding:10px;text-align:left;font-size:13px}}
  td{{padding:9px 10px;border-bottom:1px solid #ecf0f1;vertical-align:middle}}
  tr:hover{{background:#f8f9fa}}
  .legend{{display:flex;gap:12px;flex-wrap:wrap;margin:15px 0}}
  .leg{{padding:4px 12px;border-radius:4px;color:#fff;font-size:13px}}
</style>
</head>
<body>
<h1>Triage Agent — Confidence Scoring</h1>

<div>
  <div class="stat"><div class="stat-val" style="color:#e74c3c">{len(results)}</div>Échecs analysés</div>
  <div class="stat"><div class="stat-val" style="color:#e67e22">{avg_conf}%</div>Confiance moyenne</div>
  <div class="stat"><div class="stat-val" style="color:{'#e74c3c' if nb_review else '#27ae60'}">{nb_review}</div>Révisions humaines</div>
  <div class="stat"><div class="stat-val" style="color:#e74c3c">{len(by_cat.get('real_bug',[]))}</div>Vrais bugs</div>
  <div class="stat"><div class="stat-val" style="color:#e67e22">{len(by_cat.get('flaky',[]))}</div>Flaky</div>
</div>

<div class="legend">
  <span class="leg" style="background:#e74c3c">VRAI BUG — bug dans le code</span>
  <span class="leg" style="background:#e67e22">FLAKY — instable / race condition</span>
  <span class="leg" style="background:#3498db">ENV — infrastructure / réseau</span>
  <span class="leg" style="background:#27ae60">FAUX POSITIF — test incorrect</span>
</div>

<h2>Détail par test ({len(results)} cas)</h2>
<table>
  <tr><th>TC</th><th>Nom du test</th><th>Catégorie</th><th>Confiance</th><th>Raisonnement</th><th>Action</th></tr>
  {rows}
</table>

<p style="color:#999;font-size:12px;margin-top:30px">
  Généré par Triage Agent — Confidence Scoring (seuil révision : {int(CONFIDENCE_THRESHOLD*100)}%)
</p>
</body>
</html>"""

    out = os.path.join(DOCS_DIR, "triage-report.html")
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n{G}  Rapport HTML : docs/triage-report.html{E}")


def _print_triage_summary(results: list):
    by_cat = {}
    for r in results:
        by_cat.setdefault(r["category"], []).append(r)

    nb_review = sum(1 for r in results if r["needs_human_review"])
    print(f"\n  {W}Résultat :{E} ", end="")
    for cat, items in sorted(by_cat.items()):
        color = CATEGORY_COLORS.get(cat, Y)
        print(f"{color}{CATEGORY_LABELS.get(cat,'?').strip()}×{len(items)}{E}  ", end="")
    print(f"\n  Révisions humaines requises : {R if nb_review else G}{nb_review}/{len(results)}{E}")


def print_help():
    print(f"""
{W}TRIAGE AGENT — Confidence Scoring{E}

  python agents/triage-agent.py triage    Classe tous les échecs Allure
  python agents/triage-agent.py review    Affiche les cas incertains (confidence < {int(CONFIDENCE_THRESHOLD*100)}%)
  python agents/triage-agent.py summary   Résumé chiffré par catégorie
  python agents/triage-agent.py report    Rapport HTML complet

{W}Catégories :{E}
  real_bug       Bug dans le code (assertion, mauvais status HTTP)
  flaky          Test instable, race condition, timeout
  env_issue      Infrastructure, réseau, service indisponible
  false_positive Test incorrect, mauvaise assertion

{W}Confidence Scoring :{E}
  ≥ 0.80  Haute confiance  — décision automatique fiable
  0.70–0.80  Confiance correcte — acceptable
  < 0.70  Faible confiance  — révision humaine requise ⚠
""")


# ── Main ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "triage":
        cmd_triage()
    elif cmd == "review":
        cmd_review()
    elif cmd == "summary":
        cmd_summary()
    elif cmd == "report":
        results = cmd_triage()
        cmd_report(results)
    else:
        print_help()
