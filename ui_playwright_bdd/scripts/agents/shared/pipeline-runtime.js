'use strict';
const fs = require('fs');
const path = require('path');
const { spawn, spawnSync } = require('child_process');

function timeoutMs(value, fallback) {
  if (value === undefined) return fallback;
  const n = Number(value);
  if (!Number.isSafeInteger(n) || n <= 0) throw new Error('Timeout must be a positive integer (milliseconds)');
  return n;
}

// Kill the whole process tree, including Cucumber workers and browsers.
function execute(command, args, options = {}) {
  const timeout = timeoutMs(options.timeout, 300000);
  const metrics = require('./task-metrics');
  const baseEnv = options.env || process.env;
  const entry = args.find(arg => /\.[cm]?js$/.test(arg)) || command;
  const operation = args[args.indexOf(entry) + 1];
  const operations = new Set('run smoke critical regression full quick nightly status report metrics anomalies cost gate advise analyze triage rca flaky verify coverage spec tc repair loop dashboard sync generate publish notify commit push pr release create approve reject block list help index search'.split(' '));
  const label = options.taskLabel || [path.basename(entry), operations.has(operation) ? operation : ''].filter(Boolean).join(' ');
  const task = metrics.startTask(label, baseEnv);
  return new Promise(resolve => {
    const started = Date.now();
    let timedOut = false, error = null, stdout = '', stderr = '';
    const child = spawn(command, args, {
      cwd: options.cwd, env: { ...baseEnv, QA_METRICS_TASK_ID: task.taskId,
        QA_GATEWAY_BUDGET_ID: baseEnv.QA_GATEWAY_BUDGET_ID || task.taskId }, windowsHide: true,
      detached: process.platform !== 'win32', stdio: ['ignore', 'pipe', 'pipe'],
    });
    let log;
    if (options.logFile) {
      log = fs.createWriteStream(options.logFile);
      log.on('error', e => { error = `Log write failed: ${e.message}`; });
    }
    const record = (kind, data) => {
      const text = data.toString();
      if (kind === 'stdout') stdout = (stdout + text).slice(-64000);
      else stderr = (stderr + text).slice(-64000);
      if (log) log.write(data);
      if (options.verbose) process[kind].write(data);
    };
    child.stdout.on('data', data => record('stdout', data));
    child.stderr.on('data', data => record('stderr', data));
    child.on('error', e => { error = e.message; });
    const timer = setTimeout(() => {
      timedOut = true;
      if (child.pid) {
        if (process.platform === 'win32') {
          const killed = spawnSync('taskkill.exe', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, timeout: 15000 });
          if (killed.error || killed.status !== 0) { error = 'Could not confirm process tree termination'; child.kill('SIGKILL'); }
        } else {
          try { process.kill(-child.pid, 'SIGKILL'); } catch { child.kill('SIGKILL'); }
        }
      }
    }, timeout);
    child.on('close', (exitCode, signal) => {
      clearTimeout(timer);
      if (log) log.end();
      const result = { success: !error && !timedOut && exitCode === 0, exitCode, signal,
        timedOut, error, stdout, stderr, durationMs: Date.now() - started, metricsTaskId: task.taskId };
      metrics.endTask(task, result, baseEnv);
      resolve(result);
    });
  });
}

function readResults(dir) {
  const results = [], errors = [];
  if (!fs.existsSync(dir)) return { results, errors: ['Results directory missing'] };
  for (const name of fs.readdirSync(dir).filter(f => f.endsWith('-result.json'))) {
    try {
      const result = JSON.parse(fs.readFileSync(path.join(dir, name), 'utf8'));
      if (!result || typeof result !== 'object' || Array.isArray(result)) throw new Error('Invalid result object');
      results.push(result);
    }
    catch (e) { errors.push(`${name}: ${e.message}`); }
  }
  return { results, errors };
}

function checkRun(dir, expectedRunId) {
  const { results, errors } = readResults(dir);
  let manifest;
  try { manifest = JSON.parse(fs.readFileSync(path.join(dir, 'run-manifest.json'), 'utf8')); }
  catch { errors.push('No execution manifest: freshness/completeness unverified'); }
  if (expectedRunId && manifest?.runId !== expectedRunId) errors.push('Execution ID mismatch');
  if (manifest?.completed !== true) errors.push('Execution incomplete');
  if (!Number.isFinite(manifest?.startedAt) || !Number.isFinite(manifest?.finishedAt)) errors.push('Execution timestamps missing');
  if (manifest?.finishedAt < manifest?.startedAt) errors.push('Execution timestamps inconsistent');
  if (manifest?.exitCode !== 0) errors.push('Runner did not succeed');
  if (!results.length) errors.push('No test results');
  if (manifest?.resultCount !== results.length) errors.push('Result count does not match manifest');
  if (results.some(r => !Number.isFinite(r.start) || r.start < manifest?.startedAt ||
      !Number.isFinite(r.stop) || r.stop < r.start || r.stop > manifest?.finishedAt)) errors.push('Results outside execution period');
  if (results.some(r => r.status !== 'passed')) errors.push('Some tests failed, broke, were skipped or have unknown status');
  return { allowed: errors.length === 0, reasons: errors, manifest, count: results.length };
}

function resultDirectory(root, env = process.env) {
  if (env.ALLURE_RESULTS_DIR) return path.resolve(root, env.ALLURE_RESULTS_DIR);
  const latest = path.join(root, 'logs', 'latest-test-run.json');
  if (fs.existsSync(latest)) {
    // Keep traditional npm test/allure workflows usable after an agent run.
    const legacy = path.join(root, 'allure-results');
    if (fs.existsSync(legacy) && fs.readdirSync(legacy).some(name => name.endsWith('-result.json') &&
      fs.statSync(path.join(legacy, name)).mtimeMs > fs.statSync(latest).mtimeMs)) return legacy;
    const run = JSON.parse(fs.readFileSync(latest, 'utf8'));
    return path.join(root, 'allure-runs', path.basename(run.runId), 'results');
  }
  return path.join(root, 'allure-results');
}

function recordVerification(taskId, status, env = process.env) {
  if (taskId) require('./task-metrics').write({ type: 'task_verification', taskId, status }, env);
}
module.exports = { execute, timeoutMs, readResults, checkRun, resultDirectory, recordVerification };
