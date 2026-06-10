# ============================================================
# Coverage Agent — Analyse des lacunes de couverture de tests
# ============================================================
# Lit les features/*.feature existantes, mappe les scénarios
# aux endpoints, identifie les types de test manquants, et
# propose des nouveaux TCs via Chain of Thought.
#
# Usage:
#   python agents/coverage-agent.py analyse    → analyse complète
#   python agents/coverage-agent.py gaps       → lacunes uniquement
#   python agents/coverage-agent.py suggest    → suggestions de TCs
#   python agents/coverage-agent.py report     → rapport HTML
# ============================================================

import sys, os, json, glob, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm

FRAMEWORK    = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FEATURES_DIR = os.path.join(FRAMEWORK, "features")
DOCS_DIR     = os.path.join(FRAMEWORK, "docs")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

# Types de test attendus par endpoint
COVERAGE_TYPES = ["positif", "negatif", "auth", "limite", "securite", "performance"]

# Endpoints connus du framework restful-booker
ENDPOINTS = {
    "US-001": {"path": "POST /auth",            "desc": "Authentification"},
    "US-002": {"path": "GET /booking",           "desc": "Liste des réservations"},
    "US-003": {"path": "POST /booking",          "desc": "Créer une réservation"},
    "US-004": {"path": "GET /booking/{id}",      "desc": "Détail réservation"},
    "US-005": {"path": "PUT /booking/{id}",      "desc": "Modifier réservation (complète)"},
    "US-006": {"path": "PATCH /booking/{id}",    "desc": "Modifier réservation (partielle)"},
    "US-007": {"path": "DELETE /booking/{id}",   "desc": "Supprimer réservation"},
    "US-008": {"path": "GET /ping",              "desc": "Healthcheck"},
}


# ── Helpers ────────────────────────────────────────────────────────────────

def print_header(title: str):
    print(f"\n{W}{'='*58}{E}")
    print(f"{W}  {title}{E}")
    print(f"{W}{'='*58}{E}")

def coverage_bar(pct: float) -> str:
    filled = int(pct / 5)
    color  = G if pct >= 80 else Y if pct >= 60 else R
    return f"{color}{'█' * filled}{'░' * (20 - filled)}{E} {int(pct)}%"

def load_features() -> dict:
    """Charge tous les .feature et retourne un dict {filename: content}."""
    result = {}
    for fpath in sorted(glob.glob(os.path.join(FEATURES_DIR, "*.feature"))):
        result[os.path.basename(fpath)] = open(fpath, encoding="utf-8").read()
    return result


# ── Analyse de couverture ──────────────────────────────────────────────────

def analyse_coverage() -> dict:
    """
    Mappe chaque endpoint à ses scénarios existants et calcule
    un score de couverture par type de test.
    Retourne : {endpoint_id: {scenarios: [...], types_covered: [...], score: float}}
    """
    features = load_features()
    if not features:
        print(f"{R}  Aucun fichier .feature dans features/{E}")
        return {}

    # Construire l'index endpoint → scénarios
    coverage = {us: {"scenarios": [], "types_covered": set(), "score": 0.0}
                for us in ENDPOINTS}

    # Pour chaque feature, extraire les scénarios et leurs tags
    for fname, content in features.items():
        # Découper en blocs scénario
        blocks = re.split(r"\n(?=\s*@|\s*Scenario:)", content)
        current_tags = []
        for block in blocks:
            tags_in_block = re.findall(r"@(\S+)", block)
            scenario_match = re.search(r"Scenario:\s*(.+)", block)
            if not scenario_match:
                current_tags = tags_in_block
                continue

            all_tags = current_tags + tags_in_block
            scenario_name = scenario_match.group(1).strip()

            # Trouver l'US associée
            us_tags = [t for t in all_tags if re.match(r"US-\d+", t, re.IGNORECASE)]
            tc_tags = [t for t in all_tags if re.match(r"TC-\d+", t, re.IGNORECASE)]

            for us in us_tags:
                us_key = us.upper()
                if us_key in coverage:
                    coverage[us_key]["scenarios"].append({
                        "name": scenario_name,
                        "tags": all_tags,
                        "tc":   tc_tags[0] if tc_tags else None,
                        "file": fname
                    })
                    # Types couverts
                    for ct in COVERAGE_TYPES:
                        if any(ct.lower() in t.lower() for t in all_tags):
                            coverage[us_key]["types_covered"].add(ct)

            current_tags = []

    # Calculer le score
    for us, data in coverage.items():
        nb_types = len(data["types_covered"])
        data["score"] = (nb_types / len(COVERAGE_TYPES)) * 100
        data["types_covered"] = sorted(data["types_covered"])

    return coverage


# ── Affichage de la couverture ─────────────────────────────────────────────

def print_coverage(coverage: dict):
    print_header("COUVERTURE DE TESTS PAR ENDPOINT")

    total_score = 0
    missing_count = 0

    for us, data in coverage.items():
        ep = ENDPOINTS[us]
        score = data["score"]
        total_score += score
        covered   = data["types_covered"]
        missing   = [t for t in COVERAGE_TYPES if t not in covered]
        nb_scenarios = len(data["scenarios"])
        missing_count += len(missing)

        color = G if score >= 80 else Y if score >= 50 else R
        print(f"\n  {W}{us}{E} — {ep['path']}")
        print(f"  {ep['desc']} | {nb_scenarios} scénario(s)")
        print(f"  Couverture : [{coverage_bar(score)}]")

        if covered:
            print(f"  {G}✓ Couverts  :{E} {', '.join(covered)}")
        if missing:
            print(f"  {R}✗ Manquants :{E} {', '.join(missing)}")

    avg = total_score / len(coverage) if coverage else 0
    print(f"\n  {W}Couverture moyenne : [{coverage_bar(avg)}]{E}")
    print(f"  Types de test manquants (total) : {R if missing_count > 5 else Y}{missing_count}{E}")

    return avg, missing_count


# ── Identification des lacunes ─────────────────────────────────────────────

def find_gaps(coverage: dict) -> list:
    """Retourne la liste des lacunes critiques."""
    gaps = []
    for us, data in coverage.items():
        ep = ENDPOINTS[us]
        missing = [t for t in COVERAGE_TYPES if t not in data["types_covered"]]
        if not missing:
            continue

        # Priorité : negatif et auth sont critiques
        critical = [t for t in missing if t in ("negatif", "auth", "securite")]
        normal   = [t for t in missing if t not in critical]

        gaps.append({
            "endpoint":  us,
            "path":      ep["path"],
            "desc":      ep["desc"],
            "missing":   missing,
            "critical":  critical,
            "normal":    normal,
            "score":     data["score"],
            "scenarios": data["scenarios"]
        })

    # Trier par score croissant (le moins couvert en premier)
    return sorted(gaps, key=lambda x: x["score"])


def print_gaps(gaps: list):
    print_header("LACUNES CRITIQUES IDENTIFIÉES")

    if not gaps:
        print(f"{G}  Aucune lacune — couverture complète !{E}")
        return

    for gap in gaps:
        prio = f"{R}CRITIQUE{E}" if gap["critical"] else f"{Y}NORMALE {E}"
        print(f"\n  {prio}  {gap['endpoint']} — {gap['path']}")
        if gap["critical"]:
            print(f"  {R}→ Types critiques manquants : {', '.join(gap['critical'])}{E}")
        if gap["normal"]:
            print(f"  {Y}→ Types normaux manquants   : {', '.join(gap['normal'])}{E}")


# ── Suggestions LLM ───────────────────────────────────────────────────────

def suggest_tcs(gaps: list, features: dict) -> list:
    """Utilise Chain of Thought pour proposer des nouveaux TCs."""
    print_header("SUGGESTIONS DE NOUVEAUX CAS DE TEST (LLM + CoT)")

    if not gaps:
        print(f"{G}  Aucune lacune à couvrir.{E}")
        return []

    all_suggestions = []

    # Numéro TC courant (max existant + 1)
    all_tcs = []
    for content in features.values():
        all_tcs.extend([int(m) for m in re.findall(r"TC-(\d+)", content)])
    next_tc = max(all_tcs, default=0) + 1

    for gap in gaps[:5]:  # max 5 endpoints pour économiser les tokens
        ep = gap["endpoint"]
        path = gap["path"]
        missing = gap["missing"]
        existing = [s["name"] for s in gap["scenarios"][:3]]

        print(f"\n{C}  Suggestions pour {ep} — {path}...{E}")

        messages = [{
            "role": "user",
            "content": (
                f"Endpoint : {path} ({gap['desc']})\n"
                f"Tests existants : {existing}\n"
                f"Types de test manquants : {', '.join(missing)}\n\n"
                f"Propose {len(missing)} nouveaux scénarios Gherkin BDD "
                f"(un par type manquant) au format :\n"
                f"  @TC-NNN @US-XXX @type\n"
                f"  Scenario: Description claire\n"
                f"    Given ...\n"
                f"    When ...\n"
                f"    Then ...\n\n"
                f"Commence la numérotation des TCs à TC-{next_tc:03d}.\n"
                f"Sois précis, testable, et non trivial."
            )
        }]

        suggestion = llm.chat_cot(messages)
        all_suggestions.append({
            "endpoint": ep,
            "path":     path,
            "missing":  missing,
            "text":     suggestion
        })

        # Afficher les suggestions
        lines = suggestion.split("\n")
        for line in lines:
            if line.strip().startswith("@") or "Scenario:" in line:
                print(f"  {G}{line}{E}")
            elif re.match(r"\s+(Given|When|Then|And)", line):
                print(f"  {C}{line}{E}")
            elif line.strip().startswith("ÉTAPE") or line.strip().startswith("CONCLUSION"):
                print(f"  {Y}{line}{E}")
            elif line.strip():
                print(f"  {line}")

        next_tc += len(missing)

    return all_suggestions


# ── Rapport HTML ───────────────────────────────────────────────────────────

def generate_html_report(coverage: dict, gaps: list, suggestions: list):
    avg = sum(d["score"] for d in coverage.values()) / len(coverage) if coverage else 0
    gate = "PASSED" if avg >= 80 else "FAILED"
    gate_color = "#27ae60" if gate == "PASSED" else "#e74c3c"

    rows = ""
    for us, data in coverage.items():
        ep = ENDPOINTS[us]
        score = data["score"]
        covered = data["types_covered"]
        missing = [t for t in COVERAGE_TYPES if t not in covered]
        nb = len(data["scenarios"])
        color = "#27ae60" if score >= 80 else "#e67e22" if score >= 50 else "#e74c3c"
        covered_html = " ".join([f'<span style="background:#27ae60;color:#fff;padding:2px 6px;border-radius:3px;font-size:12px">{t}</span>' for t in covered])
        missing_html = " ".join([f'<span style="background:#e74c3c;color:#fff;padding:2px 6px;border-radius:3px;font-size:12px">{t}</span>' for t in missing])
        rows += f"""
        <tr>
          <td><b>{us}</b></td>
          <td style="font-family:monospace">{ep['path']}</td>
          <td>{ep['desc']}</td>
          <td style="text-align:center">{nb}</td>
          <td style="text-align:center;color:{color};font-weight:bold">{int(score)}%</td>
          <td>{covered_html or '—'}</td>
          <td>{missing_html or '<span style="color:#27ae60">Complet</span>'}</td>
        </tr>"""

    sugg_html = ""
    for s in suggestions:
        sugg_html += f"""
        <div style="background:#1e1e2e;padding:15px;border-radius:8px;margin:10px 0">
          <div style="color:#89b4fa;font-weight:bold">{s['endpoint']} — {s['path']}</div>
          <div style="color:#a6e3a1;font-size:13px">Types manquants : {', '.join(s['missing'])}</div>
          <pre style="color:#cdd6f4;font-size:13px;white-space:pre-wrap;margin-top:10px">{s['text']}</pre>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Coverage Agent — Rapport</title>
<style>
  body{{font-family:Arial,sans-serif;background:#f5f5f5;color:#333;margin:0;padding:20px}}
  h1{{color:#2c3e50}} h2{{color:#34495e}}
  .banner{{background:{gate_color};color:#fff;padding:20px;border-radius:8px;text-align:center;font-size:24px;font-weight:bold;margin-bottom:20px}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1)}}
  th{{background:#2c3e50;color:#fff;padding:10px;text-align:left}}
  td{{padding:10px;border-bottom:1px solid #ecf0f1}}
  tr:hover{{background:#f8f9fa}}
  .score-high{{color:#27ae60;font-weight:bold}}
  .score-mid{{color:#e67e22;font-weight:bold}}
  .score-low{{color:#e74c3c;font-weight:bold}}
</style>
</head>
<body>
<h1>Coverage Agent — Rapport de couverture</h1>
<div class="banner">Quality Gate Coverage : {gate} | Couverture moyenne : {avg:.0f}%</div>

<h2>Couverture par endpoint</h2>
<table>
  <tr>
    <th>Endpoint</th><th>Path</th><th>Description</th>
    <th>Scénarios</th><th>Score</th><th>Types couverts</th><th>Types manquants</th>
  </tr>
  {rows}
</table>

<h2>Suggestions LLM (Chain of Thought)</h2>
{sugg_html or '<p style="color:#27ae60">Aucune suggestion — couverture complète.</p>'}

<p style="color:#999;font-size:12px;margin-top:30px">
  Généré par Coverage Agent — framework api-pytest-framework
</p>
</body>
</html>"""

    out = os.path.join(DOCS_DIR, "coverage-report.html")
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n{G}  Rapport HTML généré : docs/coverage-report.html{E}")
    return out


# ── Commandes principales ──────────────────────────────────────────────────

def cmd_analyse():
    features = load_features()
    if not features:
        print(f"{R}Aucun fichier .feature trouvé dans {FEATURES_DIR}{E}")
        return
    print(f"{C}  {len(features)} fichier(s) feature chargé(s){E}")
    coverage = analyse_coverage()
    avg, missing = print_coverage(coverage)
    return coverage


def cmd_gaps():
    coverage = analyse_coverage()
    gaps = find_gaps(coverage)
    print_gaps(gaps)
    return gaps


def cmd_suggest():
    features = load_features()
    coverage = analyse_coverage()
    gaps     = find_gaps(coverage)
    print_coverage(coverage)
    suggestions = suggest_tcs(gaps, features)
    return suggestions


def cmd_report():
    features    = load_features()
    coverage    = analyse_coverage()
    gaps        = find_gaps(coverage)
    suggestions = suggest_tcs(gaps, features)
    generate_html_report(coverage, gaps, suggestions)
    return coverage, gaps, suggestions


def print_help():
    print(f"""
{W}COVERAGE AGENT — Analyse des lacunes de couverture{E}

  python agents/coverage-agent.py analyse    Mappe les scénarios aux endpoints
  python agents/coverage-agent.py gaps       Identifie les lacunes critiques
  python agents/coverage-agent.py suggest    Propose de nouveaux TCs via LLM CoT
  python agents/coverage-agent.py report     Rapport complet + HTML

  Endpoints analysés : US-001 → US-008 (restful-booker)
  Types de test      : positif, negatif, auth, limite, securite, performance
  Score Quality Gate : couverture moyenne ≥ 80% = PASSED
""")


# ── Main ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "analyse":
        cmd_analyse()
    elif cmd == "gaps":
        cmd_gaps()
    elif cmd == "suggest":
        cmd_suggest()
    elif cmd == "report":
        cmd_report()
    else:
        print_help()
