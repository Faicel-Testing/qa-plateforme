# ============================================================
# GitHub Agent -- Gestion complete GitHub (CI, PR, Release, Issues)
# ============================================================
#
# CI/CD :
#   python agents/github-agent.py ci run [--suite=all]      Declenche le workflow API tests
#   python agents/github-agent.py ci watch [--run-id=X]     Surveille un run en cours
#   python agents/github-agent.py ci results [--run-id=X]   Telecharge les artifacts Allure
#   python agents/github-agent.py ci list                    Liste les derniers runs
#   python agents/github-agent.py ci full [--suite=all]     Pipeline complet run+watch+results+Jira
#
# Pull Requests :
#   python agents/github-agent.py pr create [--base=main]   Cree une PR (description LLM)
#   python agents/github-agent.py pr list                    Liste les PRs ouvertes
#   python agents/github-agent.py pr merge <id>              Merge une PR
#   python agents/github-agent.py pr view <id>               Affiche les details d'une PR
#
# Releases :
#   python agents/github-agent.py release create <v1.4.0>   Cree une release taguee
#   python agents/github-agent.py release list               Liste les releases
#
# Issues :
#   python agents/github-agent.py issue create               Cree une issue (depuis echecs Allure)
#   python agents/github-agent.py issue list                 Liste les issues ouvertes
#   python agents/github-agent.py issue close <id>           Ferme une issue
#
# Divers :
#   python agents/github-agent.py status                     Etat general du repo
#   python agents/github-agent.py changelog                  Genere CHANGELOG.md via LLM
#   python agents/github-agent.py workflow list              Liste les workflows disponibles
#   python agents/github-agent.py secrets list               Liste les noms des secrets
#
# Options globales :
#   --dry-run       Simulation sans ecriture
#   --suite=X       Suite CI (all, auth, booking_list, booking_get, ...)
#   --run-id=X      ID d'un run GitHub Actions specifique
#   --base=X        Branche cible PR (defaut : main)
#   --branch=X      Branche source pour workflow_dispatch
#   --timeout=N     Timeout watch en minutes (defaut : 30)
# ============================================================

import sys
import os
import json
import subprocess
import time
import glob
import shutil
import re

# -- encodage UTF-8 sur Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(__file__))
import llm

# ── Constantes ────────────────────────────────────────────────────────────────

BASE_DIR     = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS_DIR  = os.path.join(BASE_DIR, "allure-results")
REPORT_DIR   = os.path.join(BASE_DIR, "allure-report")
WORKFLOW_FILE = "ci-api-pytest.yml"
DEFAULT_BASE  = "main"
POLL_INTERVAL = 10   # secondes entre chaque poll CI

BDD_SUITES = [
    "all", "auth", "booking_list", "booking_get",
    "booking_create", "booking_update", "booking_patch",
    "booking_delete", "health",
]

# ── Arguments ─────────────────────────────────────────────────────────────────

DRY_RUN    = "--dry-run" in sys.argv
SUITE      = next((a.split("=")[1] for a in sys.argv if a.startswith("--suite=")), "all")
RUN_ID_ARG = next((a.split("=")[1] for a in sys.argv if a.startswith("--run-id=")), None)
BASE_BRANCH = next((a.split("=")[1] for a in sys.argv if a.startswith("--base=")), DEFAULT_BASE)
SRC_BRANCH  = next((a.split("=")[1] for a in sys.argv if a.startswith("--branch=")), None)
TIMEOUT_MIN = int(next((a.split("=")[1] for a in sys.argv if a.startswith("--timeout=")), "30"))


# ── Couleurs ANSI ─────────────────────────────────────────────────────────────

class C:
    @staticmethod
    def ok(s):    return f"\033[32m{s}\033[0m"
    @staticmethod
    def err(s):   return f"\033[31m{s}\033[0m"
    @staticmethod
    def warn(s):  return f"\033[33m{s}\033[0m"
    @staticmethod
    def info(s):  return f"\033[36m{s}\033[0m"
    @staticmethod
    def bold(s):  return f"\033[1m{s}\033[0m"
    @staticmethod
    def dim(s):   return f"\033[2m{s}\033[0m"


def _sep(title="", w=62):
    if title:
        pad = (w - len(title) - 2) // 2
        print(f"\n{'=' * pad} {C.bold(title)} {'=' * pad}")
    else:
        print("=" * w)


# ── Helpers subprocess ────────────────────────────────────────────────────────

def _run(cmd, capture=True, cwd=None, check=False, env_extra=None):
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    result = subprocess.run(
        cmd, shell=isinstance(cmd, str),
        capture_output=capture, text=True,
        cwd=cwd or BASE_DIR, env=env,
        encoding="utf-8", errors="replace",
    )
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"Commande echouee : {cmd}")
    return result


def gh(args: str, capture=True) -> subprocess.CompletedProcess:
    return _run(f"gh {args}", capture=capture)


def gh_json(args: str) -> dict | list | None:
    r = gh(args)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout.strip())
    except Exception:
        return None


def git(args: str) -> str:
    r = _run(f"git -c http.sslVerify=false {args}", capture=True)
    return r.stdout.strip()


# ── Detection repo ────────────────────────────────────────────────────────────

def get_repo() -> str:
    data = gh_json("repo view --json nameWithOwner")
    if data and "nameWithOwner" in data:
        return data["nameWithOwner"]
    remote = git("remote get-url origin")
    m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", remote)
    return m.group(1) if m else "unknown/unknown"


def get_current_branch() -> str:
    return git("rev-parse --abbrev-ref HEAD")


# ── Status ────────────────────────────────────────────────────────────────────

def cmd_status():
    _sep("STATUT REPO")
    repo   = get_repo()
    branch = get_current_branch()
    ahead  = int(git(f"rev-list --count @{{u}}..HEAD") or 0)
    behind = int(git(f"rev-list --count HEAD..@{{u}}") or 0)
    last   = git('log -1 --format="%h %s (%cr)"')

    print(f"\n  Repo    : {C.bold(repo)}")
    print(f"  Branche : {C.info(branch)}")
    print(f"  Ahead   : {ahead}  |  Behind : {behind}")
    print(f"  Dernier : {C.dim(last)}")

    # PRs ouvertes
    prs = gh_json("pr list --state open --json number,title,headRefName,createdAt") or []
    print(f"\n  PRs ouvertes : {len(prs)}")
    for pr in prs[:5]:
        print(f"    #{pr['number']}  {pr['title'][:55]}  [{C.dim(pr['headRefName'])}]")

    # Dernier run CI
    runs = gh_json(f"run list --workflow={WORKFLOW_FILE} --limit=3 --json databaseId,status,conclusion,headBranch,createdAt,displayTitle") or []
    print(f"\n  Derniers runs CI ({WORKFLOW_FILE}) :")
    if not runs:
        print(f"    {C.dim('Aucun run trouve')}")
    for r in runs:
        icon  = C.ok("[PASS]") if r.get("conclusion") == "success" else \
                C.err("[FAIL]") if r.get("conclusion") == "failure" else \
                C.warn(f"[{r.get('status','?').upper()}]")
        print(f"    {icon}  #{r['databaseId']}  {r.get('displayTitle','')[:40]}  [{r['headBranch']}]  {r['createdAt'][:10]}")

    # Releases
    releases = gh_json("release list --limit=3 --json tagName,name,publishedAt,isLatest") or []
    print(f"\n  Releases recentes :")
    for rel in releases:
        latest = C.ok("  [latest]") if rel.get("isLatest") else ""
        print(f"    {rel['tagName']}  {rel.get('name','')[:45]}{latest}  {rel['publishedAt'][:10]}")
    print()


# ── CI : workflow list ────────────────────────────────────────────────────────

def cmd_workflow_list():
    _sep("WORKFLOWS")
    workflows = gh_json("workflow list --json id,name,state,path") or []
    print(f"\n  {'ID':<8} {'Etat':<10} {'Nom':<40} Fichier")
    print(f"  {'─'*70}")
    for w in workflows:
        state = C.ok("active") if w.get("state") == "active" else C.dim(w.get("state", "?"))
        print(f"  {w['id']:<8} {state:<18} {w['name']:<40} {w['path']}")
    print()


# ── CI : list runs ────────────────────────────────────────────────────────────

def cmd_ci_list(limit=10):
    _sep("DERNIERS RUNS CI")
    runs = gh_json(
        f"run list --workflow={WORKFLOW_FILE} --limit={limit} "
        "--json databaseId,status,conclusion,headBranch,createdAt,displayTitle,url"
    ) or []

    if not runs:
        print(C.warn(f"\n  Aucun run pour {WORKFLOW_FILE}"))
        print(C.dim(f"  Lancez d'abord : python agents/github-agent.py ci run"))
        return

    print(f"\n  {'ID':<12} {'Statut':<12} {'Branche':<25} {'Date':<12} Titre")
    print(f"  {'─'*80}")
    for r in runs:
        conc  = r.get("conclusion") or r.get("status") or "?"
        icon  = C.ok("[PASS]")   if conc == "success"   else \
                C.err("[FAIL]")  if conc == "failure"   else \
                C.warn(f"[{conc.upper()[:6]}]")
        print(f"  {r['databaseId']:<12} {icon:<20} {r['headBranch']:<25} {r['createdAt'][:10]}  {r.get('displayTitle','')[:35]}")
    print()


# ── CI : run (trigger workflow) ───────────────────────────────────────────────

def cmd_ci_run() -> str | None:
    _sep("CI RUN")
    branch = SRC_BRANCH or get_current_branch()
    suite  = SUITE

    print(f"  Workflow : {C.bold(WORKFLOW_FILE)}")
    print(f"  Branche  : {C.info(branch)}")
    print(f"  Suite    : {C.info(suite)}")

    if suite not in BDD_SUITES:
        print(C.err(f"\n  [ERR] Suite inconnue : {suite}"))
        print(f"  Suites disponibles : {', '.join(BDD_SUITES)}")
        return None

    if DRY_RUN:
        print(C.warn("\n  [DRY-RUN] Aurait declenche le workflow."))
        return None

    r = gh(f'workflow run {WORKFLOW_FILE} --ref {branch} --field suite={suite}')
    if r.returncode != 0:
        print(C.err(f"\n  [ERR] {r.stderr.strip()[:200]}"))
        return None

    print(C.ok("\n  [OK] Workflow declenche"))

    # Attendre que le run apparaisse dans l'API (delai GitHub ~3-5s)
    print(C.dim("  Attente du demarrage..."), end="", flush=True)
    run_id = None
    for _ in range(15):
        time.sleep(3)
        runs = gh_json(
            f"run list --workflow={WORKFLOW_FILE} --limit=1 --branch={branch} "
            "--json databaseId,status,createdAt"
        ) or []
        if runs:
            run_id = str(runs[0]["databaseId"])
            break
        print(".", end="", flush=True)

    if run_id:
        repo = get_repo()
        print(C.ok(f"\n  [OK] Run ID : {run_id}"))
        print(C.info(f"  URL : https://github.com/{repo}/actions/runs/{run_id}"))
    else:
        print(C.warn("\n  [!] Run ID non detecte -- verifiez manuellement"))

    return run_id


# ── CI : watch run ────────────────────────────────────────────────────────────

def cmd_ci_watch(run_id: str = None) -> str | None:
    _sep("CI WATCH")

    if not run_id:
        if RUN_ID_ARG:
            run_id = RUN_ID_ARG
        else:
            runs = gh_json(
                f"run list --workflow={WORKFLOW_FILE} --limit=1 "
                "--json databaseId,status"
            ) or []
            if not runs:
                print(C.err("  [ERR] Aucun run trouve."))
                return None
            run_id = str(runs[0]["databaseId"])

    print(f"  Run ID  : {C.bold(run_id)}")
    print(f"  Timeout : {TIMEOUT_MIN} min\n")

    deadline = time.monotonic() + TIMEOUT_MIN * 60
    last_status = ""

    try:
        while time.monotonic() < deadline:
            data = gh_json(
                f"run view {run_id} --json status,conclusion,jobs,displayTitle,headBranch,createdAt"
            )
            if not data:
                print(C.warn("  [!] Run introuvable ou API indisponible"))
                time.sleep(POLL_INTERVAL)
                continue

            status    = data.get("status", "?")
            conclusion = data.get("conclusion") or ""

            if status != last_status:
                ts = time.strftime("%H:%M:%S")
                icon = C.warn(f"[{status.upper()}]")
                print(f"  [{ts}] {icon}  {data.get('displayTitle','')[:50]}")
                last_status = status

                # Afficher les jobs
                for job in data.get("jobs", []):
                    jstat = job.get("conclusion") or job.get("status") or "?"
                    jicon = C.ok("[OK]") if jstat == "success" else \
                            C.err("[FAIL]") if jstat == "failure" else \
                            C.dim(f"[{jstat}]")
                    print(f"         {jicon}  {job.get('name','')[:50]}")

            if status == "completed":
                if conclusion == "success":
                    print(C.ok(f"\n  [OK] Run termine avec succes"))
                elif conclusion == "failure":
                    print(C.err(f"\n  [FAIL] Run echoue"))
                else:
                    print(C.warn(f"\n  [!] Conclusion : {conclusion}"))
                return conclusion

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print(C.warn("\n  [!] Interruption utilisateur"))
        return None

    print(C.warn(f"\n  [!] Timeout atteint ({TIMEOUT_MIN} min)"))
    return None


# ── CI : download results ────────────────────────────────────────────────────

def cmd_ci_results(run_id: str = None):
    _sep("CI RESULTS")

    if not run_id:
        run_id = RUN_ID_ARG
        if not run_id:
            runs = gh_json(
                f"run list --workflow={WORKFLOW_FILE} --limit=1 "
                "--json databaseId,conclusion"
            ) or []
            if not runs:
                print(C.err("  [ERR] Aucun run trouve."))
                return
            run_id = str(runs[0]["databaseId"])

    print(f"  Run ID : {C.bold(run_id)}")

    if DRY_RUN:
        print(C.warn("  [DRY-RUN] Aurait telecharge les artifacts."))
        return

    # Telechargement dans un dossier temporaire
    tmp_dir = os.path.join(BASE_DIR, "_ci_download")
    os.makedirs(tmp_dir, exist_ok=True)

    print(C.info("  Telechargement de allure-results..."))
    r = gh(f"run download {run_id} --name allure-results --dir {tmp_dir}")
    if r.returncode != 0:
        print(C.err(f"  [ERR] {r.stderr.strip()[:200]}"))
        # Essai sans filtre de nom
        r2 = gh(f"run download {run_id} --dir {tmp_dir}")
        if r2.returncode != 0:
            print(C.err("  [ERR] Impossible de telecharger les artifacts"))
            return

    # Detecter les JSON de resultats
    json_files = glob.glob(os.path.join(tmp_dir, "**", "*-result.json"), recursive=True)
    if not json_files:
        print(C.warn("  [!] Aucun fichier *-result.json trouve dans les artifacts"))
        return

    # Copier vers allure-results/
    os.makedirs(RESULTS_DIR, exist_ok=True)
    copied = 0
    for src in json_files:
        dst = os.path.join(RESULTS_DIR, os.path.basename(src))
        shutil.copy2(src, dst)
        copied += 1

    # Copier aussi les containers et attachments
    for extra in glob.glob(os.path.join(tmp_dir, "**", "*.json"), recursive=True):
        dst = os.path.join(RESULTS_DIR, os.path.basename(extra))
        if not os.path.exists(dst):
            shutil.copy2(extra, dst)

    shutil.rmtree(tmp_dir, ignore_errors=True)
    print(C.ok(f"  [OK] {copied} fichiers result.json -> {RESULTS_DIR}"))

    # Afficher le resume
    _print_allure_summary()


def _print_allure_summary():
    files  = glob.glob(os.path.join(RESULTS_DIR, "*-result.json"))
    if not files:
        return
    stats  = {"passed": 0, "failed": 0, "broken": 0, "skipped": 0}
    fails  = []
    for fp in files:
        try:
            with open(fp, encoding="utf-8") as f:
                d = json.load(f)
            s = d.get("status", "unknown")
            if s in stats:
                stats[s] += 1
            if s in ("failed", "broken"):
                fails.append(d.get("name", "?")[:60])
        except Exception:
            pass

    total = sum(stats.values())
    pct   = round(stats["passed"] / total * 100) if total else 0
    bar   = C.ok("█" * (pct // 5)) + "░" * (20 - pct // 5)
    print(f"\n  [{bar}] {pct}% passed")
    print(f"  Total: {total}  |  {C.ok(str(stats['passed'])+'P')}  "
          f"{C.err(str(stats['failed'])+'F')}  {C.warn(str(stats['broken'])+'B')}")
    if fails:
        print(f"\n  Echecs :")
        for f in fails[:5]:
            print(f"    {C.err('x')} {f}")
        if len(fails) > 5:
            print(f"    {C.dim(f'... et {len(fails)-5} autres')}")


# ── CI : pipeline complet ────────────────────────────────────────────────────

def cmd_ci_full():
    _sep("CI PIPELINE COMPLET")
    print(f"  Suite    : {C.info(SUITE)}")
    print(f"  Etapes   : run -> watch -> results -> sync Jira -> rapport Allure\n")

    # 1. Trigger
    run_id = cmd_ci_run()
    if not run_id and not DRY_RUN:
        print(C.err("\n  [ERR] Impossible de demarrer le run CI"))
        return

    if DRY_RUN:
        print(C.warn("\n  [DRY-RUN] Pipeline simule."))
        return

    print()

    # 2. Watch
    conclusion = cmd_ci_watch(run_id)
    print()

    # 3. Download results
    cmd_ci_results(run_id)
    print()

    # 4. Sync Jira (status-agent)
    _sep("SYNC JIRA")
    status_agent = os.path.join(os.path.dirname(__file__), "status-agent.py")
    if os.path.exists(status_agent):
        print(C.info("  Lancement de status-agent sync..."))
        r = _run([sys.executable, status_agent, "sync"], capture=False)
        if r.returncode == 0:
            print(C.ok("  [OK] Jira synchronise"))
        else:
            print(C.warn("  [!] status-agent a retourne une erreur"))
    else:
        print(C.dim("  status-agent.py introuvable -- sync Jira ignore"))

    # 5. Rapport Allure
    _sep("ALLURE REPORT")
    allure_bin = os.getenv("ALLURE_BIN", r"C:\Outils\allure-2.36.0\bin\allure.bat")
    if os.path.exists(allure_bin):
        r = _run([allure_bin, "generate", RESULTS_DIR, "-o", REPORT_DIR, "--clean"],
                 capture=True)
        if r.returncode == 0:
            print(C.ok(f"  [OK] Rapport genere : {REPORT_DIR}"))
        else:
            print(C.warn("  [!] Allure generate a echoue"))
    else:
        print(C.dim(f"  Allure CLI introuvable ({allure_bin}) -- rapport ignore"))

    _sep()
    status_icon = C.ok("[OK]") if conclusion == "success" else C.err("[FAIL]")
    print(f"\n  {status_icon}  Pipeline complet | Run #{run_id} | Suite: {SUITE}")
    print()


# ── Pull Requests ────────────────────────────────────────────────────────────

def cmd_pr_list():
    _sep("PULL REQUESTS")
    prs = gh_json("pr list --state open --json number,title,headRefName,baseRefName,createdAt,labels,url") or []

    if not prs:
        print(C.dim("\n  Aucune PR ouverte.\n"))
        return

    print(f"\n  {'#':<6} {'Source -> Base':<35} {'Titre':<45} Date")
    print(f"  {'─'*95}")
    for pr in prs:
        labels = ", ".join(l["name"] for l in pr.get("labels", []))
        label_str = f" [{C.dim(labels)}]" if labels else ""
        ref = f"{pr['headRefName'][:18]} -> {pr['baseRefName']}"
        print(f"  #{pr['number']:<5} {ref:<35} {pr['title'][:45]}{label_str}")
    print()


def cmd_pr_create():
    _sep("PR CREATE")
    branch = get_current_branch()
    base   = BASE_BRANCH

    print(f"  Source : {C.info(branch)}")
    print(f"  Base   : {C.info(base)}")

    # Verifier si PR existe deja
    existing = gh_json(f"pr list --head {branch} --base {base} --state open --json number,title") or []
    if existing:
        print(C.warn(f"\n  [!] PR #{existing[0]['number']} deja ouverte : {existing[0]['title']}"))
        return

    # Generer le titre et la description via LLM
    print(C.info("\n  Generation de la description via LLM..."))
    diff  = git(f"log --oneline {base}..{branch}")[:2000]
    files = git(f"diff --name-only {base}..{branch}")[:1000]

    prompt = f"""Tu es un expert QA. Genere un titre et une description de Pull Request au format Markdown.

Branche source : {branch}
Branche cible  : {base}

Commits :
{diff}

Fichiers modifies :
{files}

Reponds UNIQUEMENT avec ce format JSON :
{{
  "title": "titre court (<70 chars)",
  "body": "description markdown complete avec ## Summary, ## Changes, ## Test plan"
}}"""

    try:
        raw  = llm.chat([{"role": "user", "content": prompt}])
        # Extraire le JSON
        m    = re.search(r"\{.*\}", raw, re.DOTALL)
        data = json.loads(m.group(0)) if m else {}
        title = data.get("title", f"feat: {branch}")
        body  = data.get("body", f"Changes from {branch} to {base}")
    except Exception as e:
        print(C.warn(f"  [!] LLM erreur ({e}) -- titre auto"))
        title = f"feat: {branch}"
        body  = f"Changements de la branche `{branch}` vers `{base}`"

    print(f"\n  Titre : {C.bold(title)}")

    if DRY_RUN:
        print(C.warn("\n  [DRY-RUN] Aurait cree la PR."))
        return

    # Creer la PR
    tmp_body = os.path.join(BASE_DIR, "_pr_body.md")
    with open(tmp_body, "w", encoding="utf-8") as f:
        f.write(body)

    r = _run(["gh", "pr", "create",
              "--title", title,
              "--body-file", tmp_body,
              "--base", base,
              "--head", branch],
             capture=True)
    os.unlink(tmp_body)

    if r.returncode == 0:
        url = r.stdout.strip()
        print(C.ok(f"\n  [OK] PR creee : {url}"))
    else:
        print(C.err(f"\n  [ERR] {r.stderr.strip()[:200]}"))


def cmd_pr_merge(pr_id: str):
    _sep("PR MERGE")
    print(f"  PR : #{pr_id}")

    data = gh_json(f"pr view {pr_id} --json number,title,state,mergeable")
    if not data:
        print(C.err(f"  [ERR] PR #{pr_id} introuvable"))
        return

    print(f"  Titre   : {data.get('title','')}")
    print(f"  Statut  : {data.get('state','')}")
    print(f"  Mergeable: {data.get('mergeable','?')}")

    if data.get("state") != "OPEN":
        print(C.warn("  [!] La PR n'est pas ouverte -- merge ignore"))
        return

    if DRY_RUN:
        print(C.warn("\n  [DRY-RUN] Aurait merge la PR."))
        return

    r = gh(f"pr merge {pr_id} --squash --auto --delete-branch")
    if r.returncode == 0:
        print(C.ok(f"\n  [OK] PR #{pr_id} mergee (squash)"))
    else:
        print(C.err(f"\n  [ERR] {r.stderr.strip()[:200]}"))


def cmd_pr_view(pr_id: str):
    _sep(f"PR #{pr_id}")
    r = gh(f"pr view {pr_id}", capture=False)


# ── Releases ──────────────────────────────────────────────────────────────────

def cmd_release_list():
    _sep("RELEASES")
    releases = gh_json("release list --limit=10 --json tagName,name,publishedAt,isLatest,isDraft") or []

    if not releases:
        print(C.dim("\n  Aucune release.\n"))
        return

    print(f"\n  {'Tag':<12} {'Statut':<10} {'Date':<12} Nom")
    print(f"  {'─'*70}")
    for rel in releases:
        latest = C.ok("[latest]") if rel.get("isLatest") else \
                 C.dim("[draft]")  if rel.get("isDraft")  else "        "
        print(f"  {rel['tagName']:<12} {latest:<18} {rel['publishedAt'][:10]}  {rel.get('name','')[:45]}")
    print()


def cmd_release_create(version: str):
    _sep("RELEASE CREATE")
    if not version:
        print(C.err("  [ERR] Version requise : python agents/github-agent.py release create v1.4.0"))
        return

    # Verifier que le tag n'existe pas deja
    existing = gh_json(f"release view {version} --json tagName") if version else None
    if existing:
        print(C.warn(f"  [!] Release {version} existe deja"))
        return

    # Commits depuis le dernier tag
    last_tag = git("describe --tags --abbrev=0 2>/dev/null") or ""
    if last_tag:
        commit_log = git(f"log {last_tag}..HEAD --oneline")[:3000]
    else:
        commit_log = git("log --oneline -20")

    print(C.info("  Generation des release notes via LLM..."))
    prompt = f"""Genere des release notes Markdown professionnelles pour la version {version}.

Commits depuis {last_tag or 'le debut'} :
{commit_log}

Format attendu :
## Quoi de neuf
- bullet points des changements majeurs

## Corrections
- bullet points des corrections

## Stack technique
- technologies

Reponds UNIQUEMENT avec le Markdown."""

    try:
        notes = llm.chat([{"role": "user", "content": prompt}])
    except Exception as e:
        notes = f"Release {version}\n\nChangements depuis {last_tag or 'v0'}:\n{commit_log[:500]}"
        print(C.warn(f"  [!] LLM erreur : {e}"))

    print(f"\n  Version : {C.bold(version)}")
    print(f"  Tag prev: {C.dim(last_tag or 'aucun')}")

    if DRY_RUN:
        print(C.warn("\n  [DRY-RUN] Aurait cree la release."))
        print(C.dim("\n  Notes generees :"))
        print(notes[:400])
        return

    tmp_notes = os.path.join(BASE_DIR, "_release_notes.md")
    with open(tmp_notes, "w", encoding="utf-8") as f:
        f.write(notes)

    # Creer le tag git si inexistant
    if not git(f"tag -l {version}"):
        _run(f"git tag -a {version} -m 'Release {version}'", capture=True)
        _run(f"git -c http.sslVerify=false push origin {version}", capture=True)
        print(C.ok(f"  [OK] Tag {version} pousse"))

    r = _run(["gh", "release", "create", version,
              "--title", f"{version}",
              "--notes-file", tmp_notes,
              "--latest"],
             capture=True)
    os.unlink(tmp_notes)

    if r.returncode == 0:
        url = r.stdout.strip()
        print(C.ok(f"\n  [OK] Release creee : {url}"))
    else:
        print(C.err(f"\n  [ERR] {r.stderr.strip()[:200]}"))


# ── Issues ────────────────────────────────────────────────────────────────────

def cmd_issue_list():
    _sep("ISSUES")
    issues = gh_json("issue list --state open --json number,title,labels,createdAt,assignees") or []

    if not issues:
        print(C.dim("\n  Aucune issue ouverte.\n"))
        return

    print(f"\n  {'#':<6} {'Date':<12} {'Titre':<55} Labels")
    print(f"  {'─'*90}")
    for iss in issues:
        labels  = ", ".join(l["name"] for l in iss.get("labels", []))
        assigns = ", ".join(a["login"] for a in iss.get("assignees", []))
        print(f"  #{iss['number']:<5} {iss['createdAt'][:10]}  {iss['title'][:55]}  {C.dim(labels)}")
    print()


def cmd_issue_create():
    _sep("ISSUE CREATE")

    # Charger les echecs Allure si disponibles
    result_files = glob.glob(os.path.join(RESULTS_DIR, "*-result.json"))
    failures = []
    for fp in result_files:
        try:
            with open(fp, encoding="utf-8") as f:
                d = json.load(f)
            if d.get("status") in ("failed", "broken"):
                failures.append({
                    "name":    d.get("name", "?"),
                    "status":  d.get("status"),
                    "message": (d.get("statusDetails") or {}).get("message", "")[:300],
                })
        except Exception:
            pass

    if not failures:
        print(C.warn("  Aucun echec Allure trouve -- creation issue manuelle"))
        title = f"[BUG] Echecs detectes - api-pytest-framework"
        body  = "Des echecs ont ete detectes dans le framework API. Details a completer."
    else:
        print(C.info(f"  {len(failures)} echec(s) Allure detectes -- generation via LLM..."))
        fail_text = "\n".join(
            f"- [{f['status'].upper()}] {f['name']}: {f['message']}"
            for f in failures[:10]
        )
        prompt = f"""Tu es un QA expert. Genere un titre et un body d'issue GitHub en Markdown
pour les echecs de tests suivants :

{fail_text}

Format JSON :
{{
  "title": "[BUG] titre court",
  "body": "## Description\\n...\\n## Tests echoues\\n...\\n## Priorite\\n..."
}}

Reponds UNIQUEMENT avec le JSON."""

        try:
            raw  = llm.chat([{"role": "user", "content": prompt}])
            m    = re.search(r"\{.*\}", raw, re.DOTALL)
            data = json.loads(m.group(0)) if m else {}
            title = data.get("title", "[BUG] Echecs tests API")
            body  = data.get("body", fail_text)
        except Exception as e:
            title = f"[BUG] {len(failures)} echec(s) detectes - api-pytest-framework"
            body  = f"## Tests en echec\n\n{fail_text}"
            print(C.warn(f"  [!] LLM erreur : {e}"))

    print(f"\n  Titre : {C.bold(title)}")

    if DRY_RUN:
        print(C.warn("\n  [DRY-RUN] Aurait cree l'issue."))
        return

    tmp_body = os.path.join(BASE_DIR, "_issue_body.md")
    with open(tmp_body, "w", encoding="utf-8") as f:
        f.write(body)

    r = _run(["gh", "issue", "create",
              "--title", title,
              "--body-file", tmp_body,
              "--label", "bug"],
             capture=True)
    os.unlink(tmp_body)

    if r.returncode == 0:
        url = r.stdout.strip()
        print(C.ok(f"\n  [OK] Issue creee : {url}"))
    else:
        print(C.err(f"\n  [ERR] {r.stderr.strip()[:200]}"))


def cmd_issue_close(issue_id: str):
    _sep(f"FERMER ISSUE #{issue_id}")
    if DRY_RUN:
        print(C.warn(f"  [DRY-RUN] Aurait ferme l'issue #{issue_id}"))
        return
    r = gh(f"issue close {issue_id}")
    if r.returncode == 0:
        print(C.ok(f"  [OK] Issue #{issue_id} fermee"))
    else:
        print(C.err(f"  [ERR] {r.stderr.strip()[:200]}"))


# ── Changelog ────────────────────────────────────────────────────────────────

def cmd_changelog():
    _sep("CHANGELOG")
    changelog_file = os.path.join(BASE_DIR, "CHANGELOG.md")

    # Recuperer tous les commits depuis v1.0.0
    first_tag = git("tag --sort=version:refname | head -1") or ""
    all_tags  = git("tag --sort=-version:refname").splitlines()

    print(C.info("  Collecte des commits par version..."))
    sections = []
    for i, tag in enumerate(all_tags):
        prev_tag = all_tags[i + 1] if i + 1 < len(all_tags) else ""
        if prev_tag:
            log = git(f"log {prev_tag}..{tag} --oneline --no-merges")
        else:
            log = git(f"log {tag} --oneline --no-merges")
        if log:
            sections.append((tag, log[:1500]))

    # Commits non tagges (HEAD)
    latest_tag = all_tags[0] if all_tags else ""
    unreleased = git(f"log {latest_tag}..HEAD --oneline --no-merges") if latest_tag else ""
    if unreleased:
        sections.insert(0, ("Unreleased", unreleased))

    if not sections:
        print(C.warn("  Aucun commit trouve"))
        return

    print(C.info("  Generation du CHANGELOG via LLM..."))
    history = "\n\n".join(f"### {tag}\n{log}" for tag, log in sections[:8])
    prompt = f"""Genere un CHANGELOG.md professionnel au format Keep a Changelog.

Historique git par version :
{history}

Format attendu :
# Changelog
## [Unreleased]
## [v1.3.0] - date
### Added / Fixed / Changed / Removed
- ...

Reponds UNIQUEMENT avec le Markdown complet."""

    try:
        content = llm.chat([{"role": "user", "content": prompt}])
    except Exception as e:
        # Fallback : changelog basique
        content = "# Changelog\n\n"
        for tag, log in sections:
            content += f"## {tag}\n\n"
            for line in log.splitlines():
                content += f"- {line}\n"
            content += "\n"
        print(C.warn(f"  [!] LLM erreur : {e} -- changelog basique genere"))

    if DRY_RUN:
        print(C.warn("  [DRY-RUN] Apercu :"))
        print(content[:600])
        return

    with open(changelog_file, "w", encoding="utf-8") as f:
        f.write(content)
    print(C.ok(f"\n  [OK] CHANGELOG.md genere : {changelog_file}"))
    print(content[:400])


# ── Secrets ──────────────────────────────────────────────────────────────────

def cmd_secrets_list():
    _sep("SECRETS GITHUB")
    r = gh("secret list --json name,updatedAt")
    if r.returncode != 0:
        print(C.err(f"  [ERR] {r.stderr.strip()[:200]}"))
        return
    try:
        secrets = json.loads(r.stdout)
    except Exception:
        secrets = []
    if not secrets:
        print(C.warn("  Aucun secret configure"))
        print(C.dim("  Secrets requis : SMTP_USER, SMTP_PASS"))
        return
    print(f"\n  {'Nom':<30} Derniere MAJ")
    print(f"  {'─'*50}")
    for s in secrets:
        print(f"  {s['name']:<30} {s.get('updatedAt','?')[:10]}")

    # Verifier les secrets requis
    required = {"SMTP_USER", "SMTP_PASS"}
    existing = {s["name"] for s in secrets}
    missing  = required - existing
    if missing:
        print(C.warn(f"\n  [!] Secrets manquants : {', '.join(missing)}"))
        print(C.dim("  Ajouter : gh secret set SMTP_USER --body=..."))
    else:
        print(C.ok("\n  [OK] Tous les secrets requis sont configures"))
    print()


# ── Help ────────────────────────────────────────────────────────────────────

def print_help():
    print(f"""
{C.bold('GitHub Agent -- Gestion complete GitHub (CI, PR, Release, Issues)')}

{C.bold('CI/CD :')}
  python agents/github-agent.py ci run [--suite=all]     Declenche le workflow API tests
  python agents/github-agent.py ci watch [--run-id=X]    Surveille un run en cours
  python agents/github-agent.py ci results [--run-id=X]  Telecharge les artifacts Allure
  python agents/github-agent.py ci list                   Liste les derniers runs
  python agents/github-agent.py ci full [--suite=all]    Pipeline complet run+watch+results+Jira

{C.bold('Pull Requests :')}
  python agents/github-agent.py pr create [--base=main]  Cree une PR (description LLM)
  python agents/github-agent.py pr list                   Liste les PRs ouvertes
  python agents/github-agent.py pr merge <id>             Merge une PR (squash)
  python agents/github-agent.py pr view <id>              Affiche les details

{C.bold('Releases :')}
  python agents/github-agent.py release create <v1.4.0>  Cree une release taguee (notes LLM)
  python agents/github-agent.py release list              Liste toutes les releases

{C.bold('Issues :')}
  python agents/github-agent.py issue create              Cree une issue (depuis echecs Allure)
  python agents/github-agent.py issue list                Liste les issues ouvertes
  python agents/github-agent.py issue close <id>          Ferme une issue

{C.bold('Divers :')}
  python agents/github-agent.py status                    Etat general : PRs + CI + releases
  python agents/github-agent.py changelog                 Genere CHANGELOG.md via LLM
  python agents/github-agent.py workflow list             Liste les workflows disponibles
  python agents/github-agent.py secrets list              Liste les noms des secrets GitHub

{C.bold('Options :')}
  --dry-run        Simulation sans ecriture
  --suite=X        Suite CI : all, auth, booking_list, booking_get, booking_create,
                              booking_update, booking_patch, booking_delete, health
  --run-id=X       ID d'un run GitHub Actions specifique
  --base=X         Branche cible PR (defaut : main)
  --branch=X       Branche source pour workflow_dispatch
  --timeout=N      Timeout watch en minutes (defaut : 30)
""")


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    cmd  = args[0] if args else "help"
    sub  = args[1] if len(args) > 1 else ""
    arg3 = args[2] if len(args) > 2 else ""

    repo = get_repo()
    print(f"\n{C.bold('╔══════════════════════════════════════════════════╗')}")
    print(f"{C.bold('║          GITHUB AGENT -- ' + repo[:24].ljust(24) + '  ║')}")
    print(f"{C.bold('╚══════════════════════════════════════════════════╝')}")
    if DRY_RUN:
        print(C.warn("  [DRY-RUN] -- aucune ecriture"))
    print()

    # CI
    if cmd == "ci":
        if sub == "run":       cmd_ci_run()
        elif sub == "watch":   cmd_ci_watch()
        elif sub == "results": cmd_ci_results()
        elif sub == "list":    cmd_ci_list()
        elif sub == "full":    cmd_ci_full()
        else:
            print(C.err(f"  [ERR] Sous-commande ci inconnue : {sub}"))
            print(f"  Disponibles : run, watch, results, list, full")

    # PR
    elif cmd == "pr":
        if sub == "list":       cmd_pr_list()
        elif sub == "create":   cmd_pr_create()
        elif sub == "merge":    cmd_pr_merge(arg3 or sub)
        elif sub == "view":     cmd_pr_view(arg3 or sub)
        else:
            # pr <id> -> view
            if sub.isdigit():   cmd_pr_view(sub)
            else:
                print(C.err(f"  [ERR] Sous-commande pr inconnue : {sub}"))

    # Release
    elif cmd == "release":
        if sub == "list":          cmd_release_list()
        elif sub == "create":      cmd_release_create(arg3)
        else:
            print(C.err(f"  [ERR] Sous-commande release inconnue : {sub}"))
            print(f"  Disponibles : list, create <version>")

    # Issue
    elif cmd == "issue":
        if sub == "list":          cmd_issue_list()
        elif sub == "create":      cmd_issue_create()
        elif sub == "close":       cmd_issue_close(arg3 or sub)
        else:
            if sub.isdigit():      cmd_issue_close(sub)
            else:
                print(C.err(f"  [ERR] Sous-commande issue inconnue : {sub}"))

    # Divers
    elif cmd == "status":          cmd_status()
    elif cmd == "changelog":       cmd_changelog()
    elif cmd == "workflow":        cmd_workflow_list()
    elif cmd == "secrets":         cmd_secrets_list()
    elif cmd in ("help", "-h", "--help"):  print_help()
    else:
        print(C.err(f"  [ERR] Commande inconnue : {cmd}"))
        print_help()


if __name__ == "__main__":
    main()
