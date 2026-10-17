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

const fs     = require('fs');
const path   = require('path');
const llm         = require('./llm');
const tracer      = require('./shared/tracer');
const memory      = require('./shared/memory-store');
const promptStore = require('./shared/prompt-store');
const runtime = require('./shared/pipeline-runtime');

function fmt(template, vars) {
  let result = template;
  for (const [k, v] of Object.entries(vars)) {
    result = result.split('{' + k + '}').join(String(v ?? '?'));
  }
  return result;
}

const FRAMEWORK    = path.join(__dirname, '..', '..');
const verifier = require('./shared/agent-verifier').createVerifier({ agent: 'runner', root: FRAMEWORK, runtimeProcess: process });
let RESULTS_DIR = runtime.resultDirectory(FRAMEWORK);
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
async function runCucumber(tags = '', storyFiles = null, storyReference = null) {
  const args = [
    path.join(FRAMEWORK, 'node_modules', '@cucumber', 'cucumber', 'bin', 'cucumber.js'),
    ...(storyFiles || ['src/features/**/*.feature']),
    '--require-module', 'ts-node/register',
    '--require', 'src/core/world.ts',
    '--require', 'src/hooks/**/*.ts',
    '--require', 'src/steps/**/*.ts',
    '--format', 'progress',
  ];
  if (tags) args.push('--tags', tags);
  const scenarioName = process.argv.find(arg => arg.startsWith('--name='))?.slice('--name='.length);
  if (scenarioName) args.push('--name', scenarioName);

  console.log(`  ${C}→ node ${args.join(' ')}${E}`);
  if (DRY_RUN) { console.log(`  ${Y}[DRY-RUN] Tests non exécutés${E}`); return 0; }

  const runId = process.env.QA_RUN_ID || `${Date.now()}-${require('crypto').randomUUID()}`;
  RESULTS_DIR = process.env.QA_RUN_ID ? path.resolve(process.env.ALLURE_RESULTS_DIR)
    : path.join(FRAMEWORK, 'allure-runs', runId, 'results');
  fs.mkdirSync(RESULTS_DIR, { recursive: true });
  if (fs.readdirSync(RESULTS_DIR).some(name => name.endsWith('-result.json'))) throw new Error('Refusing to mix existing results with a new run');
  const manifestPath = path.join(RESULTS_DIR, 'run-manifest.json');
  const manifest = { runId, sourceHash: require('./shared/review-context').sourceHash(FRAMEWORK),
    ...(storyReference ? { story: storyReference, selectedFeatures: storyFiles } : {}),
    commit: process.env.GITHUB_SHA || null, startedAt: Date.now(), completed: false, exitCode: null, resultCount: 0,
    tags: tags || (scenarioName ? `name:${scenarioName}` : ''),
    ...(scenarioName ? { scenarioName } : {}) };
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
  fs.mkdirSync(path.join(FRAMEWORK, 'logs'), { recursive: true });
  fs.writeFileSync(path.join(FRAMEWORK, 'logs', 'latest-test-run.json'), JSON.stringify({ runId }));
  const messages = path.join(RESULTS_DIR, 'cucumber-messages.ndjson');
  // Cucumber keeps only the last formatter per output target. Give Allure its own target.
  args.push('--format', `"allure-cucumberjs/reporter":"${path.join(RESULTS_DIR, 'allure-formatter.log')}"`);
  args.push('--format-options', JSON.stringify({ resultsDir: RESULTS_DIR }), '--format', `"message":"${messages}"`);
  const result = await runtime.execute(process.execPath, args, {
    cwd: FRAMEWORK, env: { ...process.env, ALLURE_RESULTS_DIR: RESULTS_DIR }, verbose: true,
    timeout: runtime.timeoutMs(process.env.RUNNER_TIMEOUT_MS, 30 * 60 * 1000),
  });
  const data = runtime.readResults(RESULTS_DIR);
  let finished = false;
  if (fs.existsSync(messages)) {
    finished = fs.readFileSync(messages, 'utf8').split(/\r?\n/).filter(Boolean)
      .some(line => { try { return !!JSON.parse(line).testRunFinished; } catch { return false; } });
  }
  Object.assign(manifest, { finishedAt: Date.now(), completed: finished && !result.timedOut && !result.error,
    exitCode: result.exitCode, timedOut: result.timedOut, error: result.error, resultCount: data.results.length });
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
  console.log(`Results: ${RESULTS_DIR}`);
  const code = result.success && manifest.completed && data.results.length && !data.errors.length &&
    data.results.every(r => r.status === 'passed') ? 0 : 1;
  if (code) process.exitCode = 1;
  if (process.env.PLANE_SYNC_RESULTS === 'true') {
    try {
      const synced = await require('./shared/plane-results').syncResults(require('./plane-fetcher').client(), RESULTS_DIR, { apply: true, pace: 1100 });
      console.log('Plane results: ' + JSON.stringify(synced));
    } catch (e) { console.error('Plane results sync failed: ' + e.message); process.exitCode = 1; }
  }
  return code;
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
    verifier.check('summary', summary, { stats, failures });
    const factual = require('./shared/agent-verifier').factualSummary(stats);
    verifier.check('factual-summary', factual, stats);
    span.response = summary; span.end(true);
    return factual + '\n[HYPOTHÈSE IA NON VÉRIFIÉE] ' + summary;
  } catch (e) {
    verifier.failure(e);
    span.error = e.message; span.end(false);
    return `Run terminé : ${stats.pass_rate}% de réussite.`;
  }
}

// ── run : tous les tests ───────────────────────────────────────────────────────
async function cmdRun() {
  console.log(`\n${B}=== RUNNER — RUN [${llm.MODEL}] ===${E}`);
  const code = await runCucumber();
  const results  = loadResults();
  const stats    = computeStats(results);
  const failures = results.filter(r => ['failed','broken'].includes(r.status));
  printStats(stats);

  const summary = process.argv.includes('--ai-summary') && !DRY_RUN
    ? await llmSummary(stats, failures) : `Run: ${stats.passed}/${stats.total} passed.`;
  console.log(`\n  ${C}${summary}${E}`);

  if (!DRY_RUN) memory.recordEpisode('runner-agent', failures.map(f => ({ tc: f.name, status: f.status })), summary, 'run', stats);
  if (code !== 0 && !DRY_RUN) process.exitCode = 1;
}

// ── smoke : tests @smoke ──────────────────────────────────────────────────────
async function cmdSmoke() {
  console.log(`\n${B}=== RUNNER — SMOKE ===${E}`);
  const code = await runCucumber('@smoke');
  const results = loadResults();
  const stats   = computeStats(results);
  printStats(stats, '@smoke');
  if (code !== 0 && !DRY_RUN) process.exitCode = 1;
}

// ── critical : tests @critical ────────────────────────────────────────────────
async function cmdCritical() {
  console.log(`\n${B}=== RUNNER — CRITICAL ===${E}`);
  const code = await runCucumber('@critical');
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
    await runCucumber();
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

  // Analyse qualitative LLM des causes — uniquement s'il y a des tests flaky à expliquer
  let analysis = null;
  if (flaky.length) {
    const span = new tracer.Span('flakyAnalyze', JSON.stringify(flaky), llm.MODEL).begin();
    try {
      const _tpl = promptStore.get('flaky_analyze') ||
        'Ces tests UI Playwright sont flaky (passent parfois, échouent parfois) :\n{flaky_list}\n\n' +
        'En 3 points concis, explique :\n' +
        '1. Les causes probables (timing animations, lazy loading, sélecteurs fragiles, état partagé...)\n' +
        '2. Les patterns communs entre les scénarios affectés\n' +
        '3. Les actions de stabilisation recommandées (waitFor, locators robustes, isolation d\'état...)';
      const flakyList = flaky.map(t => `- ${t.name} : ${Math.round(t.flakiness*100)}% d'échec (${t.fails}/${t.runs} runs)`).join('\n');
      const prompt = fmt(_tpl, { flaky_list: flakyList });

      const resp = await llm.chat([{ role: 'user', content: prompt }]);
      analysis = resp.message.content || '';
      verifier.check('flaky', analysis, { flaky });
      analysis = '[HYPOTHÈSE IA NON VÉRIFIÉE] ' + analysis;
      span.response = analysis; span.end(true);
      promptStore.recordUsage('flaky_analyze');
      console.log(`\n  ${B}Analyse IA des causes :${E}\n  ${analysis.split('\n').join('\n  ')}`);
    } catch (e) {
      verifier.failure(e);
      span.error = e.message; span.end(false);
      analysis = null;
      console.error(`  ${R}✗ Analyse flaky : ${e.message}${E}`);
    }
  }

  if (!DRY_RUN) {
    fs.writeFileSync(path.join(DOCS_DIR, 'flaky-report.json'), JSON.stringify({ ts: new Date().toISOString(), runs: RUNS_ARG, flaky, critical, analysis }, null, 2), 'utf8');
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

  await runCucumber();
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
  // Test execution must not depend on LLM availability.

  switch (cmd) {
    case 'story': {
      const key = process.argv.slice(3).find(a => !a.startsWith('--'));
      if (!key) throw Error('Usage: runner-agent.js story <Plane key> [--dry-run]');
      const story = await require('./plane-fetcher').fetchIssue(key);
      const files = require('./shared/plane-stories').filesFor(story);
      console.log(`Plane ${story.key}: ${files.length} feature files selected`);
      await runCucumber('', files, { provider: 'plane', key: story.key, id: story.id, url: story.url });
      break;
    }
    case 'run':        await cmdRun();        break;
    case 'smoke':      await cmdSmoke();      break;
    case 'critical':   await cmdCritical();   break;
    case 'flaky':      await cmdFlaky();      break;
    case 'regression': await cmdRegression(); break;
    case 'baseline':   cmdBaseline();         break;
    default:
      console.log(`
${B}Runner Agent${E} — Exécution des tests Playwright/Cucumber

  run              Lance tous les tests (résumé LLM optionnel)
  story <key>      Lit une story Plane et lance ses features locales associées
  smoke            Lance uniquement les tests @smoke
  critical         Lance uniquement les tests @critical
  regression       Détecte les régressions vs baseline
  flaky            Détecte les tests instables (multi-runs)
  baseline         Sauvegarde le baseline actuel

Options:
  --dry-run        Simulation sans exécution ni écriture
  --ai-summary     Ajoute un résumé LLM après les tests
  --runs=N         Nombre de runs pour la détection flaky (défaut: 3)
`);
  }
}

if (require.main === module) main().catch(e => { console.error(R + e.message + E); process.exitCode = 1; });
module.exports = { runCucumber, main };
