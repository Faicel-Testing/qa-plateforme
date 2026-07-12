'use strict';
// ============================================================
// CI Agent — GitHub CI/CD + Git
// ============================================================
// Usage:
//   node scripts/agents/ci-agent.js ci run [--suite=X]    Déclenche le workflow GitHub Actions
//   node scripts/agents/ci-agent.js ci watch [--run-id=X] Surveille un run CI
//   node scripts/agents/ci-agent.js ci list               Liste les derniers runs
//   node scripts/agents/ci-agent.js pr create [--base=X]  Crée une PR (description LLM)
//   node scripts/agents/ci-agent.js pr list               Liste les PRs ouvertes
//   node scripts/agents/ci-agent.js pr merge <id>         Merge une PR (squash)
//   node scripts/agents/ci-agent.js release create <v>    Crée une release taguée (notes LLM)
//   node scripts/agents/ci-agent.js release list          Liste les releases
//   node scripts/agents/ci-agent.js git commit            Commit auto avec message LLM
//   node scripts/agents/ci-agent.js git push              Push la branche courante
//   node scripts/agents/ci-agent.js git status             Affiche l'état du repo
//   node scripts/agents/ci-agent.js status                Vue d'ensemble repo + CI + PRs
//
// Coût LLM : bas — uniquement pour commit message, PR description, release notes
// ============================================================
require('dotenv').config();
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';

const { execSync, spawnSync } = require('child_process');
const fs   = require('fs');
const path = require('path');
const llm  = require('./llm');
const tracer = require('./shared/tracer');

const FRAMEWORK      = path.join(__dirname, '..', '..');
const WORKFLOW_FILE  = process.env.CI_WORKFLOW || 'ci-k6-performance.yml';
const POLL_INTERVAL  = 10000;
const TIMEOUT_MIN    = parseInt(process.argv.find(a=>a.startsWith('--timeout='))?.split('=')[1]||'30');
const DRY_RUN        = process.argv.includes('--dry-run');
const BASE_BRANCH    = process.argv.find(a=>a.startsWith('--base='))?.split('=')[1] || 'main';
const RUN_ID_ARG     = process.argv.find(a=>a.startsWith('--run-id='))?.split('=')[1] || null;

const G = '\x1b[32m', R = '\x1b[31m', Y = '\x1b[33m', C = '\x1b[36m', B = '\x1b[1m', E = '\x1b[0m';

function sh(cmd, opts = {}) {
  try {
    return { ok: true, out: execSync(cmd, { cwd: FRAMEWORK, encoding: 'utf8', ...opts }).trim() };
  } catch (e) {
    return { ok: false, out: '', err: (e.stderr || e.message || '').slice(0,200) };
  }
}

function ghJson(args) {
  const r = sh(`gh ${args}`);
  if (!r.ok) return null;
  try { return JSON.parse(r.out); } catch { return null; }
}

function git(args) { return sh(`git ${args}`).out; }

function getCurrentBranch() { return git('rev-parse --abbrev-ref HEAD'); }
function getRepo() {
  const data = ghJson('repo view --json nameWithOwner');
  return data?.nameWithOwner || 'unknown/unknown';
}

// ── STATUS ────────────────────────────────────────────────────────────────────
function cmdStatus() {
  console.log(`\n${B}=== CI — STATUS REPO ===${E}`);
  const repo   = getRepo();
  const branch = getCurrentBranch();
  const last   = git('log -1 --format="%h %s (%cr)"');
  console.log(`\n  Repo    : ${B}${repo}${E}`);
  console.log(`  Branche : ${C}${branch}${E}`);
  console.log(`  Dernier : \x1b[2m${last}\x1b[0m`);

  const prs  = ghJson('pr list --state open --json number,title,headRefName') || [];
  console.log(`\n  PRs ouvertes : ${prs.length}`);
  prs.slice(0,5).forEach(pr => console.log(`    #${pr.number}  ${pr.title?.slice(0,50)}  [${pr.headRefName}]`));

  const runs = ghJson(`run list --workflow=${WORKFLOW_FILE} --limit=3 --json databaseId,status,conclusion,headBranch,createdAt`) || [];
  console.log(`\n  Derniers runs CI :`);
  if (!runs.length) console.log(`    \x1b[2mAucun run trouvé\x1b[0m`);
  runs.forEach(r => {
    const icon = r.conclusion === 'success' ? G+'[OK]'+E : r.conclusion === 'failure' ? R+'[FAIL]'+E : Y+`[${(r.status||'?').toUpperCase()}]`+E;
    console.log(`    ${icon}  #${r.databaseId}  [${r.headBranch}]  ${r.createdAt?.slice(0,10)}`);
  });
}

// ── CI RUN ────────────────────────────────────────────────────────────────────
function cmdCiRun() {
  console.log(`\n${B}=== CI — RUN WORKFLOW ===${E}`);
  const branch = getCurrentBranch();
  console.log(`  Workflow : ${WORKFLOW_FILE}\n  Branche  : ${C}${branch}${E}`);
  if (DRY_RUN) { console.log(`  ${Y}[DRY-RUN] Workflow non déclenché${E}`); return; }

  const r = sh(`gh workflow run ${WORKFLOW_FILE} --ref ${branch}`);
  if (!r.ok) { console.error(`  ${R}✗ ${r.err}${E}`); return; }
  console.log(`  ${G}✓ Workflow déclenché${E}`);
}

// ── CI WATCH ──────────────────────────────────────────────────────────────────
async function cmdCiWatch(runId) {
  console.log(`\n${B}=== CI — WATCH ===${E}`);
  const id = runId || RUN_ID_ARG || ghJson(`run list --workflow=${WORKFLOW_FILE} --limit=1 --json databaseId`)?.[0]?.databaseId;
  if (!id) { console.error(`  ${R}✗ Aucun run ID trouvé${E}`); return; }
  console.log(`  Run ID : ${B}${id}${E}`);

  const deadline = Date.now() + TIMEOUT_MIN * 60 * 1000;
  let last = '';
  while (Date.now() < deadline) {
    const data = ghJson(`run view ${id} --json status,conclusion,displayTitle`);
    if (!data) { await sleep(POLL_INTERVAL); continue; }
    if (data.status !== last) {
      last = data.status;
      const icon = data.conclusion === 'success' ? G+'[OK]'+E : data.conclusion === 'failure' ? R+'[FAIL]'+E : Y+`[${data.status}]`+E;
      console.log(`  ${icon}  ${data.displayTitle?.slice(0,50)||''}`);
    }
    if (data.status === 'completed') {
      console.log(data.conclusion === 'success' ? `\n  ${G}✓ Run terminé avec succès${E}` : `\n  ${R}✗ Run échoué${E}`);
      return data.conclusion;
    }
    await sleep(POLL_INTERVAL);
  }
  console.log(`  ${Y}⚠  Timeout (${TIMEOUT_MIN} min)${E}`);
}

// ── PR CREATE ─────────────────────────────────────────────────────────────────
async function cmdPrCreate() {
  console.log(`\n${B}=== CI — PR CREATE [${llm.MODEL}] ===${E}`);
  const branch = getCurrentBranch();
  const base   = BASE_BRANCH;
  if (branch === base) { console.log(`  ${Y}⚠  Déjà sur ${base}${E}`); return; }

  const diff  = git(`log --oneline ${base}..${branch}`).slice(0, 2000);
  const files = git(`diff --name-only ${base}..${branch}`).slice(0, 800);

  console.log(`  ${C}Génération description PR via LLM...${E}`);
  const span = new tracer.Span('prCreate', diff, llm.MODEL).begin();
  try {
    const prompt = `Génère un titre et une description de Pull Request Markdown.

Branche: ${branch} → ${base}
Commits:\n${diff}
Fichiers:\n${files}

Réponds UNIQUEMENT avec ce JSON:
{"title":"titre court (<70 chars)","body":"## Summary\\n...\\n## Changes\\n...\\n## Test plan\\n..."}`;

    const resp = await llm.chat([{ role: 'user', content: prompt }]);
    const raw  = resp.message.content || '';
    const m    = raw.match(/\{[\s\S]*\}/);
    let title = `feat: ${branch}`, body = `Changes from \`${branch}\` to \`${base}\``;
    if (m) { try { ({ title, body } = JSON.parse(m[0])); } catch {} }
    span.end(true);

    console.log(`  Titre : ${B}${title}${E}`);
    if (DRY_RUN) { console.log(`  ${Y}[DRY-RUN] PR non créée${E}`); return; }

    const tmp = path.join(FRAMEWORK, '_pr_body.md');
    fs.writeFileSync(tmp, body, 'utf8');
    const r = sh(`gh pr create --title "${title.replace(/"/g,'')}" --body-file "${tmp}" --base ${base} --head ${branch}`);
    fs.unlinkSync(tmp);
    if (r.ok) console.log(`  ${G}✓ PR créée : ${r.out}${E}`);
    else console.error(`  ${R}✗ ${r.err}${E}`);
  } catch (e) {
    span.error = e.message; span.end(false);
    console.error(`  ${R}✗ ${e.message}${E}`);
  }
}

// ── RELEASE CREATE ────────────────────────────────────────────────────────────
async function cmdReleaseCreate(version) {
  console.log(`\n${B}=== CI — RELEASE ${version} [${llm.MODEL}] ===${E}`);
  if (!version) { console.log(`  Usage: ci release create v2.0.0`); return; }

  const lastTag = git('describe --tags --abbrev=0 2>/dev/null || true') || '';
  const log     = lastTag ? git(`log ${lastTag}..HEAD --oneline --no-merges`).slice(0,3000) : git('log --oneline -20');

  const span = new tracer.Span('releaseNotes', log, llm.MODEL).begin();
  try {
    const prompt = `Génère des release notes Markdown professionnelles pour ${version}.

Commits depuis ${lastTag||'le début'}:\n${log}

Format:
## Quoi de neuf\n- ...\n## Corrections\n- ...\n\nRéponds UNIQUEMENT avec le Markdown.`;

    const resp  = await llm.chat([{ role: 'user', content: prompt }]);
    const notes = resp.message.content || `Release ${version}`;
    span.end(true);

    console.log(`  Version  : ${B}${version}${E}\n  Précédent: \x1b[2m${lastTag||'aucun'}\x1b[0m`);
    if (DRY_RUN) { console.log(`\n  ${Y}[DRY-RUN]\x1b[0m\n${notes.slice(0,300)}`); return; }

    const tmp = path.join(FRAMEWORK, '_release_notes.md');
    fs.writeFileSync(tmp, notes, 'utf8');
    if (!git(`tag -l ${version}`)) sh(`git tag -a ${version} -m "Release ${version}"`);
    sh(`git push origin ${version}`);
    const r = sh(`gh release create ${version} --title "${version}" --notes-file "${tmp}" --latest`);
    fs.unlinkSync(tmp);
    if (r.ok) console.log(`  ${G}✓ Release : ${r.out}${E}`);
    else console.error(`  ${R}✗ ${r.err}${E}`);
  } catch (e) {
    span.error = e.message; span.end(false);
    console.error(`  ${R}✗ ${e.message}${E}`);
  }
}

// ── GIT COMMIT ────────────────────────────────────────────────────────────────
async function cmdGitCommit() {
  console.log(`\n${B}=== CI — GIT COMMIT [${llm.MODEL}] ===${E}`);
  const diff = sh('git diff --cached --stat').out || sh('git diff --stat').out;
  if (!diff) { console.log(`  ${Y}⚠  Rien à committer${E}`); return; }

  const span = new tracer.Span('gitCommit', diff, llm.MODEL).begin();
  try {
    const prompt = `Génère un message de commit git conventionnel (max 72 chars).
Format: type(scope): description
Types: feat, fix, test, chore, refactor, docs

Changements:\n${diff.slice(0,800)}

Réponds UNIQUEMENT avec le message de commit, pas de ponctuation finale.`;

    const resp = await llm.chat([{ role: 'user', content: prompt }]);
    const msg  = (resp.message.content || '').trim().split('\n')[0].slice(0,72);
    span.end(true);

    console.log(`  ${C}Message : ${msg}${E}`);
    if (DRY_RUN) { console.log(`  ${Y}[DRY-RUN] Commit non effectué${E}`); return; }

    sh('git add -A');
    const r = sh(`git commit -m "${msg.replace(/"/g, "'")}"`);
    if (r.ok) console.log(`  ${G}✓ Commit créé${E}`);
    else console.error(`  ${R}✗ ${r.err}${E}`);
  } catch (e) {
    span.error = e.message; span.end(false);
    console.error(`  ${R}✗ ${e.message}${E}`);
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function cmdPrList() {
  const prs = ghJson('pr list --state open --json number,title,headRefName,baseRefName,createdAt') || [];
  console.log(`\n${B}=== CI — PRs OUVERTES (${prs.length}) ===${E}`);
  prs.forEach(pr => console.log(`  #${String(pr.number).padEnd(4)} ${pr.headRefName} → ${pr.baseRefName}  ${pr.title?.slice(0,45)}`));
}

function cmdReleaseList() {
  const releases = ghJson('release list --limit=10 --json tagName,name,publishedAt,isLatest') || [];
  console.log(`\n${B}=== CI — RELEASES ===${E}`);
  releases.forEach(r => console.log(`  ${r.tagName.padEnd(12)} ${r.isLatest?G+'[latest]'+E:'        '}  ${r.publishedAt?.slice(0,10)}  ${r.name?.slice(0,40)}`));
}

function cmdCiList() {
  const runs = ghJson(`run list --workflow=${WORKFLOW_FILE} --limit=10 --json databaseId,status,conclusion,headBranch,createdAt`) || [];
  console.log(`\n${B}=== CI — RUNS ===${E}`);
  runs.forEach(r => {
    const icon = r.conclusion==='success'?G+'[OK]'+E:r.conclusion==='failure'?R+'[FAIL]'+E:Y+`[${r.status}]`+E;
    console.log(`  ${icon}  #${String(r.databaseId).padEnd(10)} [${r.headBranch}]  ${r.createdAt?.slice(0,10)}`);
  });
}

// ── Main ──────────────────────────────────────────────────────────────────────
async function main() {
  const args = process.argv.slice(2).filter(a => !a.startsWith('--'));
  const [cmd, sub, arg3] = args;
  await llm.assertRunning();

  if (cmd === 'ci') {
    if (sub === 'run')   { cmdCiRun(); }
    else if (sub === 'watch') { await cmdCiWatch(arg3); }
    else if (sub === 'list')  { cmdCiList(); }
    else console.log(`  Sous-commandes ci: run, watch, list`);
  } else if (cmd === 'pr') {
    if (sub === 'create')     { await cmdPrCreate(); }
    else if (sub === 'list')  { cmdPrList(); }
    else if (sub === 'merge') {
      if (!arg3) { console.log('  Usage: ci pr merge <id>'); return; }
      if (!DRY_RUN) { const r = sh(`gh pr merge ${arg3} --squash --delete-branch`); console.log(r.ok ? `  ${G}✓ PR #${arg3} mergée${E}` : `  ${R}✗ ${r.err}${E}`); }
    }
    else console.log(`  Sous-commandes pr: create, list, merge <id>`);
  } else if (cmd === 'release') {
    if (sub === 'create') { await cmdReleaseCreate(arg3); }
    else if (sub === 'list') { cmdReleaseList(); }
    else console.log(`  Sous-commandes release: create <version>, list`);
  } else if (cmd === 'git') {
    if (sub === 'commit')     { await cmdGitCommit(); }
    else if (sub === 'push')  { if (!DRY_RUN) { const r = sh('git push'); console.log(r.ok ? `  ${G}✓ Push OK${E}` : `  ${R}✗ ${r.err}${E}`); } }
    else if (sub === 'status'){ console.log(sh('git status --short').out); }
    else console.log(`  Sous-commandes git: commit, push, status`);
  } else if (cmd === 'status') {
    cmdStatus();
  } else {
    console.log(`
${B}CI Agent${E} — GitHub CI/CD + Git

  ci run [--suite=X]       Déclenche le workflow GitHub Actions
  ci watch [--run-id=X]    Surveille un run CI
  ci list                  Liste les derniers runs

  pr create [--base=main]  Crée une PR avec description LLM
  pr list                  Liste les PRs ouvertes
  pr merge <id>            Merge une PR (squash)

  release create <v1.0.0>  Crée une release taguée (notes LLM)
  release list             Liste les releases

  git commit               Commit avec message LLM
  git push                 Push la branche courante
  git status                État du repo

  status                   Vue d'ensemble : repo + CI + PRs + releases

Options:
  --dry-run                Simulation sans écriture
  --base=<branch>          Branche cible PR (défaut: main)
  --run-id=<id>            ID d'un run CI spécifique
  --timeout=N              Timeout watch en minutes (défaut: 30)
`);
  }
}

main().catch(e => { console.error(R + e.message + E); process.exit(1); });
