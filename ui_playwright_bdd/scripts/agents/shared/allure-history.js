'use strict';
const fs = require('fs');
const path = require('path');
const { createHash } = require('crypto');
const { readResults } = require('./pipeline-runtime');
const FILES = ['history.json', 'history-trend.json', 'duration-trend.json', 'retry-trend.json', 'categories-trend.json'];
const hash = text => createHash('sha256').update(text).digest('hex');
function json(file) { return JSON.parse(fs.readFileSync(file, 'utf8')); }
function describe(input, env = {}) {
  const { results, errors } = readResults(input);
  if (errors.length || !results.length) return null;
  const manifestFile = path.join(input, 'run-manifest.json');
  const manifest = fs.existsSync(manifestFile) ? json(manifestFile) : null;
  if (manifest && (manifest.completed !== true || manifest.resultCount !== results.length)) return null;
  const startedAt = manifest?.startedAt ?? Math.min(...results.map(r => r.start));
  if (!Number.isFinite(startedAt)) return null;
  const scope = env.ALLURE_HISTORY_KEY || manifest?.tags || path.basename(input);
  const id = manifest?.runId || hash(JSON.stringify(results.map(r => [r.uuid, r.start, r.stop]).sort()));
  return { id, scope, startedAt };
}
function readHistory(dir) {
  const files = {};
  for (const name of FILES) {
    const file = path.join(dir, name);
    if (!fs.existsSync(file)) continue;
    const data = json(file);
    if (name === 'history.json' ? !data || Array.isArray(data) || typeof data !== 'object' : !Array.isArray(data)) throw new Error('Invalid Allure history: ' + name);
    files[name] = data;
  }
  return files['history-trend.json']?.length ? files : null;
}
function cacheDirectory(root, env) { return path.resolve(root, env.ALLURE_HISTORY_DIR || '.allure-history'); }
function prepareHistory(root, input, env = process.env) {
  const run = describe(input, env);
  if (!run) return null; // Incomplete executions must not pollute the trend.
  const candidates = [];
  const cache = path.join(cacheDirectory(root, env), hash(run.scope));
  function consider(candidate) {
    if (candidate?.run?.scope === run.scope && candidate.run.id !== run.id && candidate.run.startedAt < run.startedAt && candidate.files?.['history-trend.json']?.length) candidates.push(candidate);
  }
  if (fs.existsSync(cache)) {
    for (const name of fs.readdirSync(cache).filter(n => n.endsWith('.json'))) {
      try { consider(json(path.join(cache, name))); } catch { console.warn('Ignored unreadable Allure history cache: ' + name); }
    }
  }
  // Preserve the existing history of traditional npm test / allure-results runs.
  if (!env.ALLURE_HISTORY_KEY && !fs.existsSync(path.join(input, 'run-manifest.json'))) {
    try {
      const report = path.join(path.dirname(input), 'allure-report');
      const files = readHistory(path.join(report, 'history'));
      const summary = json(path.join(report, 'widgets/summary.json'));
      consider({ run: { id: 'legacy-' + files?.['history-trend.json'][0]?.buildOrder,
        scope: run.scope, startedAt: summary.time.start }, files });
    } catch { /* No previous compatible legacy report. */ }
  }
  // Bootstrap from existing isolated reports, without rerunning their tests.
  const runs = path.join(root, 'allure-runs');
  if (fs.existsSync(runs) && !env.ALLURE_HISTORY_KEY) {
    for (const entry of fs.readdirSync(runs, { withFileTypes: true }).filter(e => e.isDirectory())) {
      try {
        const dir = path.join(runs, entry.name);
        const previous = describe(path.join(dir, 'results'));
        if (previous?.scope === run.scope && previous.id !== run.id && previous.startedAt < run.startedAt) {
          consider({ run: previous, files: readHistory(path.join(dir, 'report/history')) });
        }
      } catch { /* A missing or corrupt old report is not historical evidence. */ }
    }
  }
  // The cached version wins ties: it may contain more history than an old report.
  candidates.sort((a, b) => b.run.startedAt - a.run.startedAt);
  const previous = candidates[0];
  const target = path.join(input, 'history');
  fs.mkdirSync(target, { recursive: true });
  for (const name of FILES) {
    const file = path.join(target, name);
    if (previous?.files[name]) fs.writeFileSync(file, JSON.stringify(previous.files[name]));
    else if (fs.existsSync(file)) fs.unlinkSync(file);
  }
  const executorFile = path.join(input, 'executor.json');
  const executor = fs.existsSync(executorFile) ? json(executorFile) : {};
  fs.writeFileSync(executorFile, JSON.stringify({ ...executor,
    name: executor.name || 'Playwright Cucumber', type: executor.type || 'local',
    buildOrder: Number.isFinite(executor.buildOrder) ? executor.buildOrder : run.startedAt,
    buildName: executor.buildName || run.id,
    reportName: `Playwright BDD · ${run.scope} · ${new Date(run.startedAt).toISOString()}`,
  }, null, 2));
  console.log(previous ? `Allure trend: history restored from ${previous.run.id}` : 'Allure trend: first execution in this series');
  return { run, cache };
}
function saveHistory(prepared, output) {
  if (!prepared) return;
  const files = readHistory(path.join(output, 'history'));
  if (!files) throw new Error('Allure did not generate trend history');
  fs.mkdirSync(prepared.cache, { recursive: true });
  const file = path.join(prepared.cache, hash(prepared.run.id) + '.json');
  fs.writeFileSync(file + '.tmp', JSON.stringify({ run: prepared.run, files }));
  fs.renameSync(file + '.tmp', file);
  // Bound disk/cache growth as well as the native Allure graph's 20-run window.
  const snapshots = fs.readdirSync(prepared.cache).filter(name => /^[a-f0-9]{64}\.json$/.test(name))
    .flatMap(name => {
      try { return [{ name, startedAt: json(path.join(prepared.cache, name)).run.startedAt }]; }
      catch { return []; }
    })
    .sort((a, b) => b.startedAt - a.startedAt);
  for (const stale of snapshots.slice(20)) fs.unlinkSync(path.join(prepared.cache, stale.name));
}
module.exports = { describe, prepareHistory, saveHistory };
