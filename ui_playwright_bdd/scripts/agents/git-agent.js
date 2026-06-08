// ============================================
// Git Agent — Commit / Push / PR / Release
// ============================================
// Analyse le diff git, génère un message de commit via Groq,
// pousse sur GitHub et crée optionnellement une PR ou release.
//
// Usage:
//   npm run agent:git                        → commit + push (branche courante)
//   npm run agent:git -- --pr               → commit + push + crée une PR
//   npm run agent:git -- --pr --base=main   → PR vers main (défaut)
//   npm run agent:git -- --release=v1.2.0   → commit + push + GitHub release
//   npm run agent:git -- --status           → résumé du repo sans commit
//   npm run agent:git -- --dry-run  
//         → affiche sans exécuter
//
// Output:
//   Console — résumé des actions effectuées
// ============================================

require('dotenv').config();
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';

const llm  = require('./llm');
const { execSync, spawnSync } = require('child_process');
const path = require('path');
const fs   = require('fs');

const projectRoot = path.resolve(__dirname, '../../../');  // QA_Plateforme/

// ── Arguments CLI ─────────────────────────────────────────────────────────────
const DRY_RUN  = process.argv.includes('--dry-run');
const STATUS   = process.argv.includes('--status');
const CREATE_PR = process.argv.includes('--pr');
const BASE_ARG  = process.argv.find(a => a.startsWith('--base='));
const BASE_BRANCH = BASE_ARG ? BASE_ARG.split('=')[1] : 'main';
const RELEASE_ARG = process.argv.find(a => a.startsWith('--release='));
const RELEASE_TAG = RELEASE_ARG ? RELEASE_ARG.split('=')[1] : null;

// ── Git helpers ───────────────────────────────────────────────────────────────
function git(args, opts = {}) {
  try {
    return execSync(`git ${args}`, {
      cwd: projectRoot,
      encoding: 'utf-8',
      stdio: opts.silent ? 'pipe' : ['pipe', 'pipe', 'pipe']
    }).trim();
  } catch (e) {
    return e.stdout?.trim() || '';
  }
}

function gitStatus() {
  const branch    = git('rev-parse --abbrev-ref HEAD');
  const ahead     = git(`rev-list --count origin/${branch}..HEAD 2>/dev/null || echo 0`);
  const behind    = git(`rev-list --count HEAD..origin/${branch} 2>/dev/null || echo 0`);
  const staged    = git('diff --cached --name-only');
  const unstaged  = git('diff --name-only');
  const untracked = git('ls-files --others --exclude-standard');
  const lastCommit = git('log -1 --format="%h %s"');
  return { branch, ahead: parseInt(ahead)||0, behind: parseInt(behind)||0,
           staged, unstaged, untracked, lastCommit };
}

function getDiff() {
  // diff des fichiers stagés + non stagés (hors binaires)
  const staged   = git('diff --cached --stat');
  const unstaged = git('diff --stat');
  const diffText = git('diff --cached -- . ":(exclude)*.png" ":(exclude)*.jpg" ":(exclude)package-lock.json"');
  return { staged, unstaged, diffText };
}

function stageAll() {
  // Stage tout sauf les exclusions du .gitignore
  git('add -A');
}

// ── Génère le message de commit via Groq ──────────────────────────────────────
async function generateCommitMessage(status, diff) {
  const changedFiles = [
    ...status.staged.split('\n'),
    ...status.unstaged.split('\n'),
    ...status.untracked.split('\n')
  ].filter(Boolean).slice(0, 30).join('\n');

  const messages = [
    {
      role: 'system',
      content: `Tu es un expert Git. Génère un message de commit conventionnel (Conventional Commits).
Format : <type>(<scope>): <description courte en anglais>

Types : feat, fix, docs, style, refactor, test, chore, ci
- Une seule ligne, max 72 caractères
- En anglais
- Précis et factuel
- Pas de point final
Réponds UNIQUEMENT avec le message de commit, rien d'autre.`
    },
    {
      role: 'user',
      content: `Fichiers modifiés :\n${changedFiles}\n\nDiff (extrait) :\n${diff.diffText.slice(0, 3000)}`
    }
  ];

  const resp = await llm.chat(messages);
  return (resp.message?.content || 'chore: update files').trim().replace(/^["']|["']$/g, '');
}

// ── Génère la description de PR via Groq ──────────────────────────────────────
async function generatePRDescription(commitMsg, diff, branch) {
  const messages = [
    {
      role: 'system',
      content: 'Tu es un expert Git/GitHub. Génère une description de Pull Request professionnelle en français au format Markdown.'
    },
    {
      role: 'user',
      content: `Branche : ${branch} → ${BASE_BRANCH}
Commit : ${commitMsg}

Fichiers modifiés :
${diff.staged || diff.unstaged}

Génère une description PR avec :
## Résumé (3 bullets max)
## Changements
## Test`
    }
  ];
  const resp = await llm.chat(messages);
  return resp.message?.content || '';
}

// ── Affiche le statut du repo ─────────────────────────────────────────────────
function printStatus(s) {
  console.log(`\n📍 Branche      : ${s.branch}`);
  console.log(`📤 En avance    : ${s.ahead} commit(s)`);
  console.log(`📥 En retard    : ${s.behind} commit(s)`);
  console.log(`✏️  Dernier      : ${s.lastCommit}`);
  if (s.staged)    console.log(`\n✅ Stagés :\n${s.staged.split('\n').map(f=>'   '+f).join('\n')}`);
  if (s.unstaged)  console.log(`\n📝 Modifiés :\n${s.unstaged.split('\n').map(f=>'   '+f).join('\n')}`);
  if (s.untracked) console.log(`\n❓ Non suivis :\n${s.untracked.split('\n').slice(0,10).map(f=>'   '+f).join('\n')}`);
}

// ── Main ──────────────────────────────────────────────────────────────────────
async function run() {
  await llm.assertRunning();
  console.log(`\n=== GIT AGENT  [${llm.MODEL}] ===`);
  if (DRY_RUN) console.log('   MODE DRY-RUN\n');

  const status = gitStatus();
  printStatus(status);

  // Mode --status uniquement
  if (STATUS) return;

  // Vérifie s'il y a des changements
  const hasChanges = status.staged || status.unstaged || status.untracked;
  if (!hasChanges && !RELEASE_TAG) {
    console.log('\n✅ Aucun changement à committer.');
    if (status.ahead > 0) {
      console.log(`\n📤 ${status.ahead} commit(s) non pushés — push en cours...`);
      if (!DRY_RUN) {
        const res = spawnSync('git', ['-c', 'http.sslVerify=false', 'push', 'origin', status.branch],
          { cwd: projectRoot, encoding: 'utf-8', stdio: 'inherit' });
      }
    }
    return;
  }

  // Stage tout
  if (!DRY_RUN) stageAll();
  const diff = getDiff();

  // Génère le message de commit
  console.log('\n🤖 Génération du message de commit...');
  const commitMsg = await generateCommitMessage(status, diff);
  console.log(`\n📝 Commit : "${commitMsg}"`);

  if (DRY_RUN) {
    console.log('\n[DRY-RUN] Aurait commité et pushé.');
    return;
  }

  // Commit
  const commitResult = spawnSync('git', ['commit', '-m', commitMsg,
    '--author=git-agent <git-agent@qa-plateforme>'],
    { cwd: projectRoot, encoding: 'utf-8', stdio: 'pipe' });

  if (commitResult.status !== 0) {
    // Rien à committer ? On continue quand même si ahead > 0
    if (!commitResult.stdout?.includes('nothing to commit')) {
      console.error('❌ Commit échoué:', commitResult.stderr);
      process.exit(1);
    }
  } else {
    console.log(`✅ Commit créé`);
  }

  // Push
  console.log(`\n📤 Push → origin/${status.branch}...`);
  const pushResult = spawnSync('git', ['-c', 'http.sslVerify=false', 'push', 'origin', status.branch],
    { cwd: projectRoot, encoding: 'utf-8', stdio: 'inherit' });

  if (pushResult.status !== 0) {
    console.error('❌ Push échoué');
    process.exit(1);
  }
  console.log('✅ Push réussi');

  // Crée une PR
  if (CREATE_PR) {
    console.log('\n🔀 Génération de la description PR...');
    const prDesc = await generatePRDescription(commitMsg, diff, status.branch);

    console.log('\n📬 Création de la PR...');
    const prResult = spawnSync('gh', ['pr', 'create',
      '--title', commitMsg,
      '--body', prDesc,
      '--base', BASE_BRANCH,
      '--head', status.branch
    ], { cwd: projectRoot, encoding: 'utf-8', stdio: 'pipe' });

    if (prResult.status === 0) {
      const prUrl = prResult.stdout.trim();
      console.log(`✅ PR créée : ${prUrl}`);
    } else {
      // PR existe peut-être déjà
      const errMsg = prResult.stderr || '';
      if (errMsg.includes('already exists')) {
        console.log('⚠️  Une PR existe déjà pour cette branche.');
      } else {
        console.error('❌ PR échouée:', errMsg.slice(0, 200));
      }
    }
  }

  // Crée une GitHub Release
  if (RELEASE_TAG) {
    console.log(`\n🏷️  Création du tag ${RELEASE_TAG}...`);
    spawnSync('git', ['tag', RELEASE_TAG], { cwd: projectRoot, stdio: 'inherit' });
    spawnSync('git', ['-c', 'http.sslVerify=false', 'push', 'origin', RELEASE_TAG],
      { cwd: projectRoot, encoding: 'utf-8', stdio: 'inherit' });

    console.log(`🚀 Création de la GitHub Release ${RELEASE_TAG}...`);
    const releaseNotes = await generateCommitMessage(status, diff);
    const relResult = spawnSync('gh', ['release', 'create', RELEASE_TAG,
      '--title', `Release ${RELEASE_TAG}`,
      '--notes', `## ${RELEASE_TAG}\n\n${releaseNotes}`,
      '--repo', 'Faicel-Testing/qa-plateforme'
    ], { cwd: projectRoot, encoding: 'utf-8', stdio: 'pipe' });

    if (relResult.status === 0) {
      console.log(`✅ Release : ${relResult.stdout.trim()}`);
    } else {
      console.error('❌ Release échouée:', relResult.stderr?.slice(0, 200));
    }
  }
}

run().catch(err => { console.error('Git agent error:', err.message || err); process.exit(1); });
