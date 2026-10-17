'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { prepareHistory, saveHistory } = require('../shared/allure-history');
const { execute } = require('../shared/pipeline-runtime');
function temporary(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-allure-history-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 }));
  return root;
}
function fixture(root, id, start, tags = '@smoke', completed = true) {
  const input = path.join(root, 'allure-runs', id, 'results');
  fs.mkdirSync(input, { recursive: true });
  fs.writeFileSync(path.join(input, 'run-manifest.json'), JSON.stringify({ runId: id, startedAt: start,
    finishedAt: start + 100, tags, completed, resultCount: 1, exitCode: id === 'first' ? 1 : 0 }));
  fs.writeFileSync(path.join(input, id + '-result.json'), JSON.stringify({ uuid: id, historyId: 'stable-test',
    name: 'Example test', fullName: 'Example test', status: id === 'first' ? 'failed' : 'passed', start: start + 10, stop: start + 90 }));
  return input;
}
function fakeReport(output, order) {
  fs.mkdirSync(path.join(output, 'history'), { recursive: true });
  fs.writeFileSync(path.join(output, 'history/history-trend.json'), JSON.stringify([{ buildOrder: order, data: { total: 1 } }]));
  fs.writeFileSync(path.join(output, 'history/history.json'), '{}');
}
test('history is isolated by selection and excludes current/future/incomplete runs', t => {
  const root = temporary(t);
  const first = fixture(root, 'first', 1000), second = fixture(root, 'second', 2000);
  const prep = prepareHistory(root, first, {}), report = path.join(root, 'first-report');
  fakeReport(report, 1000);
  saveHistory(prep, report);
  prepareHistory(root, second, {});
  assert.equal(JSON.parse(fs.readFileSync(path.join(second, 'history/history-trend.json')))[0].buildOrder, 1000);
  const other = fixture(root, 'regression', 3000, '@regression');
  prepareHistory(root, other, {});
  assert.equal(fs.existsSync(path.join(other, 'history/history-trend.json')), false);
  const incomplete = fixture(root, 'incomplete', 4000, '@smoke', false);
  assert.equal(prepareHistory(root, incomplete, {}), null);
  prepareHistory(root, first, {});
  assert.equal(fs.existsSync(path.join(first, 'history/history-trend.json')), false, 'Never import own report');
});
test('existing isolated reports seed history without rerunning tests', t => {
  const root = temporary(t), first = fixture(root, 'first', 1000), second = fixture(root, 'second', 2000);
  fakeReport(path.join(path.dirname(first), 'report'), 1000);
  prepareHistory(root, second, {});
  assert.equal(JSON.parse(fs.readFileSync(path.join(second, 'history/history-trend.json'))).length, 1);
});
test('traditional reports retain their history when initializing the cache', t => {
  const root = temporary(t), input = path.join(root, 'allure-results');
  fs.mkdirSync(input);
  fs.writeFileSync(path.join(input, 'new-result.json'), JSON.stringify({ uuid: 'new', start: 2000, stop: 2090, status: 'passed' }));
  const output = path.join(root, 'allure-report');
  fakeReport(output, 1000);
  fs.mkdirSync(path.join(output, 'widgets'));
  fs.writeFileSync(path.join(output, 'widgets/summary.json'), JSON.stringify({ time: { start: 1000 } }));
  prepareHistory(root, input, {});
  assert.equal(JSON.parse(fs.readFileSync(path.join(input, 'history/history-trend.json')))[0].buildOrder, 1000);
});
test('history cache retains at most twenty execution snapshots', t => {
  const root = temporary(t), output = path.join(root, 'generated-report');
  let prepared;
  for (let index = 0; index < 21; index++) {
    prepared = prepareHistory(root, fixture(root, 'run-' + index, 1000 + index), {});
    fakeReport(output, 1000 + index);
    saveHistory(prepared, output);
  }
  const snapshots = fs.readdirSync(prepared.cache).map(name => JSON.parse(fs.readFileSync(path.join(prepared.cache, name))));
  assert.equal(snapshots.length, 20);
  assert.equal(snapshots.some(snapshot => snapshot.run.id === 'run-0'), false);
});
test('real Allure renders two trend points and regeneration does not duplicate the current run', async t => {
  const root = temporary(t);
  const project = path.resolve(__dirname, '../../..');
  const generate = async input => {
    const output = path.join(path.dirname(input), 'report');
    const prepared = prepareHistory(root, input, {});
    const result = await execute(process.execPath, [path.join(project, 'node_modules/allure-commandline/bin/allure'),
      'generate', input, '-o', output, '--clean'], { cwd: project, timeout: 180000 });
    assert.equal(result.success, true, result.stderr || result.stdout);
    saveHistory(prepared, output);
    return output;
  };
  const first = fixture(root, 'first', 1000), second = fixture(root, 'second', 2000);
  await generate(first);
  const output = await generate(second);
  const trend = () => JSON.parse(fs.readFileSync(path.join(output, 'widgets/history-trend.json')));
  assert.equal(trend().length, 2);
  assert.equal(trend()[0].data.passed, 1);
  assert.equal(trend()[1].data.failed, 1);
  await generate(second);
  assert.equal(trend().length, 2);
  assert.equal(JSON.parse(fs.readFileSync(path.join(output, 'widgets/summary.json'))).statistic.total, 1);
  assert.equal(JSON.parse(fs.readFileSync(path.join(second, 'second-result.json'))).status, 'passed');
});
