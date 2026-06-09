# ============================================================
# Report Agent -- Génération et publication du rapport Allure
# ============================================================
# Usage:
#   python agents/report-agent.py run       # Exécute les tests BDD + collecte Allure
#   python agents/report-agent.py generate  # Génère le rapport HTML depuis allure-results/
#   python agents/report-agent.py serve     # Lance un serveur HTTP (auto-ouvre le navigateur)
#   python agents/report-agent.py open      # Ouvre le rapport HTML déjà généré
#   python agents/report-agent.py summary   # Affiche le résumé des résultats JSON
#   python agents/report-agent.py full      # run + generate + open (pipeline complet)
#
# Options:
#   --clean        Vide allure-results/ avant run
#   --suite=auth   Limite run à un module de test (auth, booking_list, ...)
# ============================================================

import sys
import os
import json
import subprocess
import glob
import time

# ── Chemins ───────────────────────────────────────────────────────────────────

BASE_DIR     = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS_DIR  = os.path.join(BASE_DIR, "allure-results")
REPORT_DIR   = os.path.join(BASE_DIR, "allure-report")
ALLURE_BIN   = os.getenv("ALLURE_BIN", r"C:\Outils\allure-2.36.0\bin\allure.bat")
PYTHON_BIN   = sys.executable

# Suites BDD disponibles (par ordre d'exécution logique)
BDD_SUITES = {
    "auth":           "tests/test_auth_bdd.py",
    "booking_list":   "tests/test_booking_list_bdd.py",
    "booking_get":    "tests/test_booking_get_bdd.py",
    "booking_create": "tests/test_booking_create_bdd.py",
    "booking_update": "tests/test_booking_update_bdd.py",
    "booking_patch":  "tests/test_booking_patch_bdd.py",
    "booking_delete": "tests/test_booking_delete_bdd.py",
    "health":         "tests/test_health_check_bdd.py",
}

CLEAN   = "--clean"  in sys.argv
SUITE   = next((a.split("=")[1] for a in sys.argv if a.startswith("--suite=")), None)

# ── Couleurs ANSI ─────────────────────────────────────────────────────────────

class C:
    @staticmethod
    def ok(s):   return f"\033[32m{s}\033[0m"
    @staticmethod
    def err(s):  return f"\033[31m{s}\033[0m"
    @staticmethod
    def warn(s): return f"\033[33m{s}\033[0m"
    @staticmethod
    def info(s): return f"\033[36m{s}\033[0m"
    @staticmethod
    def bold(s): return f"\033[1m{s}\033[0m"
    @staticmethod
    def dim(s):  return f"\033[2m{s}\033[0m"


def _sep(title="", w=60):
    if title:
        pad = (w - len(title) - 2) // 2
        print(f"\n{'═' * pad} {C.bold(title)} {'═' * pad}")
    else:
        print("═" * w)


# ── Commandes ─────────────────────────────────────────────────────────────────

def cmd_clean():
    """Vide le dossier allure-results/."""
    import shutil
    if os.path.isdir(RESULTS_DIR):
        shutil.rmtree(RESULTS_DIR)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    print(C.ok(f"  [OK] {RESULTS_DIR} vidé"))


def cmd_run():
    """Exécute les tests BDD pytest avec collecte Allure."""
    _sep("RUN")
    os.chdir(BASE_DIR)

    if CLEAN:
        print(C.warn("  [--clean] Suppression des résultats précédents..."))
        cmd_clean()

    if SUITE:
        if SUITE not in BDD_SUITES:
            print(C.err(f"  [ERR] Suite inconnue : {SUITE}"))
            print(f"  Suites disponibles : {', '.join(BDD_SUITES)}")
            sys.exit(1)
        test_targets = [BDD_SUITES[SUITE]]
        print(C.info(f"  Suite     : {SUITE}"))
    else:
        test_targets = list(BDD_SUITES.values())
        print(C.info(f"  Suites    : toutes ({len(test_targets)})"))

    print(C.info(f"  Résultats : {RESULTS_DIR}"))
    print()

    cmd = [
        PYTHON_BIN, "-m", "pytest",
        *test_targets,
        "-v",
        f"--alluredir={RESULTS_DIR}",
        "--tb=short",
    ]

    start = time.monotonic()
    result = subprocess.run(cmd, cwd=BASE_DIR)
    elapsed = time.monotonic() - start

    print()
    _sep()
    if result.returncode == 0:
        print(C.ok(f"  Tous les tests ont passé  ({elapsed:.1f}s)"))
    else:
        print(C.warn(f"  Certains tests ont échoué  ({elapsed:.1f}s)  — voir le rapport"))
    _sep()
    return result.returncode


def cmd_summary():
    """Affiche un résumé des fichiers result JSON dans allure-results/."""
    _sep("RÉSUMÉ DES RÉSULTATS")

    result_files = glob.glob(os.path.join(RESULTS_DIR, "*-result.json"))
    if not result_files:
        print(C.warn(f"  Aucun fichier résultat dans {RESULTS_DIR}"))
        return

    stats = {"passed": 0, "failed": 0, "broken": 0, "skipped": 0, "unknown": 0}
    failures = []
    scenarios = []

    for fpath in result_files:
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        status = data.get("status", "unknown").lower()
        name   = data.get("name", os.path.basename(fpath))
        labels = {lbl["name"]: lbl["value"] for lbl in data.get("labels", [])}
        suite  = labels.get("suite", labels.get("feature", ""))
        tc_tag = next(
            (lbl["value"] for lbl in data.get("labels", [])
             if lbl.get("name") == "tag" and lbl.get("value", "").startswith("tc-")),
            ""
        )

        stats[status] = stats.get(status, 0) + 1
        scenarios.append((status, name, suite, tc_tag))

        if status in ("failed", "broken"):
            msg = ""
            for step in data.get("steps", []):
                if step.get("status") in ("failed", "broken"):
                    for att in step.get("attachments", []):
                        pass
                    msg = step.get("statusDetails", {}).get("message", "")[:120]
                    break
            failures.append((name, suite, tc_tag, msg))

    # Afficher stats globales
    total = sum(stats.values())
    print(f"\n  {'Métrique':<12}  {'Valeur':>6}")
    print(f"  {'─' * 20}")
    print(f"  {'Total':<12}  {total:>6}")
    print(f"  {C.ok('Passed'):<20}  {stats['passed']:>6}")
    print(f"  {C.err('Failed'):<20}  {stats['failed']:>6}")
    print(f"  {C.warn('Broken'):<20}  {stats['broken']:>6}")
    print(f"  {C.dim('Skipped'):<20}  {stats['skipped']:>6}")

    passed_pct = round(stats["passed"] / total * 100) if total else 0
    bar_ok  = "█" * (passed_pct // 5)
    bar_ko  = "░" * (20 - len(bar_ok))
    print(f"\n  [{C.ok(bar_ok)}{bar_ko}] {passed_pct}% passed\n")

    # Lister les échecs
    if failures:
        print(C.bold(f"  ÉCHECS ({len(failures)}) :"))
        for name, suite, tc_tag, msg in failures:
            tc_label = f"  {C.warn(tc_tag)}" if tc_tag else ""
            print(f"  {C.err('✗')} {name[:60]}{tc_label}")
            if msg:
                print(f"      {C.dim(msg[:100])}")
        print()

    # Répartition par feature
    suites_stats = {}
    for status, name, suite, _ in scenarios:
        key = suite or "?"
        suites_stats.setdefault(key, {"passed": 0, "failed": 0, "broken": 0, "skipped": 0})
        suites_stats[key][status] = suites_stats[key].get(status, 0) + 1

    if suites_stats:
        print(C.bold("  PAR FEATURE :"))
        for feat, s in sorted(suites_stats.items()):
            total_f = sum(s.values())
            ok = s.get("passed", 0)
            ko = s.get("failed", 0) + s.get("broken", 0)
            icon = C.ok("✓") if ko == 0 else C.err("✗")
            print(f"  {icon} {feat:<42} {C.ok(str(ok)+'P'):<12} "
                  f"{ (C.err(str(ko)+'F') if ko else C.dim('0F')):<12} / {total_f}")
    print()


def cmd_generate():
    """Génère le rapport HTML Allure depuis allure-results/."""
    _sep("GENERATE")

    result_files = glob.glob(os.path.join(RESULTS_DIR, "*-result.json"))
    if not result_files:
        print(C.err(f"  [ERR] Aucun résultat dans {RESULTS_DIR}"))
        print(f"  Lancez d'abord : python agents/report-agent.py run")
        sys.exit(1)

    print(C.info(f"  Résultats : {len(result_files)} fichiers"))
    print(C.info(f"  Rapport   : {REPORT_DIR}"))
    print()

    allure_cmd = [
        ALLURE_BIN, "generate",
        RESULTS_DIR,
        "-o", REPORT_DIR,
        "--clean",
        "--single-file",     # rapport auto-contenu (1 seul HTML)
    ]

    result = subprocess.run(allure_cmd, cwd=BASE_DIR, capture_output=True, text=True)

    if result.returncode == 0:
        index = os.path.join(REPORT_DIR, "index.html")
        single = os.path.join(REPORT_DIR, "allure-report.html")
        report_path = single if os.path.exists(single) else index
        print(C.ok(f"  [OK] Rapport généré : {report_path}"))
        return report_path
    else:
        # --single-file peut ne pas être supporté selon la version
        allure_cmd_v2 = [ALLURE_BIN, "generate", RESULTS_DIR, "-o", REPORT_DIR, "--clean"]
        result2 = subprocess.run(allure_cmd_v2, cwd=BASE_DIR, capture_output=True, text=True)
        if result2.returncode == 0:
            index = os.path.join(REPORT_DIR, "index.html")
            print(C.ok(f"  [OK] Rapport généré : {index}"))
            return index
        else:
            print(C.err(f"  [ERR] Allure generate a échoué :"))
            print(result2.stderr[:500])
            sys.exit(1)


def cmd_open(report_path=None):
    """Ouvre le rapport HTML dans le navigateur par défaut."""
    if not report_path:
        report_path = os.path.join(REPORT_DIR, "index.html")

    if not os.path.exists(report_path):
        print(C.err(f"  [ERR] Rapport introuvable : {report_path}"))
        print(f"  Lancez d'abord : python agents/report-agent.py generate")
        sys.exit(1)

    import webbrowser
    url = "file:///" + report_path.replace("\\", "/").replace("/c/", "C:/")
    print(C.info(f"  Ouverture : {url}"))
    webbrowser.open(url)
    print(C.ok("  [OK] Navigateur ouvert"))


def cmd_serve():
    """Lance `allure serve allure-results/` (serveur local + auto-ouvre le navigateur)."""
    _sep("SERVE")
    result_files = glob.glob(os.path.join(RESULTS_DIR, "*-result.json"))
    print(C.info(f"  {len(result_files)} résultats dans {RESULTS_DIR}"))
    print(C.info("  Serveur Allure → Ctrl+C pour arrêter\n"))

    subprocess.run([ALLURE_BIN, "serve", RESULTS_DIR], cwd=BASE_DIR)


# ── Main ──────────────────────────────────────────────────────────────────────

def print_help():
    print(f"""
{C.bold('Report Agent -- Génération du rapport Allure')}

{C.bold('Usage :')}
  python agents/report-agent.py run                   # Exécute tests BDD + Allure
  python agents/report-agent.py run --clean           # Vide les résultats, puis exécute
  python agents/report-agent.py run --suite=auth      # Seulement la suite auth
  python agents/report-agent.py generate              # Génère le rapport HTML
  python agents/report-agent.py open                  # Ouvre le rapport dans le navigateur
  python agents/report-agent.py serve                 # Serveur local + auto-ouvre
  python agents/report-agent.py summary               # Résumé texte des résultats
  python agents/report-agent.py full                  # run + generate + open
  python agents/report-agent.py full --clean          # Pipeline complet depuis zéro

{C.bold('Suites disponibles (--suite=) :')}
  {', '.join(BDD_SUITES.keys())}
""")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    header = f"""
{C.bold('╔══════════════════════════════════════════════════╗')}
{C.bold('║         REPORT AGENT -- Restful Booker API       ║')}
{C.bold('╚══════════════════════════════════════════════════╝')}"""
    print(header)

    if cmd in ("-h", "--help", "help"):
        print_help()

    elif cmd == "clean":
        cmd_clean()

    elif cmd == "run":
        cmd_run()
        print()
        cmd_summary()

    elif cmd == "generate":
        cmd_generate()

    elif cmd == "open":
        cmd_open()

    elif cmd == "serve":
        cmd_serve()

    elif cmd == "summary":
        cmd_summary()

    elif cmd == "full":
        rc = cmd_run()
        print()
        cmd_summary()
        report_path = cmd_generate()
        cmd_open(report_path)

    else:
        print(C.err(f"  [ERR] Commande inconnue : {cmd}"))
        print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
