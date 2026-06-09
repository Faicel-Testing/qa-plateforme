# ============================================
# Bug Analyzer — Analyse les échecs et propose des corrections
# ============================================
# Lit les résultats Allure, identifie les causes racines via LLM,
# propose des correctifs dans les fichiers test_*.py.
#
# Usage:
#   python agents/bug-analyzer.py
#   python agents/bug-analyzer.py --dry-run
#   python agents/bug-analyzer.py --apply   → applique les correctifs
# ============================================

import sys
import os
import json
sys.path.insert(0, os.path.dirname(__file__))

import llm

DRY_RUN     = "--dry-run" in sys.argv
APPLY       = "--apply" in sys.argv
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "../allure-results")
TESTS_DIR   = os.path.join(os.path.dirname(__file__), "../tests")


def load_failures() -> list[dict]:
    failures = []
    if not os.path.exists(RESULTS_DIR):
        return failures
    for f in os.listdir(RESULTS_DIR):
        if f.endswith("-result.json"):
            with open(os.path.join(RESULTS_DIR, f)) as fh:
                data = json.load(fh)
            if data.get("status") in ("failed", "broken"):
                failures.append({
                    "name":    data.get("name", ""),
                    "message": data.get("statusDetails", {}).get("message", ""),
                    "trace":   data.get("statusDetails", {}).get("trace", "")[:800],
                })
    return failures


def analyze(failure: dict) -> dict:
    prompt = f"""Tu es un expert QA Python / pytest / requests.
Analyse cet échec de test API et propose un correctif précis.

Test    : {failure['name']}
Message : {failure['message']}
Trace   : {failure['trace']}

Réponds en JSON :
{{
  "root_cause": "...",
  "fix_description": "...",
  "code_patch": "...code Python corrigé..."
}}"""
    raw = llm.chat([{"role": "user", "content": prompt}])
    start, end = raw.find("{"), raw.rfind("}") + 1
    return json.loads(raw[start:end]) if start != -1 else {"root_cause": raw}


def run():
    print(f"\n=== BUG ANALYZER [{llm.MODEL}] ===")
    if DRY_RUN:
        print("   MODE DRY-RUN\n")

    failures = load_failures()
    print(f"📂 {len(failures)} échec(s) trouvé(s)")
    if not failures:
        print("✅ Aucun échec à analyser.")
        return

    for f in failures:
        print(f"\n🔍 Analyse : {f['name']}")
        result = analyze(f)
        print(f"  Cause racine  : {result.get('root_cause', '')[:120]}")
        print(f"  Correctif     : {result.get('fix_description', '')[:120]}")

        if APPLY and result.get("code_patch"):
            # TODO: appliquer le patch dans le fichier test correspondant
            print("  📝 Patch (--apply non encore implémenté)")


if __name__ == "__main__":
    run()
