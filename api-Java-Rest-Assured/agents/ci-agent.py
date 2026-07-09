# ============================================================
# CI Agent — Git · GitHub Actions · Release
# ============================================================
# Commandes :
#   python agents/ci-agent.py sync              → stage + commit + push (tout en un)
#   python agents/ci-agent.py stage             → stage les fichiers non-sensibles
#   python agents/ci-agent.py commit            → commit Git avec message IA
#   python agents/ci-agent.py push              → push vers GitHub (SSL bypass)
#   python agents/ci-agent.py pr               → créer une Pull Request
#   python agents/ci-agent.py ci status         → état des workflows GitHub Actions
#   python agents/ci-agent.py ci run [workflow] → déclencher un workflow
#   python agents/ci-agent.py release           → créer une release GitHub
#   python agents/ci-agent.py changelog         → générer CHANGELOG
# ============================================================

import sys, os, json, subprocess, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm

FRAMEWORK = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# Racine git (QA_Plateforme/) — les chemins de git status sont relatifs à elle
GIT_ROOT  = subprocess.run(
    ["git", "rev-parse", "--show-toplevel"],
    cwd=FRAMEWORK, capture_output=True, text=True
).stdout.strip()

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

NEVER_COMMIT = {".env", "local.properties", "staging.properties", "production.properties"}

NEVER_STAGE_PATTERNS = [
    ".env", "local.properties", "staging.properties", "production.properties",
    ".log", ".dump", ".dumpstream",
]


def run_git(args: list, cwd: str = FRAMEWORK) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-c", "http.sslVerify=false"] + args,
                          cwd=cwd, capture_output=True, text=True)


def git_diff() -> str:
    r = run_git(["diff", "--cached", "--stat"])
    return r.stdout + r.stderr


def git_log(n: int = 5) -> str:
    r = run_git(["log", f"-{n}", "--oneline"])
    return r.stdout


def check_staged_for_secrets() -> list:
    r = run_git(["diff", "--cached", "--name-only"])
    staged = r.stdout.strip().split("\n")
    return [f for f in staged if any(f.endswith(s) or os.path.basename(f) in NEVER_COMMIT for s in NEVER_COMMIT)]


def _is_sensitive(filepath: str) -> bool:
    name = os.path.basename(filepath)
    return any(name == p or filepath.endswith(p) for p in NEVER_STAGE_PATTERNS)


def cmd_stage():
    print(f"\n{W}CI AGENT — Stage des fichiers{E}")
    r_status = run_git(["status", "--porcelain"], cwd=GIT_ROOT)
    lines = [l for l in r_status.stdout.splitlines() if l.strip()]

    staged_count = 0
    skipped = []
    for line in lines:
        filepath = line[3:].strip().strip('"')
        if _is_sensitive(filepath):
            skipped.append(filepath)
            run_git(["reset", "HEAD", "--", filepath], cwd=GIT_ROOT)
            continue
        run_git(["add", filepath], cwd=GIT_ROOT)
        staged_count += 1

    r_cached = run_git(["diff", "--cached", "--name-only"], cwd=GIT_ROOT)
    for f in r_cached.stdout.splitlines():
        if _is_sensitive(f):
            run_git(["reset", "HEAD", "--", f], cwd=GIT_ROOT)
            if f not in skipped:
                skipped.append(f)

    print(f"  {G}✓ {staged_count} fichier(s) stagé(s){E}")
    if skipped:
        print(f"  {Y}Ignorés (sensibles) :{E}")
        for s in skipped:
            print(f"  {Y}  • {s}{E}")
    return staged_count


def cmd_sync(message: str = None, branch: str = "main"):
    print(f"\n{W}CI AGENT — Sync complet : stage → commit → push{E}")
    count = cmd_stage()
    if count == 0:
        print(f"  {Y}Rien à commiter.{E}")
        return
    cmd_commit(message)
    cmd_push(branch)


def cmd_commit(message: str = None):
    print(f"\n{W}CI AGENT — Git Commit{E}")
    diff = git_diff()
    if not diff.strip():
        print(f"  {Y}Aucun fichier stagé. Utilise 'git add' d'abord.{E}")
        return

    secrets = check_staged_for_secrets()
    if secrets:
        print(f"  {R}STOP — Fichiers sensibles dans le stage :{E}")
        for s in secrets:
            print(f"  {R}  • {s}{E}")
        return

    if not message:
        log = git_log(3)
        messages = [{"role": "user", "content": (
            f"Génère un message de commit Git conventionnel (feat/fix/chore/test/docs) "
            f"pour ces changements API RestAssured :\n\n{diff}\n\n"
            f"Commits récents :\n{log}\n\n"
            f"Format : <type>(<scope>): <description courte>\n"
            f"1 ligne maximum."
        )}]
        try:
            message = llm.chat(messages).strip().split("\n")[0]
        except Exception:
            message = f"test(restassured): update test suite {time.strftime('%Y-%m-%d')}"
        print(f"  {C}Message généré : {message}{E}")

    result = run_git(["commit", "-m", message])
    if result.returncode == 0:
        print(f"  {G}✓ Commit créé{E}")
    else:
        print(f"  {R}Erreur commit :{E}\n{result.stderr}")


def cmd_push(branch: str = "main"):
    print(f"\n{W}CI AGENT — Push vers GitHub{E}")
    result = run_git(["push", "origin", branch])
    if result.returncode == 0:
        print(f"  {G}✓ Push réussi → {branch}{E}")
    else:
        print(f"  {R}Erreur push :{E}\n{result.stderr}")
    return result.returncode


def cmd_pr(title: str = None, base: str = "main"):
    print(f"\n{W}CI AGENT — Création Pull Request{E}")
    log = git_log(10)
    diff_stat = run_git(["diff", f"origin/{base}...HEAD", "--stat"]).stdout

    if not title:
        messages = [{"role": "user", "content": (
            f"Génère un titre de Pull Request pour ces commits API RestAssured :\n\n{log}\n\n"
            f"Changements :\n{diff_stat}\n\nFormat : <type>: <description> (max 70 chars)"
        )}]
        try:
            title = llm.chat(messages).strip().split("\n")[0]
        except Exception:
            title = f"test(restassured): update api restassured suite"

    result = subprocess.run(
        ["gh", "pr", "create", "--title", title, "--body",
         f"## Changements\n\n{diff_stat}\n\n🤖 Généré par CI Agent",
         "--base", base],
        cwd=FRAMEWORK, capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"  {G}✓ PR créée : {result.stdout.strip()}{E}")
    else:
        print(f"  {R}Erreur PR :{E}\n{result.stderr}")


def cmd_ci_status():
    print(f"\n{W}CI AGENT — État GitHub Actions{E}")
    result = subprocess.run(
        ["gh", "run", "list", "--limit", "5"],
        cwd=FRAMEWORK, capture_output=True, text=True
    )
    if result.returncode == 0:
        print(result.stdout)
    else:
        print(f"  {Y}gh CLI non configuré ou pas de runs.{E}\n{result.stderr}")


def cmd_ci_run(workflow: str = "ci-api-restassured.yml"):
    print(f"\n{W}CI AGENT — Déclenchement workflow : {workflow}{E}")
    result = subprocess.run(
        ["gh", "workflow", "run", workflow],
        cwd=FRAMEWORK, capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"  {G}✓ Workflow déclenché{E}")
    else:
        print(f"  {R}{result.stderr}{E}")


def cmd_release(tag: str = None):
    print(f"\n{W}CI AGENT — Création release GitHub{E}")
    if not tag:
        tag = f"v{time.strftime('%Y.%m.%d')}"
    log = git_log(20)
    messages = [{"role": "user", "content": (
        f"Génère des release notes pour la version {tag} du framework API RestAssured :\n\n{log}\n\n"
        f"Format Markdown, 3-5 points max."
    )}]
    try:
        notes = llm.chat(messages)
    except Exception:
        notes = f"Release {tag} — api-Java-Rest-Assured restful-booker.herokuapp.com"

    result = subprocess.run(
        ["gh", "release", "create", tag, "--title", f"Release {tag}",
         "--notes", notes],
        cwd=FRAMEWORK, capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"  {G}✓ Release {tag} créée{E}")
    else:
        print(f"  {R}{result.stderr}{E}")


def cmd_changelog():
    print(f"\n{W}CI AGENT — CHANGELOG{E}")
    log = run_git(["log", "--oneline", "-30"]).stdout
    messages = [{"role": "user", "content": (
        f"Génère un CHANGELOG Markdown depuis ces commits Git :\n\n{log}\n\n"
        f"Groupe par type (Features, Fixes, Refactoring, Tests). Sois concis."
    )}]
    try:
        changelog = llm.chat(messages)
        out = os.path.join(FRAMEWORK, "CHANGELOG.md")
        with open(out, "w", encoding="utf-8") as f:
            f.write(f"# Changelog\n\n{changelog}\n")
        print(f"  {G}CHANGELOG.md généré{E}")
    except Exception as e:
        print(f"  {R}LLM indisponible : {e}{E}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CI Agent — API RestAssured")
    parser.add_argument("command", choices=["sync", "stage", "commit", "push", "pr", "ci", "release", "changelog"])
    parser.add_argument("sub", nargs="?", default="status")
    parser.add_argument("--message", "-m", default=None)
    parser.add_argument("--branch", default="main")
    parser.add_argument("--tag", default=None)
    args = parser.parse_args()

    if args.command == "sync":      cmd_sync(args.message, args.branch)
    elif args.command == "stage":   cmd_stage()
    elif args.command == "commit":  cmd_commit(args.message)
    elif args.command == "push":    cmd_push(args.branch)
    elif args.command == "pr":      cmd_pr()
    elif args.command == "ci":
        if args.sub == "run":       cmd_ci_run()
        else:                       cmd_ci_status()
    elif args.command == "release": cmd_release(args.tag)
    elif args.command == "changelog": cmd_changelog()
