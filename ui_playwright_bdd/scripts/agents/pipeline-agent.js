'use strict';
// ============================================================
// Pipeline Agent — Orchestrateur maître
// ============================================================
// Master orchestrator : exécute les agents dans l'ordre optimal
//
// Usage:
//   node scripts/agents/pipeline-agent.js full           Pipeline complet (tous les agents)
//   node scripts/agents/pipeline-agent.js quick          Pipeline rapide (runner+quality+reporting)
//   node scripts/agents/pipeline-agent.js report         Rapport de pipeline uniquement
//   node scripts/agents/pipeline-agent.js status         État de santé de tous les agents
//
// Coût LLM : dépend des agents invoqués (aucun LLM propre à cet agent)
// ============================================================
require('dotenv').config();

const fs   = require('fs');
const path = require('path');
const runtime = require('./shared/pipeline-runtime');
const { readVerification } = require('./shared/agent-verifier');

const AGENTS_DIR = __dirname;
const FRAMEWORK  = path.join(__dirname, '..', '..');
const DOCS_DIR   = path.join(FRAMEWORK, 'docs');
const LOG_DIR    = path.join(FRAMEWORK, 'logs');

fs.mkdirSync(DOCS_DIR, { recursive: true });
fs.mkdirSync(LOG_DIR,  { recursive: true });

const DRY_RUN   = process.argv.includes('--dry-run');
const VERBOSE   = process.argv.includes('--verbose');
const NO_TESTS  = process.argv.includes('--no-tests');

const G = '\x1b[32m', R = '\x1b[31m', Y = '\x1b[33m', C = '\x1b[36m', B = '\x1b[1m', E = '\x1b[0m';
const validationLabel = status => ({ PENDING_APPROVAL: 'EN ATTENTE D’APPROBATION', REJECTED: 'REJETÉ',
  BLOCKED: 'BLOQUÉ', NOT_EVALUATED: 'NON ÉVALUÉ', PASS: 'VALIDÉ' }[status] || status);

// ── Utilitaire d'exécution d'agent ────────────────────────────────────────────
async function runAgent(agentFile, args = [], label = '', env = process.env, logDir = LOG_DIR) {
  const name = label || path.basename(agentFile, '.js');
  const start = Date.now();
  console.log(`\n${C}▶ ${name}${args.length ? ' ' + args.join(' ') : ''}${E}`);

  if (DRY_RUN) {
    console.log(`  ${Y}[DRY-RUN] skipped${E}`);
    return { success: false, durationMs: 0, skipped: true };
  }

  const verificationFile = path.join(logDir, `${path.basename(agentFile, '.js')}-${require('crypto').randomUUID()}.verification.jsonl`);
  const decisionFile = verificationFile + '.decision.json';
  const entryArgs = env.QA_AGENT_RUNTIME === 'python'
    // Native advisor gates tests only. Preserve this legacy pipeline's human release checks.
    ? [path.join(FRAMEWORK, 'scripts', 'python-agents.cjs'), agentFile === 'advisor-agent.js' ? 'advisor-legacy' : agentFile.replace(/-agent\.js$/, ''), ...args]
    : [path.join(AGENTS_DIR, agentFile), ...args];
  const result = await runtime.execute(process.execPath, entryArgs, {
    cwd: FRAMEWORK,
    env: { ...env, QA_VERIFICATION_FILE: verificationFile, QA_DECISION_FILE: decisionFile }, verbose: VERBOSE,
    logFile: path.join(logDir, `${path.basename(agentFile, '.js')}-${args[0] || 'run'}.log`),
    timeout: agentFile === 'runner-agent.js'
      ? runtime.timeoutMs(env.RUNNER_TIMEOUT_MS, 1800000) + 30000
      : agentFile === 'quality-agent.js' && args[0] === 'full'
        ? runtime.timeoutMs(env.QUALITY_TIMEOUT_MS || env.AGENT_TIMEOUT_MS, 900000)
      : agentFile === 'bug-agent.js'
        ? runtime.timeoutMs(env.BUG_TIMEOUT_MS || env.AGENT_TIMEOUT_MS, 600000)
      : runtime.timeoutMs(env.AGENT_TIMEOUT_MS, 300000),
  });

  const durationMs = Date.now() - start;
  const verification = readVerification(verificationFile);
  runtime.recordVerification?.(result.metricsTaskId, verification.status, env);
  const success = result.success && verification.status !== 'REJECTED';
  let decision;
  // Consume a per-invocation record, never infer approval state from arbitrary log text.
  if (agentFile === 'advisor-agent.js' && !result.timedOut && !result.error && verification.status !== 'REJECTED' && fs.existsSync(decisionFile)) {
    try {
      const record = JSON.parse(fs.readFileSync(decisionFile, 'utf8'));
      if (record.schemaVersion === 1 && record.runId === env.QA_RUN_ID && typeof record.reason === 'string' &&
          ((record.status === 'PENDING_APPROVAL' && result.exitCode === 2) ||
           (['REJECTED', 'BLOCKED'].includes(record.status) && result.exitCode === 1))) decision = record;
    } catch { /* Invalid status records remain technical failures. */ }
  }
  const pendingApproval = decision?.status === 'PENDING_APPROVAL';
  const rejected = decision?.status === 'REJECTED';
  const blocked = decision?.status === 'BLOCKED';

  if (success) {
    console.log(`  ${G}✓ Terminé en ${(durationMs/1000).toFixed(1)}s${E}`);
    if (VERBOSE && result.stdout) console.log(result.stdout.slice(-300));
  } else if (decision) {
    console.log(`  ${Y}${validationLabel(decision.status)} — ${decision.reason}${E}`);
  } else {
    console.log(`  ${R}✗ Échec (${result.timedOut ? 'timeout' : result.exitCode ?? result.error}) en ${(durationMs/1000).toFixed(1)}s${E}`);
    const errOut = [result.stdout, result.stderr].filter(Boolean).map(text => text.slice(-2200)).join('\n');
    if (errOut) console.log(`  ${R}${errOut}${E}`);
  }

  return { name, ...result, success, durationMs, verification, pendingApproval, rejected, blocked, reason: decision?.reason };
}

// ── Étapes de pipeline ────────────────────────────────────────────────────────
const PIPELINE_STEPS = {
  // Pipeline complet — ordre optimal
  full: [
    { file: 'planning-agent.js',     args: ['coverage', 'analyze'], label: 'Planning → Analyse couverture' },
    { file: 'codegen-agent.js',      args: ['spec'],                label: 'Codegen → Génération specs' },
    { file: 'runner-agent.js',       args: ['run'],                 label: 'Runner → Exécution tests',      skipIfNoTests: true },
    { file: 'allure-agent.js', args: ['generate'], label: 'Allure → Rapport des tests' },
    { file: 'quality-agent.js',      args: ['full'],                label: 'Quality → Triage + RCA' },
    { file: 'bug-agent.js',          args: ['analyze'],             label: 'Bug → Analyse échecs' },
    { file: 'reporting-agent.js',    args: ['dashboard'],           label: 'Reporting → Dashboard KPI' },
    { file: 'reporting-agent.js',    args: ['sync'],                label: 'Reporting → Sync Plane' },
    { file: 'advisor-agent.js',      args: ['advise'],              label: 'Advisor → Recommandation GO/NO-GO' },
    { file: 'observability-agent.js',args: ['metrics'],             label: 'Observability → Métriques' },
    { file: 'ci-agent.js',           args: ['status'],              label: 'CI → État pipeline GitHub' },
    { file: 'advisor-agent.js', args: ['gate'], label: 'Advisor → Quality gate' },
  ],

  // Pipeline rapide — post-run essentiels
  quick: [
    { file: 'runner-agent.js',    args: ['smoke'],       label: 'Runner → Exécution smoke', skipIfNoTests: true },
    { file: 'allure-agent.js', args: ['generate'], label: 'Allure → Rapport des tests' },
    { file: 'quality-agent.js',   args: ['triage'],      label: 'Quality → Triage rapide' },
    { file: 'reporting-agent.js', args: ['dashboard'],   label: 'Reporting → Dashboard KPI' },
    { file: 'advisor-agent.js',   args: ['gate'],        label: 'Advisor → Quality gate' },
  ],

  // Rapport uniquement (sans exécution)
  report: [
    { file: 'allure-agent.js', args: ['generate'], label: 'Allure → Rapport des tests' },
    { file: 'quality-agent.js',      args: ['full'],      label: 'Quality → Analyse complète' },
    { file: 'bug-agent.js',          args: ['report'],    label: 'Bug → Rapport bugs' },
    { file: 'reporting-agent.js',    args: ['dashboard'], label: 'Reporting → Dashboard KPI' },
    { file: 'observability-agent.js',args: ['report'],    label: 'Observability → Rapport traces' },
  ],
};

// ── Exécution du pipeline ─────────────────────────────────────────────────────
async function runPipeline(mode) {
  const steps   = PIPELINE_STEPS[mode];
  const startTs = Date.now();
  const results = [];
  const runId = `${Date.now()}-${require('crypto').randomUUID()}`;
  const logDir = path.join(LOG_DIR, 'pipeline', runId);
  const fresh = mode !== 'report' && !NO_TESTS;
  const resultsDir = fresh ? path.join(FRAMEWORK, 'allure-runs', runId, 'results') : runtime.resultDirectory(FRAMEWORK);
  const env = { ...process.env, ALLURE_RESULTS_DIR: resultsDir };
  if (fresh) { env.QA_RUN_ID = runId; env.QA_EXECUTION_MANAGED = 'true'; }
  else delete env.QA_RUN_ID;
  if (!DRY_RUN) {
    fs.mkdirSync(logDir, { recursive: true });
    if (fresh) {
      fs.mkdirSync(resultsDir, { recursive: true });
      fs.writeFileSync(path.join(resultsDir, 'run-manifest.json'), JSON.stringify({ runId, completed: false, startedAt: Date.now() }));
      fs.writeFileSync(path.join(LOG_DIR, 'latest-test-run.json'), JSON.stringify({ runId }));
    }
  }

  console.log(`\n${B}${'═'.repeat(60)}${E}`);
  console.log(`${B}  PIPELINE AGENT — ${mode.toUpperCase()}${E}`);
  console.log(`${B}${'═'.repeat(60)}${E}`);
  console.log(`  ${steps.length} étapes | ${new Date().toLocaleString('fr-FR')}\n`);

  for (const step of steps) {
    if (step.skipIfNoTests && NO_TESTS) {
      console.log(`  ${Y}⊘ ${step.label} — skipped (--no-tests)${E}`);
      results.push({ name: step.label, success: false, skipped: true, durationMs: 0 });
      continue;
    }
    if (step.file === 'reporting-agent.js' && step.args[0] === 'sync' && !process.argv.includes('--sync-plane')) {
      results.push({ name: step.label, success: false, skipped: true, durationMs: 0, reason: 'External sync disabled; use --sync-plane' });
      continue;
    }
    const decision = step.file === 'advisor-agent.js';
    if (decision && results.some(r => ['REJECTED', 'UNVERIFIED'].includes(r.verification?.status))) {
      results.push({ name: step.label, success: false, blocked: true,
        reason: 'Prior AI outputs are rejected or unverified; no automated release decision.', durationMs: 0 });
      continue;
    }
    const needsResults = ['quality-agent.js', 'bug-agent.js', 'reporting-agent.js'].includes(step.file);
    if (!DRY_RUN && decision) {
      const check = runtime.checkRun(resultsDir, fresh ? runId : undefined);
      const previousFailure = results.some(r => !r.success && !r.skipped && !r.pendingApproval);
      if (!fresh || !check.allowed || previousFailure) {
        const reason = !fresh ? 'No new test execution: release validation disabled'
          : [...check.reasons, ...(previousFailure ? ['A required pipeline step failed'] : [])].join('; ');
        console.error(`BLOCKED: ${step.label}: ${reason}`);
        results.push({ name: step.label, success: false, blocked: true, reason, durationMs: 0 });
        continue;
      }
    }
    if (!DRY_RUN && needsResults && !runtime.readResults(resultsDir).results.length) {
      results.push({ name: step.label, success: false, blocked: true, reason: 'No results for this execution', durationMs: 0 });
      continue;
    }
    const r = await runAgent(step.file, step.args, step.label, env, logDir);
    results.push({ name: step.label, ...r });
    if (step.file === 'codegen-agent.js' && !DRY_RUN) {
      console.log('Codegen produit uniquement des propositions a revoir. Le runner execute les sources existantes, pas ces propositions.');
      if (!r.success) console.log('Generation incomplete : les tests existants peuvent etre executes, mais la validation globale restera bloquee.');
    }
  }

  const totalMs = Date.now() - startTs;
  const ok      = results.filter(r => r.success && !r.skipped).length;
  const ko      = results.filter(r => !r.success && !r.skipped && !r.blocked && !r.pendingApproval && !r.rejected).length;
  const blocked = results.filter(r => r.blocked).length;
  const pendingApproval = results.filter(r => r.pendingApproval).length;
  const rejected = results.filter(r => r.rejected).length;
  const testData = !DRY_RUN && fresh ? runtime.readResults(resultsDir) : { results: [], errors: [] };
  const testSummary = { total: testData.results.length, passed: testData.results.filter(r => r.status === 'passed').length,
    complete: !DRY_RUN && fresh && runtime.checkRun(resultsDir, runId).manifest?.completed === true && !testData.errors.length };

  console.log(`\n${B}${'═'.repeat(60)}${E}`);
  console.log(`TESTS BDD : ${testSummary.total ? `${testSummary.passed}/${testSummary.total} réussis` : 'NON ÉVALUÉS'}${testSummary.total && !testSummary.complete ? ' (résultats incomplets)' : ''}`);
  console.log(`${B}  PIPELINE${E}   ${G}${ok}/${results.length} étapes terminées${E}   ${ko} ÉCHEC(S)   ${blocked} BLOQUÉ(S)   ${rejected} REJETÉ(S)   ${pendingApproval} EN ATTENTE D’APPROBATION   ${(totalMs/1000).toFixed(1)}s`);
  console.log(`${B}${'═'.repeat(60)}${E}\n`);

  results.forEach(r => {
    const icon = r.pendingApproval ? Y+'EN ATTENTE D’APPROBATION'+E : r.rejected ? R+'REJETÉ'+E : r.blocked ? Y+'BLOQUÉ'+E : r.skipped ? Y+'⊘'+E : r.success ? G+'✓'+E : R+'ÉCHEC'+E;
    console.log(`  ${icon}  ${(r.name||'').slice(0,50).padEnd(52)} ${((r.durationMs||0)/1000).toFixed(1).padStart(5)}s`);
    if (r.reason) console.log(`    Motif : ${r.reason}`);
  });

  // Sauvegarde du résumé
  const summary = {
    mode, runId, resultsDir, logDir, timestamp: new Date().toISOString(), totalMs,
    validation: DRY_RUN || !fresh ? 'NOT_EVALUATED' : ko ? 'BLOCKED'
      : rejected ? 'REJECTED' : blocked ? 'BLOCKED' : pendingApproval ? 'PENDING_APPROVAL'
      : results.some(r => r.verification?.status === 'UNVERIFIED') ? 'NOT_EVALUATED' : 'PASS',
    ok, ko, blocked, pendingApproval, rejected, testSummary, steps: results.length,
    skipped: results.filter(r => r.skipped).length,
    results: results.map(({ stdout, stderr, ...r }) => r)
  };
  const summaryPath = path.join(LOG_DIR, 'pipeline-summary.json');
  if (!DRY_RUN) {
    fs.writeFileSync(summaryPath, JSON.stringify(summary, null, 2), 'utf8');
    fs.writeFileSync(path.join(logDir, 'summary.json'), JSON.stringify(summary, null, 2), 'utf8');
    console.log(`STATUT GLOBAL : ${validationLabel(summary.validation)}\nLogs: ${logDir}\nAllure: npm.cmd run allure:open`);
  }

  // Rapport HTML
  const html = buildHtmlReport(summary);
  const htmlPath = path.join(DOCS_DIR, 'pipeline-dashboard.html');
  if (!DRY_RUN) {
    fs.writeFileSync(htmlPath, html, 'utf8');
    console.log(`\n  ${G}✓ Rapport : ${htmlPath}${E}`);
  }

  process.exitCode = ko > 0 || blocked > 0 || rejected > 0 ? 1 : pendingApproval > 0 ? 2 : 0;
}

// ── STATUS — Vérification rapide des agents ───────────────────────────────────
function cmdStatus() {
  const agents = [
    'codegen-agent.js', 'runner-agent.js', 'quality-agent.js', 'ci-agent.js',
    'planning-agent.js', 'reporting-agent.js', 'advisor-agent.js',
    'observability-agent.js', 'bug-agent.js', 'pipeline-agent.js',
    'shared/tracer.js', 'shared/circuit-breaker.js',
    'shared/memory-store.js', 'shared/prompt-store.js',
  ];

  console.log(`\n${B}=== PIPELINE STATUS ===${E}\n`);
  agents.forEach(a => {
    const fp = path.join(AGENTS_DIR, a);
    const ok = fs.existsSync(fp);
    console.log(`  ${ok ? G+'✓'+E : R+'✗'+E}  ${a}`);
  });

  // Vérifier les logs/artefacts
  console.log(`\n${B}Artefacts :${E}`);
  const artefacts = [
    ['logs/traces.jsonl',              'Traces LLM'],
    ['logs/circuit_breaker_state.json','Circuit Breaker state'],
    ['logs/llm_cache.json',            'LLM cache'],
    ['memory/episodes.jsonl',          'Mémoire épisodique'],
    ['docs/kpi-dashboard.html',        'Dashboard KPI'],
    ['docs/pipeline-dashboard.html',   'Pipeline dashboard'],
  ];
  artefacts.forEach(([rel, label]) => {
    const fp = path.join(FRAMEWORK, rel);
    const ok = fs.existsSync(fp);
    const sz = ok ? ` (${(fs.statSync(fp).size / 1024).toFixed(1)}KB)` : '';
    console.log(`  ${ok ? G+'✓'+E : Y+'○'+E}  ${label.padEnd(30)} ${ok ? rel+sz : Y+'manquant'+E}`);
  });
}

// ── Génération HTML ───────────────────────────────────────────────────────────
function buildHtmlReport(s) {
  const rows = s.results.map(r => {
    const cls   = r.skipped || r.blocked || r.pendingApproval ? 'skip' : r.success ? 'ok' : 'ko';
    const icon  = r.pendingApproval ? 'EN ATTENTE D’APPROBATION' : r.rejected ? 'REJETÉ' : r.blocked ? 'BLOQUÉ' : r.skipped ? 'IGNORÉ' : r.success ? 'TERMINÉ' : 'ÉCHEC';
    const escape = value => String(value || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    return `<tr class="${cls}"><td>${icon}</td><td>${escape(r.name)}<br>${escape(r.reason || r.error || (r.timedOut ? 'Timeout' : ''))}</td><td>${((r.durationMs||0)/1000).toFixed(1)}s</td></tr>`;
  }).join('');

  return `<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><title>Pipeline Dashboard</title>
<style>
body{font-family:sans-serif;background:#0f172a;color:#e2e8f0;padding:24px;margin:0}
h1{color:#7c3aed}p{color:#64748b;font-size:.9rem}
.summary{display:flex;gap:16px;margin:16px 0}
.badge{background:#1e293b;border-radius:8px;padding:12px 20px;font-size:1.2rem;font-weight:700}
.badge.ok{color:#4ade80}.badge.ko{color:#f87171}.badge.time{color:#94a3b8}
table{width:100%;border-collapse:collapse;margin-top:16px}
th{background:#1e293b;padding:10px 14px;text-align:left;color:#64748b;font-size:.8rem}
td{padding:9px 14px;border-bottom:1px solid #1e293b;font-size:.85rem}
tr.ok td:first-child{color:#4ade80}tr.ko td:first-child{color:#f87171}tr.skip td:first-child{color:#fbbf24}
tr:hover td{background:#1e293b22}
</style></head>
<body>
<h1>Pipeline Dashboard</h1>
<p>Statut global : <strong>${validationLabel(s.validation)}</strong> | ${s.skipped || 0} étape(s) ignorée(s)</p>
<p>Tests BDD : ${s.testSummary?.total ? `${s.testSummary.passed}/${s.testSummary.total} réussis${s.testSummary.complete ? '' : ' (résultats incomplets)'}` : 'NON ÉVALUÉS'}</p>
<p>Rapport Allure : <code>npm.cmd run allure:open</code></p>
<p>Mode : <strong>${s.mode}</strong> &nbsp;|&nbsp; ${new Date(s.timestamp).toLocaleString('fr-FR')}</p>
<div class="summary">
  <div class="badge">${s.blocked || 0} BLOQUÉ(S)</div>
  <div class="badge">${s.pendingApproval || 0} EN ATTENTE D’APPROBATION</div>
  <div class="badge">${s.rejected || 0} REJETÉ(S)</div>
  <div class="badge ok">${s.ok} ÉTAPES TERMINÉES</div>
  <div class="badge ko">${s.ko} ÉCHEC(S)</div>
  <div class="badge time">${(s.totalMs/1000).toFixed(1)}s</div>
</div>
<table>
  <tr><th>État</th><th>Étape</th><th>Durée</th></tr>
  ${rows}
</table>
</body></html>`;
}

// ── Main ──────────────────────────────────────────────────────────────────────
async function main() {
  const [cmd] = process.argv.slice(2).filter(a => !a.startsWith('--'));

  switch (cmd) {
    case 'full':   await runPipeline('full');   break;
    case 'quick':  await runPipeline('quick');  break;
    case 'report': await runPipeline('report'); break;
    case 'status': cmdStatus();                 break;
    default:
      console.log(`
${B}Pipeline Agent${E} — Orchestrateur maître

  full            Pipeline complet (planning → codegen → run → quality → report → advisor → ci)
  quick           Pipeline rapide (run → triage → dashboard → gate)
  report          Analyse + dashboards sans exécution de tests
  status          Vérifie la présence de tous les agents et artefacts

Options:
  --dry-run       Simulation sans exécution
  --verbose       Affiche la sortie complète de chaque agent
  --no-tests      Saute l'étape d'exécution des tests (runner-agent)
  --sync-plane     Active explicitement la synchronisation externe Plane

Délais configurables : RUNNER_TIMEOUT_MS (1800000), AGENT_TIMEOUT_MS (300000).
Allure est généré après le Runner, même en cas d'échec. Ouverture : npm run allure:open.

Coût LLM : somme des agents invoqués
  full  ≈ 35k tokens/run ($0.03)
  quick ≈ 12k tokens/run ($0.01)
  report ≈ 20k tokens/run ($0.02)
`);
  }
}

if (require.main === module) main().catch(e => { console.error(R + e.message + E); process.exitCode = 1; });
module.exports = { runPipeline, runAgent, PIPELINE_STEPS };
