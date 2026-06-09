# ============================================
# Git Agent — Commit / Push / PR / Release automatisés
# ============================================
# Analyse le diff git, génère un message de commit via LLM (Conventional Commits),
# pousse sur GitHub et crée optionnellement une PR ou release.
#
# Usage:
#   python agents/git-agent.py                     → commit + push
#   python agents/git-agent.py --pr                → commit + push + PR
#   python agents/git-agent.py --pr --base=main    → PR vers main
#   python agents/git-agent.py --release=v1.0.0    → commit + push + release
#   python agents/git-agent.py --status            → résumé repo sans commit
#   python agents/git-agent.py --dry-run           → simulation
# ============================================

import sys
import os
import subprocess
sys.path.insert(0, os.path.dirname(__file__))

import llm

DRY_RUN     = "--dry-run" in sys.argv
STATUS_ONLY = "--status" in sys.argv
CREATE_PR   = "--pr" in sys.argv
BASE_BRANCH = next((a.split("=")[1] for a in sys.argv if a.startswith("--base=")), "main")
RELEASE_TAG = next((a.split("=")[1] for a in sys.argv if a.startswith("--release=")), None)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))


def git(args: str) -> str:
    try:
        return subprocess.check_output(f"git {args}", shell=True, cwd=PROJECT_ROOT,
                                       encoding="utf-8", stderr=subprocess.DEVNULL).strip()
    except subprocess.CalledProcessError:
        return ""


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


def generate_commit_message(status: dict) -> str:
    changed = "\n".join(filter(None, [
        status["staged"], status["unstaged"], status["untracked"]
    ]))
    diff = git('diff --cached -- . ":(exclude)*.png" ":(exclude)*.jpg"')[:3000]
    prompt = f"""Génère un message de commit Conventional Commits (une ligne, max 72 chars, en anglais).
Format : <type>(<scope>): <description>
Types : feat, fix, docs, test, refactor, chore, ci

Fichiers modifiés :
{changed[:500]}

Diff :
{diff}

Réponds UNIQUEMENT avec le message de commit."""
    msg = llm.chat([{"role": "user", "content": prompt}])
    return msg.strip().strip('"\'')


def print_status(s: dict):
    print(f"\n📍 Branche    : {s['branch']}")
    print(f"📤 En avance  : {s['ahead']} commit(s)")
    print(f"📥 En retard  : {s['behind']} commit(s)")
    print(f"✏️  Dernier    : {s['last_commit']}")
    if s["staged"]:    print(f"\n✅ Stagés :\n" + "\n".join(f"   {f}" for f in s["staged"].splitlines()))
    if s["unstaged"]:  print(f"\n📝 Modifiés :\n" + "\n".join(f"   {f}" for f in s["unstaged"].splitlines()))
    if s["untracked"]: print(f"\n❓ Non suivis :\n" + "\n".join(f"   {f}" for f in s["untracked"].splitlines()[:10]))


def run():
    print(f"\n=== GIT AGENT [{llm.MODEL}] ===")
    if DRY_RUN:
        print("   MODE DRY-RUN\n")

    status = get_status()
    print_status(status)

    if STATUS_ONLY:
        return

    has_changes = any([status["staged"], status["unstaged"], status["untracked"]])
    if not has_changes and not RELEASE_TAG:
        print("\n✅ Aucun changement à committer.")
        if status["ahead"] > 0:
            print(f"📤 Push de {status['ahead']} commit(s)...")
            if not DRY_RUN:
                subprocess.run("git -c http.sslVerify=false push", shell=True, cwd=PROJECT_ROOT)
        return

    if not DRY_RUN:
        subprocess.run("git add api-pytest-framework/", shell=True, cwd=PROJECT_ROOT)

    print("\n🤖 Génération du message de commit...")
    commit_msg = generate_commit_message(status)
    print(f'\n📝 Commit : "{commit_msg}"')

    if DRY_RUN:
        print("\n[DRY-RUN] Aurait commité et pushé.")
        return

    subprocess.run(["git", "commit", "-m", commit_msg,
                    "--author=git-agent <git-agent@qa-plateforme>"],
                   cwd=PROJECT_ROOT)

    print(f"\n📤 Push → origin/{status['branch']}...")
    result = subprocess.run(
        "git -c http.sslVerify=false push origin " + status["branch"],
        shell=True, cwd=PROJECT_ROOT
    )
    if result.returncode != 0:
        print("❌ Push échoué")
        sys.exit(1)
    print("✅ Push réussi")

    if CREATE_PR:
        print("\n📬 Création de la PR via gh...")
        subprocess.run(
            ["gh", "pr", "create", "--title", commit_msg,
             "--body", f"Automated PR — {commit_msg}",
             "--base", BASE_BRANCH, "--head", status["branch"]],
            cwd=PROJECT_ROOT
        )

    if RELEASE_TAG:
        print(f"\n🏷️  Tag + Release {RELEASE_TAG}...")
        subprocess.run(f"git tag {RELEASE_TAG}", shell=True, cwd=PROJECT_ROOT)
        subprocess.run(f"git -c http.sslVerify=false push origin {RELEASE_TAG}",
                       shell=True, cwd=PROJECT_ROOT)
        subprocess.run(["gh", "release", "create", RELEASE_TAG,
                        "--title", f"Release {RELEASE_TAG}", "--notes", commit_msg],
                       cwd=PROJECT_ROOT)


if __name__ == "__main__":
    run()
