'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { main } = require('../../browser-dashboard');
const { metrics, writeEnvironment } = require('../shared/allure-environment');
function fixture(t) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'allure-environment-'));
  t.after(async () => { assert.equal(path.dirname(path.resolve(dir)), path.resolve(os.tmpdir())); await fs.promises.rm(dir, { recursive: true, force: true, maxRetries: 10, retryDelay: 200 }); });
  const write = (file, value) => fs.writeFileSync(path.join(dir, file), JSON.stringify(value));
  const result = (uuid, historyId, status, start, stop) => write(uuid + '-result.json', { uuid, historyId, name: historyId, status, start, stop, labels: [{ name: 'browser', value: 'chromium' }] });
  return { dir, write, result };
}
test('global metrics use final attempts while gate preserves failures and flaky evidence', t => {
  const f = fixture(t);
  f.result('a', 'login', 'failed', 1000, 1500);
  f.result('b', 'login', 'passed', 2000, 3000);
  f.result('c', 'other', 'broken', 1000, 4000);
  f.write('run-manifest.json', { runId: 'run-1', completed: true, startedAt: 1000, finishedAt: 4000, resultCount: 3, exitCode: 1 });
  const m = metrics(f.dir, main(f.dir), '2026-10-15T00:00:00Z');
  assert.equal(m['Total.TCs'], '2'); assert.equal(m['Pass.Rate'], '50.00%');
  assert.equal(m['Fail.Rate'], '0.00%'); assert.equal(m['Broken.Rate'], '50.00%');
  assert.equal(m['Anomaly.Rate'], '50.00%'); assert.equal(m['Flaky.Tests'], '1');
  assert.equal(m['Execution.Time'], '3.000 s'); assert.equal(m['Avg.Test.Duration'], '2.000 s');
  assert.equal(m['Quality.Gate'], 'FAIL'); assert.equal(m['Gate.Criteria.Passed'], '5/7');
  assert.equal(m['Gate.Blockers'], 'Runner did not succeed | Some tests failed, broke, were skipped or have unknown status');
});
test('passing run, coverage scoped to run, and environment metadata are rendered once', t => {
  const f = fixture(t);
  f.result('a', 'login', 'passed', 1000, 2000);
  f.write('run-manifest.json', { runId: 'run-1', completed: true, startedAt: 1000, finishedAt: 2000, resultCount: 1, exitCode: 0 });
  f.write('automation-coverage.json', { schemaVersion: 1, runId: 'run-1', scope: 'Lot approuvé', totalTestCases: 10, automatedTestCases: 6 });
  f.write('hook-container.json', { children: ['a'], befores: [{ attachments: [{ type: 'text/plain', source: 'target.txt' }] }] });
  fs.writeFileSync(path.join(f.dir, 'target.txt'), 'Base URL: https://user:secret@example.test/app?token=private');
  fs.writeFileSync(path.join(f.dir, 'environment.properties'), 'team=QA\nPass.Rate=old\n');
  const d = main(f.dir), m = writeEnvironment(f.dir, d);
  assert.equal(m['Quality.Gate'], 'PASS'); assert.equal(m['Gate.Criteria.Passed'], '7/7');
  assert.match(m['Automation.Coverage'], /^60.00%/); assert.equal(m['API.Under.Test'], 'https://example.test/app');
  assert.match(m['LLM.Engine'], /^NOT_RECORDED/);
  writeEnvironment(f.dir, d);
  const properties = fs.readFileSync(path.join(f.dir, 'environment.properties'), 'utf8');
  assert.equal(properties.match(/^Pass.Rate=/gm).length, 1); assert.match(properties, /team=QA/);
  assert.doesNotMatch(properties, /secret|token=private/);
  assert.doesNotMatch(properties, /^(?:tests_execution_time|chromium_(?:total|passed|failed|pass_rate|failure_rate|execution_time))=/m);
  assert.match(properties, /^chromium_skipped=0$/m);
  assert.match(properties, /^chromium_broken=0$/m);
  // Re-generating the browser dashboard must not reintroduce the duplicates.
  writeEnvironment(f.dir, main(f.dir));
  assert.equal(fs.readFileSync(path.join(f.dir, 'environment.properties'), 'utf8').replace(/^Report.Generated=.*$/m, ''), properties.replace(/^Report.Generated=.*$/m, ''));
  f.write('automation-coverage.json', { schemaVersion: 1, runId: 'old-run', scope: 'Lot', totalTestCases: 10, automatedTestCases: 10 });
  assert.match(metrics(f.dir, d)['Automation.Coverage'], /^NOT_EVALUATED/);
});
test('multi-browser reports retain their breakdown alongside global metrics', t => {
  const f = fixture(t);
  f.result('a', 'login', 'passed', 1000, 2000);
  f.write('b-result.json', { uuid: 'b', historyId: 'login', status: 'failed', start: 1000, stop: 3000, labels: [{ name: 'browser', value: 'firefox' }] });
  writeEnvironment(f.dir, main(f.dir));
  const properties = fs.readFileSync(path.join(f.dir, 'environment.properties'), 'utf8');
  assert.match(properties, /^Total.TCs=2$/m);
  assert.match(properties, /^chromium_total=1$/m);
  assert.match(properties, /^firefox_total=1$/m);
  assert.doesNotMatch(properties, /^tests_execution_time=/m);
});
test('empty, corrupt and untimed results never yield fabricated rates or durations', t => {
  const f = fixture(t);
  let m = metrics(f.dir, {});
  assert.equal(m['Quality.Gate'], 'NOT_EVALUATED'); assert.equal(m['Pass.Rate'], 'NOT_EVALUATED');
  assert.equal(m['Execution.Time'], 'NOT_EVALUATED');
  f.result('a', 'untimed', 'passed', null, null);
  m = metrics(f.dir, main(f.dir));
  assert.equal(m['Avg.Test.Duration'], 'NOT_EVALUATED');
  fs.writeFileSync(path.join(f.dir, 'bad-result.json'), '{bad');
  m = metrics(f.dir, main(f.dir));
  assert.equal(m['Pass.Rate'], 'NOT_EVALUATED'); assert.equal(m['Total.TCs'], 'NOT_EVALUATED');
});
