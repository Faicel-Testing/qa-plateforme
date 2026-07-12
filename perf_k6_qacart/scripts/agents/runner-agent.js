'use strict';
// ============================================================
// Runner Agent — Exécution des scénarios k6
// ============================================================
// Usage:
//   node scripts/agents/runner-agent.js run              Lance tous les scénarios (smoke, load, stress)
//   node scripts/agents/runner-agent.js smoke            Scénario @smoke uniquement
//   node scripts/agents/runner-agent.js load              Scénario @load uniquement
//   node scripts/agents/runner-agent.js stress            Scénario @stress uniquement
//   node scripts/agents/runner-agent.js baseline          Sauvegarde le baseline actuel
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

const FRAMEWORK     = path.join(__dirname, '..', '..');
const SCENARIOS_DIR  = path.join(FRAMEWORK, 'k6', 'scenarios');
const REPORTS_DIR    = path.join(FRAMEWORK, 'reports');
const DOCS_DIR       = path.join(FRAMEWORK, 'docs');
const BASELINE_FILE  = path.join(DOCS_DIR, 'baseline.json');

fs.mkdirSync(REPORTS_DIR, { recursive: true });
fs.mkdirSync(DOCS_DIR, { recursive: true });

const DRY_RUN     = process.argv.includes('--dry-run');
const NO_DASHBOARD = process.argv.includes('--no-dashboard');
const SCENARIOS    = ['smoke', 'load', 'stress'];

const G = '\x1b[32m', R = '\x1b[31m', Y = '\x1b[33m', C = '\x1b[36m', B = '\x1b[1m', E = '\x1b[0m';

// ── Lecture summary-export k6 ──────────────────────────────────────────────────
function loadSummary(scenario) {
  const fp = path.join(REPORTS_DIR, `summary-${scenario}.json`);
  if (!fs.existsSync(fp)) return null;
  try { return JSON.parse(fs.readFileSync(fp, 'utf8')); } catch { return null; }
}

function computeStats(summary) {
  if (!summary) return null;
  const checks = summary.metrics?.checks || { passes: 0, fails: 0, value: 0 };
  const httpFailed = summary.metrics?.http_req_failed || { value: 0 };
  const dur = summary.metrics?.http_req_duration || {};

  const breaches = [];
  for (const [metricName, metric] of Object.entries(summary.metrics || {})) {
    for (const [expr, breached] of Object.entries(metric.thresholds || {})) {
      if (breached) breaches.push({ metric: metricName, expr });
    }
  }

  return {
    checks_total: checks.passes + checks.fails,
    checks_passed: checks.passes,
    checks_failed: checks.fails,
    pass_rate: (checks.passes + checks.fails) ? Math.round(checks.passes / (checks.passes + checks.fails) * 1000) / 10 : 0,
    error_rate: Math.round((httpFailed.value || 0) * 1000) / 10,
    p95_ms: Math.round(dur['p(95)'] || 0),
    avg_ms: Math.round(dur.avg || 0),
    breaches,
    gate_ok: breaches.length === 0,
  };
}

function printStats(scenario, stats) {
  if (!stats) { console.log(`  ${Y}⚠  Pas de résultats pour ${scenario}${E}`); return; }
  const bar = (stats.gate_ok ? G : R) + '█'.repeat(Math.round(stats.pass_rate / 5)) + E + '░'.repeat(20 - Math.round(stats.pass_rate / 5));
  console.log(`\n  [${bar}] ${stats.pass_rate}% checks OK  (${scenario})`);
  console.log(`  p95=${stats.p95_ms}ms  avg=${stats.avg_ms}ms  error_rate=${stats.error_rate}%  checks=${stats.checks_passed}/${stats.checks_total}`);
  if (stats.breaches.length) {
    console.log(`  ${R}✗ ${stats.breaches.length} seuil(s) dépassé(s) :${E}`);
    stats.breaches.forEach(b => console.log(`    ${R}•${E} ${b.metric} — ${b.expr}`));
  } else {
    console.log(`  ${G}✓ Tous les seuils respectés${E}`);
  }
}

// ── Exécution k6 ────────────────────────────────────────────────────────────────
function runK6(scenario) {
  const scriptPath = path.join(SCENARIOS_DIR, `${scenario}.js`);
  const summaryPath = path.join(REPORTS_DIR, `summary-${scenario}.json`);
  const args = ['run', `--summary-export=${summaryPath}`, scriptPath];

  console.log(`  ${C}→ k6 ${args.join(' ')}${E}`);
  if (DRY_RUN) { console.log(`  ${Y}[DRY-RUN] Scénario non exécuté${E}`); return 0; }

  const env = { ...process.env };
  if (!NO_DASHBOARD) {
    env.K6_WEB_DASHBOARD = 'true';
    env.K6_WEB_DASHBOARD_EXPORT = path.join(REPORTS_DIR, `dashboard-${scenario}.html`);
    env.K6_WEB_DASHBOARD_PERIOD = '5s';
  }

  const result = spawnSync('k6', args, { cwd: FRAMEWORK, stdio: 'inherit', shell: true, encoding: 'utf8', env });
  return result.status || 0;
}

// ── Résumé LLM ────────────────────────────────────────────────────────────────
async function llmSummary(scenario, stats) {
  const span = new tracer.Span('runnerSummary', JSON.stringify(stats), llm.MODEL).begin();
  try {
    const prompt = `Tu es un expert en tests de performance k6. Génère un résumé court (2-3 phrases) du run "${scenario}".

Résultats : p95=${stats.p95_ms}ms, avg=${stats.avg_ms}ms, error_rate=${stats.error_rate}%, checks=${stats.pass_rate}%
Seuils dépassés : ${stats.breaches.map(b => `${b.metric} (${b.expr})`).join(', ') || 'aucun'}

Sois factuel et direct. Si tous les seuils sont respectés → rassurant. Si dépassés → cause probable (charge, backend, réseau) + action.`;

    const resp = await llm.chat([{ role: 'user', content: prompt }]);
    const summary = resp.message.content || '';
    span.response = summary; span.end(true);
    return summary;
  } catch (e) {
    span.error = e.message; span.end(false);
    return `Run ${scenario} terminé : ${stats.pass_rate}% de checks OK, p95=${stats.p95_ms}ms.`;
  }
}

// ── run : un scénario ──────────────────────────────────────────────────────────
async function runScenario(scenario) {
  console.log(`\n${B}=== RUNNER — ${scenario.toUpperCase()} [${llm.MODEL}] ===${E}`);
  const code  = runK6(scenario);
  const stats = computeStats(loadSummary(scenario));
  printStats(scenario, stats);

  if (stats) {
    const summary = await llmSummary(scenario, stats);
    console.log(`\n  ${C}${summary}${E}`);
    memory.recordEpisode('runner-agent', stats.breaches.map(b => ({ tc: `${scenario}/${b.metric}`, status: 'breach' })), summary, scenario, stats);
  }

  if (code !== 0 && !DRY_RUN) process.exitCode = 1;
  return stats;
}

// ── run : tous les scénarios ───────────────────────────────────────────────────
async function cmdRun() {
  console.log(`\n${B}=== RUNNER — RUN (smoke → load → stress) ===${E}`);
  const results = {};
  for (const scenario of SCENARIOS) {
    results[scenario] = await runScenario(scenario);
  }
  return results;
}

// ── baseline : sauvegarde l'état actuel ───────────────────────────────────────
function cmdBaseline() {
  console.log(`\n${B}=== RUNNER — BASELINE ===${E}`);
  const baseline = { ts: new Date().toISOString(), scenarios: {} };
  for (const scenario of SCENARIOS) {
    const stats = computeStats(loadSummary(scenario));
    if (stats) baseline.scenarios[scenario] = { p95_ms: stats.p95_ms, avg_ms: stats.avg_ms, error_rate: stats.error_rate };
  }
  if (!DRY_RUN) {
    fs.writeFileSync(BASELINE_FILE, JSON.stringify(baseline, null, 2), 'utf8');
    console.log(`  ${G}✓ Baseline sauvegardé : ${Object.keys(baseline.scenarios).length} scénario(s)${E}`);
  } else {
    console.log(`  ${Y}[DRY-RUN] Baseline non sauvegardé${E}`);
  }
}

// ── regression : compare avec baseline ────────────────────────────────────────
async function cmdRegression() {
  console.log(`\n${B}=== RUNNER — REGRESSION vs BASELINE ===${E}`);
  const baseline = fs.existsSync(BASELINE_FILE) ? JSON.parse(fs.readFileSync(BASELINE_FILE, 'utf8')) : null;
  if (!baseline) console.log(`  ${Y}⚠  Aucun baseline — lance d'abord: runner baseline${E}`);

  for (const scenario of SCENARIOS) {
    const stats = await runScenario(scenario);
    if (!stats || !baseline?.scenarios?.[scenario]) continue;
    const prev = baseline.scenarios[scenario];
    const deltaP95 = stats.p95_ms - prev.p95_ms;
    const pct = prev.p95_ms ? Math.round(deltaP95 / prev.p95_ms * 1000) / 10 : 0;
    if (pct > 20) console.log(`  ${R}⚠  Régression p95 ${scenario} : ${prev.p95_ms}ms → ${stats.p95_ms}ms (+${pct}%)${E}`);
    else console.log(`  ${G}✓ p95 ${scenario} stable : ${prev.p95_ms}ms → ${stats.p95_ms}ms (${pct >= 0 ? '+' : ''}${pct}%)${E}`);
  }
}

// ── Main ──────────────────────────────────────────────────────────────────────
async function main() {
  const [cmd] = process.argv.slice(2).filter(a => !a.startsWith('--'));
  await llm.assertRunning();

  switch (cmd) {
    case 'run':        await cmdRun();               break;
    case 'smoke':       await runScenario('smoke');   break;
    case 'load':        await runScenario('load');    break;
    case 'stress':      await runScenario('stress');  break;
    case 'regression':  await cmdRegression();        break;
    case 'baseline':    cmdBaseline();                break;
    default:
      console.log(`
${B}Runner Agent${E} — Exécution des scénarios k6

  run              Lance smoke → load → stress + résumé LLM
  smoke            Lance uniquement le scénario smoke
  load             Lance uniquement le scénario load
  stress           Lance uniquement le scénario stress
  regression       Compare p95 actuel vs baseline
  baseline         Sauvegarde le baseline actuel (p95/avg/error_rate)

Options:
  --dry-run        Simulation sans exécution ni écriture
  --no-dashboard   Désactive l'export du dashboard HTML natif k6
`);
  }
}

main().catch(e => { console.error(R + e.message + E); process.exit(1); });
