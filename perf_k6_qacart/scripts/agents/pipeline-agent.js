'use strict';
// ============================================================
// Pipeline Agent — Orchestrateur maître (k6 Performance)
// ============================================================
// Master orchestrator : exécute les agents dans l'ordre optimal
//
// Usage:
//   node scripts/agents/pipeline-agent.js full           Pipeline complet (tous les agents)
//   node scripts/agents/pipeline-agent.js quick          Pipeline rapide (runner+quality+reporting)
//   node scripts/agents/pipeline-agent.js report         Rapport de pipeline uniquement
//   node scripts/agents/pipeline-agent.js status          État de santé de tous les agents
//
// Coût LLM : dépend des agents invoqués (aucun LLM propre à cet agent)
// ============================================================
require('dotenv').config();
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';

const { spawnSync } = require('child_process');
const fs   = require('fs');
const path = require('path');

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

// ── Utilitaire d'exécution d'agent ────────────────────────────────────────────
function runAgent(agentFile, args = [], label = '') {
  const name = label || path.basename(agentFile, '.js');
  const start = Date.now();
  console.log(`\n${C}▶ ${name}${args.length ? ' ' + args.join(' ') : ''}${E}`);

  if (DRY_RUN) {
    console.log(`  ${Y}[DRY-RUN] skipped${E}`);
    return { success: true, durationMs: 0, skipped: true };
  }

  const result = spawnSync('node', [path.join(AGENTS_DIR, agentFile), ...args], {
    cwd: FRAMEWORK,
    stdio: VERBOSE ? 'inherit' : ['ignore', 'pipe', 'pipe'],
    encoding: 'utf8',
    timeout: 10 * 60 * 1000,
  });

  const durationMs = Date.now() - start;
  const success    = result.status === 0;

  if (success) {
    console.log(`  ${G}✓ Terminé en ${(durationMs/1000).toFixed(1)}s${E}`);
    if (VERBOSE && result.stdout) console.log(result.stdout.slice(-300));
  } else {
    console.log(`  ${R}✗ Échec (${result.status ?? 'timeout'}) en ${(durationMs/1000).toFixed(1)}s${E}`);
    const errOut = (result.stderr || result.stdout || '').slice(-400);
    if (errOut) console.log(`  ${R}${errOut}${E}`);
  }

  return { name, success, durationMs, stdout: result.stdout || '', stderr: result.stderr || '' };
}

// ── Étapes de pipeline ────────────────────────────────────────────────────────
const PIPELINE_STEPS = {
  full: [
    { file: 'planning-agent.js',     args: ['coverage', 'analyze'], label: 'Planning → Analyse couverture' },
    { file: 'runner-agent.js',       args: ['run'],                 label: 'Runner → Exécution scénarios k6', skipIfNoTests: true },
    { file: 'quality-agent.js',      args: ['full'],                label: 'Quality → Triage + RCA' },
    { file: 'bug-agent.js',          args: ['analyze'],             label: 'Bug → Analyse seuils dépassés' },
    { file: 'reporting-agent.js',    args: ['dashboard'],           label: 'Reporting → Dashboard KPI' },
    { file: 'advisor-agent.js',      args: ['advise'],              label: 'Advisor → Recommandation GO/NO-GO' },
    { file: 'observability-agent.js',args: ['metrics'],             label: 'Observability → Métriques' },
    { file: 'ci-agent.js',           args: ['status'],              label: 'CI → État pipeline GitHub' },
  ],

  quick: [
    { file: 'runner-agent.js',    args: ['run'],         label: 'Runner → Exécution scénarios k6', skipIfNoTests: true },
    { file: 'quality-agent.js',   args: ['triage'],      label: 'Quality → Triage rapide' },
    { file: 'reporting-agent.js', args: ['dashboard'],   label: 'Reporting → Dashboard KPI' },
    { file: 'advisor-agent.js',   args: ['gate'],        label: 'Advisor → Quality gate' },
  ],

  report: [
    { file: 'quality-agent.js',      args: ['full'],      label: 'Quality → Analyse complète' },
    { file: 'bug-agent.js',          args: ['report'],    label: 'Bug → Rapport seuils' },
    { file: 'reporting-agent.js',    args: ['dashboard'], label: 'Reporting → Dashboard KPI' },
    { file: 'observability-agent.js',args: ['report'],    label: 'Observability → Rapport traces' },
  ],
};

// ── Exécution du pipeline ─────────────────────────────────────────────────────
async function runPipeline(mode) {
  const steps   = PIPELINE_STEPS[mode];
  const startTs = Date.now();
  const results = [];

  console.log(`\n${B}${'═'.repeat(60)}${E}`);
  console.log(`${B}  PIPELINE AGENT — ${mode.toUpperCase()} (k6 Performance)${E}`);
  console.log(`${B}${'═'.repeat(60)}${E}`);
  console.log(`  ${steps.length} étapes | ${new Date().toLocaleString('fr-FR')}\n`);

  for (const step of steps) {
    if (step.skipIfNoTests && NO_TESTS) {
      console.log(`  ${Y}⊘ ${step.label} — skipped (--no-tests)${E}`);
      results.push({ name: step.label, success: true, skipped: true, durationMs: 0 });
      continue;
    }
    const r = runAgent(step.file, step.args, step.label);
    results.push({ name: step.label, ...r });
  }

  const totalMs = Date.now() - startTs;
  const ok      = results.filter(r => r.success || r.skipped).length;
  const ko      = results.filter(r => !r.success && !r.skipped).length;

  console.log(`\n${B}${'═'.repeat(60)}${E}`);
  console.log(`${B}  RÉSULTATS${E}   ${G}${ok}/${results.length} OK${E}   ${ko ? R+ko+' KO'+E : ''}   ${(totalMs/1000).toFixed(1)}s`);
  console.log(`${B}${'═'.repeat(60)}${E}\n`);

  results.forEach(r => {
    const icon = r.skipped ? Y+'⊘'+E : r.success ? G+'✓'+E : R+'✗'+E;
    console.log(`  ${icon}  ${(r.name||'').slice(0,50).padEnd(52)} ${((r.durationMs||0)/1000).toFixed(1).padStart(5)}s`);
  });

  const summary = {
    mode, timestamp: new Date().toISOString(), totalMs,
    ok, ko, steps: results.length,
    results: results.map(r => ({ name: r.name, success: r.success||false, skipped: !!r.skipped, durationMs: r.durationMs||0 }))
  };
  const summaryPath = path.join(LOG_DIR, 'pipeline-summary.json');
  if (!DRY_RUN) fs.writeFileSync(summaryPath, JSON.stringify(summary, null, 2), 'utf8');

  const html = buildHtmlReport(summary);
  const htmlPath = path.join(DOCS_DIR, 'pipeline-dashboard.html');
  if (!DRY_RUN) {
    fs.writeFileSync(htmlPath, html, 'utf8');
    console.log(`\n  ${G}✓ Rapport : ${htmlPath}${E}`);
  }

  process.exitCode = ko > 0 ? 1 : 0;
}

// ── STATUS — Vérification rapide des agents ───────────────────────────────────
function cmdStatus() {
  const agents = [
    'runner-agent.js', 'quality-agent.js', 'ci-agent.js',
    'planning-agent.js', 'reporting-agent.js', 'advisor-agent.js',
    'observability-agent.js', 'bug-agent.js', 'pipeline-agent.js', 'codegen-agent.js',
    'shared/tracer.js', 'shared/circuit-breaker.js',
    'shared/memory-store.js', 'shared/prompt-store.js',
  ];

  console.log(`\n${B}=== PIPELINE STATUS ===${E}\n`);
  agents.forEach(a => {
    const fp = path.join(AGENTS_DIR, a);
    const ok = fs.existsSync(fp);
    console.log(`  ${ok ? G+'✓'+E : R+'✗'+E}  ${a}`);
  });

  console.log(`\n${B}Artefacts :${E}`);
  const artefacts = [
    ['logs/traces.jsonl',              'Traces LLM'],
    ['logs/circuit_breaker_state.json','Circuit Breaker state'],
    ['logs/llm_cache.json',            'LLM cache'],
    ['memory/episodes.jsonl',          'Mémoire épisodique'],
    ['reports/summary-smoke.json',     'Résultats k6 smoke'],
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
    const cls   = r.skipped ? 'skip' : r.success ? 'ok' : 'ko';
    const icon  = r.skipped ? '⊘' : r.success ? '✓' : '✗';
    return `<tr class="${cls}"><td>${icon}</td><td>${r.name||''}</td><td>${((r.durationMs||0)/1000).toFixed(1)}s</td></tr>`;
  }).join('');

  return `<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><title>Pipeline Dashboard — k6 Performance</title>
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
<h1>Pipeline Dashboard — k6 Performance</h1>
<p>Mode : <strong>${s.mode}</strong> &nbsp;|&nbsp; ${new Date(s.timestamp).toLocaleString('fr-FR')}</p>
<div class="summary">
  <div class="badge ok">✓ ${s.ok} OK</div>
  <div class="badge ko">${s.ko > 0 ? '✗ '+s.ko+' KO' : '○ 0 KO'}</div>
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
${B}Pipeline Agent${E} — Orchestrateur maître (k6 Performance)

  full            Pipeline complet (planning → run → quality → report → advisor → ci)
  quick           Pipeline rapide (run → triage → dashboard → gate)
  report          Analyse + dashboards sans exécution de tests
  status          Vérifie la présence de tous les agents et artefacts

Options:
  --dry-run       Simulation sans exécution
  --verbose       Affiche la sortie complète de chaque agent
  --no-tests      Saute l'étape d'exécution des tests (runner-agent)
`);
  }
}

main().catch(e => { console.error(R + e.message + E); process.exit(1); });
