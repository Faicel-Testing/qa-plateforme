'use strict';
// ============================================================
// Runner Agent — Exécution des tests Playwright/Cucumber
// ============================================================
// Absorbe : execute-agent, qa-agent (run), smoke, regression, flaky
//
// Usage:
//   node scripts/agents/runner-agent.js run              Lance tous les tests
//   node scripts/agents/runner-agent.js smoke            Tests @smoke uniquement
//   node scripts/agents/runner-agent.js critical         Tests @critical uniquement
//   node scripts/agents/runner-agent.js regression       Détecte les régressions vs baseline
//   node scripts/agents/runner-agent.js flaky [--runs=N] Lance N fois, identifie les tests instables
//   node scripts/agents/runner-agent.js baseline         Sauvegarde le baseline actuel
//
// Coût LLM : très bas — LLM utilisé uniquement pour le résumé narratif final
// ============================================================
require('dotenv').config();
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';

const fs     = require('fs');
const path   = require('path');
const { spawnSync } = require('child_process');
const llm    = require('./llm');
const tracer = require('./shared/tracer');
const memory = require('./shared/memory-store');

const FRAMEWORK    = path.join(__dirname, '..', '..');
const RESULTS_DIR  = path.join(FRAMEWORK, 'allure-results');
const DOCS_DIR     = path.join(FRAMEWORK, 'docs');
const BASELINE_FILE = path.join(DOCS_DIR, 'baseline.json');

fs.mkdirSync(DOCS_DIR, { recursive: true });

const DRY_RUN  = process.argv.includes('--dry-run');
const RUNS_ARG = parseInt(process.argv.find(a => a.startsWith('--runs='))?.split('=')[1] || '3');
const FLAKY_THRESHOLD = 0.34; // 1/3 des runs = flaky

const G = '\x1b[32m', R = '\x1b[31m', Y = '\x1b[33m', C = '\x1b[36m', B = '\x1b[1m', E = '\x1b[0m';

// ── Lecture allure-results ─────────────────────────────────────────────────────
function loadResults() {
  if (!fs.existsSync(RESULTS_DIR)) return [];
  return fs.readdirSync(RESULTS_DIR)
    .filter(f => f.endsWith('-result.json'))
    .map(f => { try { return JSON.parse(fs.readFileSync(path.join(RESULTS_DIR, f), 'utf8')); } catch { return null; } })
    .filter(Boolean);
}

function computeStats(results) {
  const stats = { passed: 0, failed: 0, broken: 0, skipped: 0, total: 0 };
  for (const r of results) {
    const s = r.status || 'unknown';
    if (s in stats) stats[s]++;
    stats.total++;
  }
  stats.pass_rate = stats.total ? Math.round(stats.passed / stats.total * 1000) / 10 : 0;
  return stats;
}

function printStats(stats, label = '') {
  const bar  = '\x1b[32m' + '█'.repeat(Math.round(stats.pass_rate / 5)) + '\x1b[0m' + '░'.repeat(20 - Math.round(stats.pass_rate / 5));
  console.log(`\n  [${bar}] ${stats.pass_rate}% passed  ${label}`);
  console.log(`  Total: ${stats.total}  |  ${G}${stats.passed}P${E}  ${R}${stats.failed}F${E}  ${Y}${stats.broken}B${E}  ${C}${stats.skipped}S${E}`);
}

// ── Exécution cucumber-js ──────────────────────────────────────────────────────
function runCucumber(tags = '') {
  const args = [
    'cucumber-js',
    'src/features/**/*.feature',
    '--require-module', 'ts-node/register',
    '--require', 'src/core/world.ts',
    '--require', 'src/hooks/**/*.ts',
    '--require', 'src/steps/**/*.ts',
    '--format', 'allure-cucumberjs/reporter',
    '--format', 'progress',
  ];
  if (tags) args.push('--tags', tags);

  console.log(`  ${C}→ npx ${args.join(' ')}${E}`);
  if (DRY_RUN) { console.log(`  ${Y}[DRY-RUN] Tests non exécutés${E}`); return 0; }

  const result = spawnSync('npx', args, {
    cwd: FRAMEWORK, stdio: 'inherit', shell: true, encoding: 'utf8'
  });
  return result.status || 0;
}

// ── Résumé LLM ────────────────────────────────────────────────────────────────
async function llmSummary(stats, failures) {
  const span = new tracer.Span('runnerSummary', JSON.stringify(stats), llm.MODEL).begin();
  try {
    const prompt = `Tu es un expert QA. Génère un résumé court (2-3 phrases) du run de tests Playwright.

Résultats : ${stats.passed}/${stats.total} passés (${stats.pass_rate}%)
Échecs : ${failures.map(f => f.name).join(', ') || 'aucun'}

Sois factuel et direct. Si PASSED → rassurant. Si FAILED → cause probable + action.`;

    const resp = await llm.chat([{ role: 'user', content: prompt }]);
    const summary = resp.message.content || '';
    span.response = summary; span.end(true);
    return summary;
  } catch (e) {
    span.error = e.message; span.end(false);
    return `Run terminé : ${stats.pass_rate}% de réussite.`;
  }
}

// ── run : tous les tests ───────────────────────────────────────────────────────
async function cmdRun() {
  console.log(`\n${B}=== RUNNER — RUN [${llm.MODEL}] ===${E}`);
  const code = runCucumber();
  const results  = loadResults();
  const stats    = computeStats(results);
  const failures = results.filter(r => ['failed','broken'].includes(r.status));
  printStats(stats);

  const summary = await llmSummary(stats, failures);
  console.log(`\n  ${C}${summary}${E}`);

  memory.recordEpisode('runner-agent', failures.map(f => ({ tc: f.name, status: f.status })), summary, 'run', stats);
  if (code !== 0 && !DRY_RUN) process.exitCode = 1;
}

// ── smoke : tests @smoke ──────────────────────────────────────────────────────
async function cmdSmoke() {
  console.log(`\n${B}=== RUNNER — SMOKE ===${E}`);
  const code = runCucumber('@smoke');
  const results = loadResults();
  const stats   = computeStats(results.filter(r => (r.labels||[]).some(l => l.value === 'smoke')));
  printStats(stats, '@smoke');
  if (code !== 0 && !DRY_RUN) process.exitCode = 1;
}

// ── critical : tests @critical ────────────────────────────────────────────────
async function cmdCritical() {
  console.log(`\n${B}=== RUNNER — CRITICAL ===${E}`);
  const code = runCucumber('@critical');
  const results = loadResults();
  printStats(computeStats(results), '@critical');
  if (code !== 0 && !DRY_RUN) process.exitCode = 1;
}

// ── flaky : N runs pour détecter les tests instables ─────────────────────────
async function cmdFlaky() {
  console.log(`\n${B}=== RUNNER — FLAKY DETECTION (${RUNS_ARG} runs) ===${E}`);
  const tcMap = {}; // tc_name → { fails, total }

  for (let i = 1; i <= RUNS_ARG; i++) {
    console.log(`\n  ${C}Run ${i}/${RUNS_ARG}${E}`);
    runCucumber();
    const results = loadResults();
    for (const r of results) {
      const name = r.name || r.fullName || 'unknown';
      if (!tcMap[name]) tcMap[name] = { fails: 0, total: 0 };
      tcMap[name].total++;
      if (['failed','broken'].includes(r.status)) tcMap[name].fails++;
    }
  }

  const flaky = Object.entries(tcMap)
    .map(([name, s]) => ({ name, flakiness: s.fails / s.total, fails: s.fails, runs: s.total }))
    .filter(t => t.flakiness > 0 && t.flakiness < 1)
    .sort((a, b) => b.flakiness - a.flakiness);

  const critical = flaky.filter(t => t.flakiness >= FLAKY_THRESHOLD);

  console.log(`\n  ${B}Tests flaky détectés : ${flaky.length}${E}`);
  for (const t of flaky) {
    const icon = t.flakiness >= FLAKY_THRESHOLD ? R + '⚠ FLAKY' + E : Y + '~ instable' + E;
    console.log(`  ${icon}  ${t.name.slice(0,55).padEnd(55)} ${Math.round(t.flakiness*100)}% (${t.fails}/${t.runs})`);
  }

  if (!DRY_RUN) {
    fs.writeFileSync(path.join(DOCS_DIR, 'flaky-report.json'), JSON.stringify({ ts: new Date().toISOString(), runs: RUNS_ARG, flaky, critical }, null, 2), 'utf8');
    console.log(`\n  ${G}✓ docs/flaky-report.json${E}`);
  }

  memory.recordEpisode('runner-agent', critical.map(t => ({ tc: t.name, flakiness: t.flakiness })), `${critical.length} tests flaky critiques`, 'flaky');
}

// ── regression : compare avec baseline ────────────────────────────────────────
async function cmdRegression() {
  console.log(`\n${B}=== RUNNER — REGRESSION ===${E}`);
  const baseline = fs.existsSync(BASELINE_FILE) ? JSON.parse(fs.readFileSync(BASELINE_FILE, 'utf8')) : null;
  if (!baseline) {
    console.log(`  ${Y}⚠  Aucun baseline — lance d'abord: runner baseline${E}`);
  }

  runCucumber();
  const results = loadResults();
  const stats   = computeStats(results);
  printStats(stats, 'vs baseline');

  if (baseline) {
    const regressions = results.filter(r => {
      const prev = baseline.tests?.[r.name];
      return ['failed','broken'].includes(r.status) && prev === 'passed';
    });
    if (regressions.length) {
      console.log(`\n  ${R}⚠  ${regressions.length} régression(s) détectée(s) :${E}`);
      regressions.forEach(r => console.log(`    ${R}✗${E} ${r.name}`));
    } else {
      console.log(`\n  ${G}✓ Aucune régression${E}`);
    }
  }
}

// ── baseline : sauvegarde l'état actuel ───────────────────────────────────────
function cmdBaseline() {
  console.log(`\n${B}=== RUNNER — BASELINE ===${E}`);
  const results = loadResults();
  const tests   = {};
  results.forEach(r => { tests[r.name] = r.status; });
  const baseline = { ts: new Date().toISOString(), total: results.length, tests };
  if (!DRY_RUN) {
    fs.writeFileSync(BASELINE_FILE, JSON.stringify(baseline, null, 2), 'utf8');
    console.log(`  ${G}✓ Baseline sauvegardé : ${results.length} tests${E}`);
  } else {
    console.log(`  ${Y}[DRY-RUN] Baseline non sauvegardé (${results.length} tests)${E}`);
  }
}

// ── Main ──────────────────────────────────────────────────────────────────────
async function main() {
  const [cmd] = process.argv.slice(2).filter(a => !a.startsWith('--'));
  await llm.assertRunning();

  switch (cmd) {
    case 'run':        await cmdRun();        break;
    case 'smoke':      await cmdSmoke();      break;
    case 'critical':   await cmdCritical();   break;
    case 'flaky':      await cmdFlaky();      break;
    case 'regression': await cmdRegression(); break;
    case 'baseline':   cmdBaseline();         break;
    default:
      console.log(`
${B}Runner Agent${E} — Exécution des tests Playwright/Cucumber

  run              Lance tous les tests + résumé LLM
  smoke            Lance uniquement les tests @smoke
  critical         Lance uniquement les tests @critical
  regression       Détecte les régressions vs baseline
  flaky            Détecte les tests instables (multi-runs)
  baseline         Sauvegarde le baseline actuel

Options:
  --dry-run        Simulation sans exécution ni écriture
  --runs=N         Nombre de runs pour la détection flaky (défaut: 3)
`);
  }
}

main().catch(e => { console.error(R + e.message + E); process.exit(1); });
