'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { readResults, checkRun } = require('./pipeline-runtime');
const NA = 'NOT_EVALUATED';
function safeUrl(value) {
  try { const u = new URL(value); return ['http:', 'https:'].includes(u.protocol) ? u.origin + u.pathname : null; }
  catch { return null; }
}
function metrics(directory, dashboard, generated = new Date().toISOString()) {
  const data = readResults(directory), gate = checkRun(directory);
  const m = gate.manifest;
  const ds = Object.values(dashboard);
  const sum = key => ds.reduce((n, d) => n + (d[key] || 0), 0);
  const total = sum('total');
  const pct = n => total && !data.errors.length ? (100 * n / total).toFixed(2) + '%' : NA;
  const timed = ds.filter(d => d.durationMs !== null);
  const validTimes = total > 0 && sum('timedTests') === total && !data.errors.length;
  const seconds = value => (value / 1000).toFixed(3) + ' s';
  const criteria = [
    ['Results missing or unreadable', data.results.length > 0 && data.errors.length === 0],
    ['Execution ID missing', typeof m?.runId === 'string' && m.runId.length > 0],
    ['Execution incomplete, timed out or interrupted', m?.completed === true && !m.timedOut && !m.error],
    ['Runner did not succeed', m?.exitCode === 0],
    ['Result count does not match manifest', m?.resultCount === data.results.length],
    ['Execution period missing or inconsistent', Number.isFinite(m?.startedAt) && Number.isFinite(m?.finishedAt) && m.finishedAt >= m.startedAt && data.results.every(r => Number.isFinite(r.start) && Number.isFinite(r.stop) && r.start >= m.startedAt && r.stop >= r.start && r.stop <= m.finishedAt)],
    ['Some tests failed, broke, were skipped or have unknown status', data.results.length > 0 && data.results.every(r => r.status === 'passed')],
  ];
  const blockers = [...new Set([...gate.reasons, ...criteria.filter(([, ok]) => !ok).map(([name]) => name)])];
  let coverage = NA + ' - reference test inventory missing';
  try {
    const c = JSON.parse(fs.readFileSync(path.join(directory, 'automation-coverage.json'), 'utf8'));
    if (m?.runId && c.runId === m.runId && c.schemaVersion === 1 && typeof c.scope === 'string' && c.scope.trim() &&
        Number.isSafeInteger(c.totalTestCases) && c.totalTestCases > 0 && Number.isSafeInteger(c.automatedTestCases) && c.automatedTestCases >= 0 && c.automatedTestCases <= c.totalTestCases) {
      coverage = `${(100 * c.automatedTestCases / c.totalTestCases).toFixed(2)}% (${c.automatedTestCases}/${c.totalTestCases}) - ${c.scope}`;
    } else coverage = NA + ' - invalid or mismatched reference inventory';
  } catch { /* Never derive requirement coverage from execution success. */ }
  const targets = new Set();
  if (safeUrl(m?.baseUrl)) targets.add(safeUrl(m.baseUrl));
  // Only explicit Base URL hook attachments from this run, never the current .env.
  for (const name of fs.readdirSync(directory).filter(n => n.endsWith('-container.json'))) {
    try {
      const c = JSON.parse(fs.readFileSync(path.join(directory, name), 'utf8'));
      if (!c.children?.some(id => data.results.some(r => r.uuid === id))) continue;
      const visit = node => {
        for (const a of node.attachments || []) {
          if (a.type !== 'text/plain' || typeof a.source !== 'string' || path.basename(a.source) !== a.source) continue;
          const file = path.join(directory, a.source);
          const stat = fs.lstatSync(file);
          if (stat.isSymbolicLink() || stat.size > 4096) continue;
          const match = fs.readFileSync(file, 'utf8').match(/^Base URL:\s*(https?:\/\/\S+)\s*$/);
          if (match && safeUrl(match[1])) targets.add(safeUrl(match[1]));
        }
        for (const step of node.steps || []) visit(step);
      };
      for (const hook of [...(c.befores || []), ...(c.afters || [])]) visit(hook);
    } catch { /* Missing attachments do not establish an application URL. */ }
  }
  return {
    'Quality.Gate': !m ? NA : gate.allowed && criteria.every(([, ok]) => ok) ? 'PASS' : 'FAIL',
    'Gate.Criteria.Passed': `${criteria.filter(([, ok]) => ok).length}/${criteria.length}`,
    'Gate.Blockers': blockers.length ? blockers.join(' | ') : 'None',
    'Pass.Rate': pct(sum('passed')), 'Fail.Rate': pct(sum('failed')), 'Broken.Rate': pct(sum('broken')),
    'Anomaly.Rate': pct(sum('failed') + sum('broken')),
    'Flaky.Tests': data.errors.length ? NA : String(sum('flaky')),
    'Automation.Coverage': coverage,
    'Total.TCs': data.errors.length ? NA : String(total),
    Passed: data.errors.length ? NA : String(sum('passed')), Failed: data.errors.length ? NA : String(sum('failed')),
    'Execution.Time': validTimes ? seconds(Math.max(...timed.map(d => d.stop)) - Math.min(...timed.map(d => d.start))) : NA,
    'Avg.Test.Duration': validTimes ? seconds(sum('durationTotalMs') / total) : NA,
    Framework: 'Playwright + Cucumber / TypeScript | Python LangChain + LangGraph agents',
    'LLM.Engine': m?.llmEngine || 'NOT_RECORDED - model usage not established for this run',
    'API.Under.Test': [...targets].join(' | ') || 'NOT_RECORDED - application target unavailable',
    'Report.Generated': generated,
  };
}
function escape(value) {
  return String(value).replace(/\\/g, '\\\\').replace(/\r/g, '\\r').replace(/\n/g, '\\n').replace(/\t/g, '\\t')
    .replace(/[^\x20-\x7e]/g, ch => '\\u' + ch.charCodeAt(0).toString(16).padStart(4, '0'));
}
function writeEnvironment(directory, dashboard) {
  const values = metrics(directory, dashboard);
  const file = path.join(directory, 'environment.properties');
  const existing = fs.existsSync(file) ? fs.readFileSync(file, 'utf8').split(/\r?\n/) : [];
  const owned = new Set(Object.keys(values));
  // One browser has the same scope as the global metrics. Keep complementary
  // counters and keep the full browser breakdown for multi-browser runs.
  const redundant = new Set(['tests_execution_time', 'chromium_broken',
    'chromium_skipped', 'chromium_unknown', 'chromium_retried', 'chromium_retry_rate']);
  const browsers = Object.keys(dashboard);
  if (browsers.length === 1) {
    for (const suffix of ['total', 'passed', 'failed', 'pass_rate', 'failure_rate', 'execution_time']) {
      redundant.add(`${browsers[0]}_${suffix}`);
    }
  }
  const preserved = existing.filter(line => {
    const key = line.split(/[=:]/, 1)[0].trim();
    return line.trim() && !owned.has(key) && !redundant.has(key);
  });
  fs.writeFileSync(file, [...Object.entries(values).map(([key, value]) => `${key}=${escape(value)}`), ...preserved, ''].join('\n'));
  fs.writeFileSync(path.join(directory, 'report-metrics.json'), JSON.stringify({ schemaVersion: 1, metrics: values }, null, 2));
  return values;
}
module.exports = { metrics, writeEnvironment };
