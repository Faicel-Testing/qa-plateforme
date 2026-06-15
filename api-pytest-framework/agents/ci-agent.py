# ============================================================
# CI Agent — Git · GitHub · CI/CD · Release
# ============================================================
# Absorbe : github-agent · git-agent
#
# Commandes :
#   python agents/ci-agent.py commit               → commit auto (message LLM)
#   python agents/ci-agent.py commit --dry-run     → simulation
#   python agents/ci-agent.py push                 → push vers origin
#   python agents/ci-agent.py pr                   → crée une PR (description LLM)
#   python agents/ci-agent.py pr list              → liste les PRs ouvertes
#   python agents/ci-agent.py pr merge <id>        → merge une PR
#   python agents/ci-agent.py ci run [--suite=all] → déclenche le workflow CI
#   python agents/ci-agent.py ci watch [--run-id=X] → surveille un run CI
#   python agents/ci-agent.py ci list              → derniers runs CI
#   python agents/ci-agent.py release create v1.5.0 → crée une release taguée
#   python agents/ci-agent.py release list         → liste les releases
#   python agents/ci-agent.py status               → état général du repo
#   python agents/ci-agent.py changelog            → génère CHANGELOG.md
# ============================================================

import sys, os, subprocess, json, time, glob, shutil, re
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm

FRAMEWORK   = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROJECT_ROOT = os.path.abspath(os.path.join(FRAMEWORK, ".."))
RESULTS_DIR = os.path.join(FRAMEWORK, "allure-results")
REPORT_DIR  = os.path.join(FRAMEWORK, "allure-report")
WORKFLOW_FILE = "ci-api-pytest.yml"
POLL_INTERVAL = 10

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

DRY_RUN    = "--dry-run" in sys.argv
SUITE      = next((a.split("=")[1] for a in sys.argv if a.startswith("--suite=")), "all")
RUN_ID_ARG = next((a.split("=")[1] for a in sys.argv if a.startswith("--run-id=")), None)
BASE_BRANCH = next((a.split("=")[1] for a in sys.argv if a.startswith("--base=")), "main")
TIMEOUT_MIN = int(next((a.split("=")[1] for a in sys.argv if a.startswith("--timeout=")), "30"))

BDD_SUITES = ["all", "auth", "booking_list", "booking_get", "booking_create",
               "booking_update", "booking_patch", "booking_delete", "health"]


# ── Git helpers ────────────────────────────────────────────────────────────

def git(args: str) -> str:
    try:
        return subprocess.check_output(
            f"git {args}", shell=True, cwd=PROJECT_ROOT,
            encoding="utf-8", stderr=subprocess.DEVNULL
        ).strip()
    except subprocess.CalledProcessError:
        return ""


def gh(args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        f"gh {args}", shell=True, capture_output=True,
        text=True, encoding="utf-8", errors="replace"
    )


def get_status() -> dict:
    return {
        "branch":      git("rev-parse --abbrev-ref HEAD"),
        "ahead":       int(git("rev-list --count @{u}..HEAD") or 0),
        "behind":      int(git("rev-list --count HEAD..@{u}") or 0),
        "staged":      git("diff --cached --name-only"),
        "unstaged":    git("diff --name-only"),
        "untracked":   git("ls-files --others --exclude-standard"),
        "last_commit": git('log -1 --format="%h %s"'),
    }


# ── Commit ────────────────────────────────────────────────────────────────

def generate_commit_message(status: dict) -> str:
    changed = "\n".join(filter(None, [status["staged"], status["unstaged"], status["untracked"]]))
    diff    = git('diff --cached -- . ":(exclude)*.png" ":(exclude)*.jpg"')[:3000]
    prompt  = (
        f"Génère un message de commit Conventional Commits (une ligne, max 72 chars, en anglais).\n"
        f"Format : <type>(<scope>): <description>\n"
        f"Types : feat, fix, docs, test, refactor, chore, ci\n\n"
        f"Fichiers modifiés :\n{changed[:800]}\n\n"
        f"Diff :\n{diff}\n\n"
        f"Retourne UNIQUEMENT la ligne de commit, sans explication."
    )
    return llm.chat([{"role": "user", "content": prompt}]).strip().split("\n")[0]


def cmd_commit():
    print(f"\n{W}CI AGENT — Commit{E}")
    status = get_status()
    branch = status["branch"]
    print(f"  Branche : {C}{branch}{E}")
    print(f"  Staged  : {status['staged'] or '(aucun)'}")
    print(f"  Unstaged: {status['unstaged'] or '(aucun)'}")

    has_changes = bool(status["staged"] or status["unstaged"] or status["untracked"])
    if not has_changes:
        print(f"  {Y}Aucun changement a committer.{E}")
        return

    # Stage tout (sauf .env, user.json)
    if not DRY_RUN:
        subprocess.run("git add -A", shell=True, cwd=PROJECT_ROOT)
        subprocess.run("git reset HEAD .env ui_playwright_bdd/.env ui_playwright_bdd/src/fixtures/user.json",
                       shell=True, cwd=PROJECT_ROOT, capture_output=True)

    msg = generate_commit_message(status)
    print(f"\n  {W}Message :{E} {msg}")

    if DRY_RUN:
        print(f"\n  {Y}[DRY-RUN] Commit simule.{E}")
        return

    result = subprocess.run(
        ["git", "commit", "-m", msg],
        cwd=PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode == 0:
        print(f"  {G}Commit cree.{E}")
    else:
        print(f"  {R}Erreur commit : {result.stderr[:200]}{E}")


def cmd_push():
    print(f"\n{W}CI AGENT — Push{E}")
    status = get_status()
    branch = status["branch"]

    if status["ahead"] == 0:
        print(f"  {Y}Rien a pusher (0 commits d'avance).{E}")
        return

    print(f"  {C}{status['ahead']} commit(s) a pusher sur {branch}{E}")
    if DRY_RUN:
        print(f"  {Y}[DRY-RUN] Push simule.{E}")
        return

    result = subprocess.run(
        f"git -c http.sslVerify=false push origin {branch}",
        shell=True, cwd=PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode == 0:
        print(f"  {G}Push reussi.{E}")
    else:
        print(f"  {R}Erreur push : {result.stderr[:200]}{E}")


# ── PR ────────────────────────────────────────────────────────────────────

def generate_pr_body(branch: str, base: str) -> tuple:
    diff = git(f"log {base}..{branch} --oneline")[:2000]
    messages = [{"role": "user", "content": (
        f"Génère un titre (max 70 chars) et une description de PR pour cette branche.\n\n"
        f"Branche : {branch} → {base}\n"
        f"Commits :\n{diff}\n\n"
        f"Format JSON : {{\"title\": \"...\", \"body\": \"...\"}}"
    )}]
    try:
        result = llm.chat_structured(messages, {
            "type": "object",
            "properties": {"title": {"type": "string"}, "body": {"type": "string"}},
            "required": ["title", "body"]
        })
        return result.get("title", f"feat: {branch}"), result.get("body", "")
    except Exception:
        return f"feat: {branch}", f"Merge {branch} into {base}"


def cmd_pr(sub: str = "create"):
    if sub == "list":
        print(f"\n{W}CI AGENT — PR List{E}")
        result = gh("pr list --json number,title,state,headRefName")
        if result.returncode == 0 and result.stdout.strip():
            prs = json.loads(result.stdout)
            for pr in prs:
                print(f"  #{pr['number']}  {C}{pr['headRefName']:<30}{E}  {pr['title'][:50]}")
        else:
            print(f"  {Y}Aucune PR ouverte.{E}")
        return

    if sub and sub.isdigit():
        # merge
        print(f"\n{W}CI AGENT — PR Merge #{sub}{E}")
        if DRY_RUN:
            print(f"  {Y}[DRY-RUN]{E}")
            return
        result = gh(f"pr merge {sub} --squash --delete-branch")
        print(f"  {G if result.returncode == 0 else R}{result.stdout or result.stderr}{E}")
        return

    # create
    print(f"\n{W}CI AGENT — PR Create{E}")
    status = get_status()
    branch = status["branch"]
    base   = BASE_BRANCH

    if branch == base:
        print(f"  {Y}Deja sur {base}. Creez une branche feature d'abord.{E}")
        return

    title, body = generate_pr_body(branch, base)
    print(f"  Titre : {title}")

    if DRY_RUN:
        print(f"  {Y}[DRY-RUN] PR non creee.{E}")
        return

    result = gh(f'pr create --title "{title}" --body "{body[:500]}" --base {base}')
    if result.returncode == 0:
        print(f"  {G}PR creee : {result.stdout.strip()}{E}")
    else:
        print(f"  {R}Erreur : {result.stderr[:200]}{E}")


# ── CI — GitHub Actions ────────────────────────────────────────────────────

def cmd_ci(sub: str = "list"):
    print(f"\n{W}CI AGENT — GitHub Actions [{sub}]{E}\n")

    if sub == "run":
        suite = SUITE if SUITE in BDD_SUITES else "all"
        print(f"  Declenchement workflow '{WORKFLOW_FILE}' (suite={suite})...")
        if DRY_RUN:
            print(f"  {Y}[DRY-RUN]{E}")
            return
        result = gh(f'workflow run {WORKFLOW_FILE} -f suite={suite}')
        if result.returncode == 0:
            print(f"  {G}Workflow declenche.{E}")
            time.sleep(3)
            cmd_ci("list")
        else:
            print(f"  {R}{result.stderr[:200]}{E}")

    elif sub == "list":
        result = gh(f'run list --workflow={WORKFLOW_FILE} --limit=5 --json databaseId,status,conclusion,createdAt,displayTitle')
        if result.returncode == 0 and result.stdout.strip():
            try:
                runs = json.loads(result.stdout)
                for r in runs:
                    status     = r.get("status", "?")
                    conclusion = r.get("conclusion", "")
                    color      = G if conclusion == "success" else R if conclusion == "failure" else Y
                    ts         = r.get("createdAt", "?")[:16]
                    print(f"  #{r['databaseId']}  {color}{status:<12}{E}  {conclusion:<10}  {ts}  {r.get('displayTitle','')[:40]}")
            except Exception:
                print(result.stdout[:500])
        else:
            print(f"  {Y}Aucun run trouve.{E}")

    elif sub == "watch":
        run_id = RUN_ID_ARG
        if not run_id:
            # Récupérer le dernier run
            result = gh(f'run list --workflow={WORKFLOW_FILE} --limit=1 --json databaseId')
            if result.returncode == 0 and result.stdout.strip():
                runs = json.loads(result.stdout)
                run_id = str(runs[0]["databaseId"]) if runs else None
        if not run_id:
            print(f"  {R}Aucun run ID disponible.{E}")
            return
        print(f"  Surveillance du run #{run_id} (timeout={TIMEOUT_MIN}min)...")
        deadline = time.time() + TIMEOUT_MIN * 60
        while time.time() < deadline:
            result = gh(f'run view {run_id} --json status,conclusion,jobs')
            if result.returncode == 0:
                data       = json.loads(result.stdout)
                status     = data.get("status", "?")
                conclusion = data.get("conclusion", "")
                if status == "completed":
                    color = G if conclusion == "success" else R
                    print(f"\n  {color}{W}Run {run_id} : {conclusion.upper()}{E}")
                    return
                print(f"  Status : {Y}{status}{E}  ...", end="\r")
            time.sleep(POLL_INTERVAL)
        print(f"\n  {Y}Timeout apres {TIMEOUT_MIN} minutes.{E}")


# ── Release ────────────────────────────────────────────────────────────────

def cmd_release(sub: str = "list", tag: str = None):
    print(f"\n{W}CI AGENT — Release [{sub}]{E}\n")

    if sub == "list":
        result = gh("release list --limit=5")
        if result.returncode == 0:
            print(result.stdout or f"  {Y}Aucune release.{E}")
        return

    if sub == "create" and tag:
        # Générer les notes de release via LLM
        log = git(f"log --oneline -20")
        messages = [{"role": "user", "content": (
            f"Génère des notes de release pour {tag} en markdown (max 300 chars).\n\n"
            f"Commits recents :\n{log}\n\n"
            f"Format : liste de bullet points des changements principaux."
        )}]
        notes = llm.chat(messages)
        title = f"{tag} — API pytest-bdd Framework"
        print(f"  Tag   : {tag}")
        print(f"  Titre : {title}")

        if DRY_RUN:
            print(f"  {Y}[DRY-RUN]{E}")
            return

        # Créer le tag
        subprocess.run(f"git tag {tag}", shell=True, cwd=PROJECT_ROOT)
        subprocess.run(f"git -c http.sslVerify=false push origin {tag}", shell=True, cwd=PROJECT_ROOT)

        result = gh(f'release create {tag} --title "{title}" --notes "{notes[:400]}"')
        if result.returncode == 0:
            url = result.stdout.strip()
            print(f"  {G}Release creee : {url}{E}")
        else:
            print(f"  {R}Erreur : {result.stderr[:200]}{E}")


# ── Status & Changelog ────────────────────────────────────────────────────

def cmd_status():
    print(f"\n{W}CI AGENT — Etat du repo{E}\n")
    status = get_status()
    print(f"  Branche      : {C}{status['branch']}{E}")
    print(f"  Dernier commit : {status['last_commit']}")
    print(f"  Ahead/Behind : {status['ahead']}/{status['behind']}")
    print(f"  Staged       : {status['staged'] or '(aucun)'}")
    print(f"  Unstaged     : {status['unstaged'] or '(aucun)'}")
    print(f"  Untracked    : {status['untracked'][:100] or '(aucun)'}")

    # État CI
    result = gh(f'run list --workflow={WORKFLOW_FILE} --limit=1 --json status,conclusion,createdAt')
    if result.returncode == 0 and result.stdout.strip():
        runs = json.loads(result.stdout)
        if runs:
            r = runs[0]
            conclusion = r.get("conclusion", "?")
            color      = G if conclusion == "success" else R if conclusion == "failure" else Y
            print(f"\n  Dernier CI   : {color}{conclusion}{E}  ({r.get('createdAt','?')[:16]})")


def cmd_changelog():
    print(f"\n{W}CI AGENT — CHANGELOG{E}\n")
    log = git("log --oneline -30")
    messages = [{"role": "user", "content": (
        f"Génère un CHANGELOG.md professionnel pour ce projet.\n\n"
        f"Commits recents :\n{log}\n\n"
        f"Format Markdown Keep a Changelog. Groupe par : Added, Fixed, Changed, Removed."
    )}]
    changelog_content = llm.chat(messages)
    changelog_file = os.path.join(FRAMEWORK, "CHANGELOG.md")
    with open(changelog_file, "w", encoding="utf-8") as f:
        f.write(changelog_content)
    print(f"  {G}CHANGELOG.md genere.{E}")
    print(changelog_content[:500])


# ── Main ───────────────────────────────────────────────────────────────────

def print_help():
    print(f"""
{W}CI AGENT — Git · GitHub · CI/CD · Release{E}

{W}Git :{E}
  python agents/ci-agent.py commit              Commit auto (message LLM Conventional Commits)
  python agents/ci-agent.py commit --dry-run    Simulation
  python agents/ci-agent.py push                Push vers origin (SSL bypass)
  python agents/ci-agent.py status              Etat complet du repo + dernier CI

{W}Pull Requests :{E}
  python agents/ci-agent.py pr                  Cree une PR (description LLM)
  python agents/ci-agent.py pr list             Liste les PRs ouvertes
  python agents/ci-agent.py pr <id>             Merge la PR <id>

{W}CI/CD GitHub Actions :{E}
  python agents/ci-agent.py ci run              Declenche le workflow CI
  python agents/ci-agent.py ci run --suite=auth Suite specifique
  python agents/ci-agent.py ci list             Derniers runs CI
  python agents/ci-agent.py ci watch            Surveille le dernier run

{W}Releases :{E}
  python agents/ci-agent.py release create v1.5.0  Cree une release taguee
  python agents/ci-agent.py release list            Liste les releases

{W}Documentation :{E}
  python agents/ci-agent.py changelog          Genere CHANGELOG.md via LLM

{W}Options :{E}
  --dry-run       Simulation sans ecriture
  --suite=X       Suite CI (all, auth, booking_list, ...)
  --run-id=X      ID d'un run GitHub Actions
  --base=X        Branche cible PR (defaut: main)
  --timeout=N     Timeout watch en minutes (defaut: 30)

{W}Modules absorbes :{E} github-agent · git-agent
""")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    sub = sys.argv[2] if len(sys.argv) > 2 else None
    arg = sys.argv[3] if len(sys.argv) > 3 else None

    if cmd == "commit":
        cmd_commit()
    elif cmd == "push":
        cmd_push()
    elif cmd == "pr":
        cmd_pr(sub or "create")
    elif cmd == "ci":
        cmd_ci(sub or "list")
    elif cmd == "release":
        cmd_release(sub or "list", arg)
    elif cmd == "status":
        cmd_status()
    elif cmd == "changelog":
        cmd_changelog()
    else:
        print_help()
