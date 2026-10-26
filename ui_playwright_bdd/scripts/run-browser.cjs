'use strict';
const path = require('node:path');
const fs = require('node:fs');
const { execute } = require('./agents/shared/pipeline-runtime');

async function main() {
  const [browser, ...extra] = process.argv.slice(2);
  if (!['chromium', 'firefox'].includes(browser)) throw new Error('Expected chromium or firefox');
  const root = path.resolve(__dirname, '..');
  if (!fs.existsSync(require('playwright')[browser].executablePath())) {
    throw new Error(`${browser} executable missing. Run: node node_modules/playwright-core/cli.js install --force ${browser}`);
  }
  const execution = require('./agents/shared/run-context').newExecution(root, { ...process.env, QA_EXECUTION_MANAGED: 'false' });
  const { resultsDir, runId } = execution;
  fs.mkdirSync(resultsDir, { recursive: true });
  fs.mkdirSync(path.join(root, 'logs'), { recursive: true });
  const manifest = { runId, browser, startedAt: Date.now(), completed: false, exitCode: null, resultCount: 0,
    sourceHash: require('./agents/shared/review-context').sourceHash(root), tags: '' };
  const manifestFile = path.join(resultsDir, 'run-manifest.json');
  fs.writeFileSync(manifestFile, JSON.stringify(manifest));
  const pointer = JSON.stringify({ runId });
  fs.writeFileSync(path.join(root, 'logs', `latest-${browser}-run.json`), pointer);
  fs.writeFileSync(path.join(root, 'logs', 'latest-test-run.json'), pointer);
  const messages = path.join(resultsDir, 'cucumber-messages.ndjson');
  const args = [path.join(root, 'node_modules/@cucumber/cucumber/bin/cucumber.js'),
    'src/features/**/*.feature', '--retry', '1',
    '--require-module', 'ts-node/register', '--require', 'src/core/world.ts',
    '--require', 'src/hooks/**/*.ts', '--require', 'src/steps/**/*.ts',
    '--format', 'progress', '--format', `"allure-cucumberjs/reporter":"${path.join(resultsDir, 'formatter.log')}"`,
    '--format-options', JSON.stringify({ resultsDir }), '--format', `"message":"${messages}"`, ...extra];
  console.log(`[${browser}] Starting local Cucumber; results: ${resultsDir}`);
  const started = Date.now();
  const heartbeat = setInterval(() => console.log(`[${browser}] Running (${Math.round((Date.now() - started) / 1000)}s)`), 15000);
  try {
    const result = await execute(process.execPath, args, { cwd: root, verbose: true,
      env: { ...execution.env, TEST_BROWSER: browser, TEST_HEADLESS: process.env.TEST_HEADLESS || 'true' },
      logFile: path.join(resultsDir, 'runner.log'), timeout: process.env.RUNNER_TIMEOUT_MS || 1800000 });
    const finished = fs.existsSync(messages) && fs.readFileSync(messages, 'utf8').split(/\r?\n/).filter(Boolean)
      .some(line => { try { return !!JSON.parse(line).testRunFinished; } catch { return false; } });
    Object.assign(manifest, { finishedAt: Date.now(), completed: finished && !result.timedOut && !result.error,
      exitCode: result.exitCode, resultCount: require('./agents/shared/pipeline-runtime').readResults(resultsDir).results.length });
    fs.writeFileSync(manifestFile, JSON.stringify(manifest, null, 2));
    console.log(`[${browser}] Finished: exit=${result.exitCode}, timeout=${result.timedOut}; run=${runId}`);
    if (result.error) console.error(result.error);
    process.exitCode = result.success ? 0 : 1;
  } finally { clearInterval(heartbeat); }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
