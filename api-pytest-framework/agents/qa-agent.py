# ============================================
# QA Agent — Analyse la qualité de la suite de tests API
# ============================================
# Analyse la couverture, la cohérence et la qualité des tests pytest,
# produit un rapport dans docs/qa-report.md.
#
# Usage:
#   python agents/qa-agent.py
#   python agents/qa-agent.py --dry-run
# ============================================

import sys
import os
import glob
sys.path.insert(0, os.path.dirname(__file__))

import llm

DRY_RUN   = "--dry-run" in sys.argv
TESTS_DIR = os.path.join(os.path.dirname(__file__), "../tests")
DOCS_DIR  = os.path.join(os.path.dirname(__file__), "../docs")


def load_tests() -> dict[str, str]:
    tests = {}
    for path in glob.glob(os.path.join(TESTS_DIR, "test_*.py")):
        with open(path) as f:
            tests[os.path.basename(path)] = f.read()
    return tests


def analyze_quality(tests: dict[str, str]) -> str:
    files_summary = "\n\n".join(
        f"### {name}\n```python\n{content[:600]}\n```"
        for name, content in tests.items()
    )
    prompt = f"""Tu es un expert QA Python. Analyse cette suite de tests API pytest.
Évalue : couverture des cas positifs/négatifs, assertions, fixtures, lisibilité, bonnes pratiques.

{files_summary}

Génère un rapport Markdown avec :
## Résumé
## Points forts
## Axes d'amélioration
## Recommandations prioritaires"""
    return llm.chat([{"role": "user", "content": prompt}])


def run():
    print(f"\n=== QA AGENT [{llm.MODEL}] ===")

    tests = load_tests()
    print(f"📂 {len(tests)} fichier(s) de test trouvé(s)")
    if not tests:
        print("⚠️  Aucun test trouvé dans tests/")
        return

    print("🤖 Analyse qualité en cours...")
    report = analyze_quality(tests)

    if DRY_RUN:
        print(report[:500])
        return

    os.makedirs(DOCS_DIR, exist_ok=True)
    out = os.path.join(DOCS_DIR, "qa-report.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# QA Report — API Tests\n\n_{llm.MODEL}_\n\n{report}")
    print(f"✅ Rapport généré : {out}")


if __name__ == "__main__":
    run()
