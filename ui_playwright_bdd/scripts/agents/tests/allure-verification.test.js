'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { buildAllureSummary, allureVerdict } = require('../shared/allure-verification');

const AGENTS = path.resolve(__dirname, '..');
const FRAMEWORK = path.resolve(AGENTS, '../..');
const RESULTS = path.join(FRAMEWORK, 'allure-results');
const REPORT = path.join(FRAMEWORK, 'docs/verify-report.json');

let sequence = 0;
function result(overrides = {}) {
  return {
    uuid: `test-uuid-${sequence++}`, name: 'Login test', status: 'broken',
    // Place the other fields beyond the old 300-character cut-off.
    statusDetails: { message: 'Navigation timeout. '.repeat(100), trace: 'Complete stack trace' },
    start: 1700000000000, stop: 1700000001000, stage: 'finished',
    steps: [{ name: 'Open login page', status: 'broken' }],
    labels: [{ name: 'browser', value: 'chromium' }],
    attachments: [], parameters: [], links: [], fullName: 'features/login.feature:10',
    historyId: 'login-history', testCaseId: 'login-case', ...overrides,
  };
}

function summarize(entries) {
  return buildAllureSummary(Object.keys(entries), file => {
    if (entries[file] instanceof Error) throw entries[file];
    return entries[file];
  });
}

test('complete JSON preserves fields beyond character 300 without sending raw fragments', () => {
  const original = JSON.stringify(result());
  assert.throws(() => JSON.parse(original.slice(0, 300)));
  const summary = summarize({ 'login-result.json': original });
  const sample = summary.samples[0];
  assert.equal(summary.parsedJsonFiles, 1);
  assert.deepEqual(summary.errors, []);
  for (const key of ['start', 'stop', 'steps', 'labels']) {
    assert.ok(sample.presentFields.includes(key));
    assert.equal(summary.fieldPresenceCounts[key], 1);
  }
  assert.equal(sample.values.start, 1700000000000);
  assert.equal(sample.values.stop, 1700000001000);
  assert.deepEqual(sample.fields.steps, { present: true, type: 'array', count: 1 });
  assert.equal(sample.fields.statusDetails.trace.present, true);
  assert.equal(sample.fields.statusDetails.message.length, result().statusDetails.message.length);
  assert.equal(JSON.parse(JSON.stringify(summary)).samples[0].values.status, 'broken');
  assert.ok(JSON.stringify(summary).length < original.length);
});

test('all files contribute to presence/status counts even beyond the sample limit', () => {
  const entries = {};
  for (let i = 0; i < 7; i++) {
    const r = result({ name: `Test ${i}`, status: i < 4 ? 'broken' : 'passed' });
    if (i === 6) delete r.labels;
    entries[`${i}-result.json`] = JSON.stringify(r);
  }
  const summary = summarize(entries);
  assert.equal(summary.totalFiles, 7);
  assert.equal(summary.parsedJsonFiles, 7);
  assert.equal(summary.samples.length, 3);
  assert.equal(summary.fieldPresenceCounts.start, 7);
  assert.equal(summary.fieldPresenceCounts.labels, 6);
  assert.deepEqual(summary.statusCounts, { broken: 4, passed: 3 });
  assert.deepEqual(summary.errors, []);
});

test('malformed JSON after the first three files is detected', () => {
  const summary = summarize({
    '1-result.json': JSON.stringify(result()),
    '2-result.json': JSON.stringify(result()),
    '3-result.json': JSON.stringify(result()),
    '4-result.json': '{"status":',
  });
  assert.equal(summary.parsedJsonFiles, 3);
  assert.deepEqual(summary.errors.map(e => [e.file, e.kind]), [['4-result.json', 'invalid_json']]);
});

test('absent, null and empty fields remain distinguishable', () => {
  const r = result({ steps: [], labels: null });
  delete r.attachments;
  const sample = summarize({ 'test-result.json': JSON.stringify(r) }).samples[0];
  assert.deepEqual(sample.fields.steps, { present: true, type: 'array', count: 0 });
  assert.deepEqual(sample.fields.labels, { present: true, type: 'null' });
  assert.deepEqual(sample.fields.attachments, { present: false });
  assert.ok(!sample.presentFields.includes('attachments'));
});

test('unreadable files and non-object JSON are reported separately from syntax errors', () => {
  const summary = summarize({
    'unreadable-result.json': new Error('Private path details'),
    'null-result.json': 'null',
    'array-result.json': '[]',
  });
  assert.equal(summary.parsedJsonFiles, 2);
  assert.equal(summary.resultObjects, 0);
  assert.deepEqual(summary.errors.map(e => e.kind), ['read_error', 'invalid_root', 'invalid_root']);
  assert.doesNotMatch(JSON.stringify(summary), /Private path details/);
});

async function runVerify(entries, { dryRun = false, localOnly = false } = {}) {
  const prompts = [], extractionPrompts = [], output = [], writes = new Map();
  const deps = {
    path,
    fs: {
      mkdirSync() {},
      existsSync: dir => dir === RESULTS,
      readdirSync: () => Object.keys(entries),
      readFileSync: file => entries[path.basename(file)],
      writeFileSync: (file, data) => writes.set(file, data),
    },
    dotenv: { config() {} },
    './shared/agent-verifier': require('../shared/agent-verifier'),
    './llm': {
      MODEL: 'simulated', assertRunning: async () => { throw new Error('Provider unavailable'); },
      chatAdversarial: async messages => {
        prompts.push(messages[0].content);
        throw new Error('No LLM should be called for Allure');
      },
      chatStructured: async messages => {
        extractionPrompts.push(messages[0].content);
        throw new Error('No LLM should be called for Allure');
      },
    },
    './shared/allure-verification': { buildAllureSummary, allureVerdict },
    './shared/source-verification': { verifySources: async () => [] },
    './shared/pipeline-runtime': { resultDirectory: () => RESULTS },
    './shared/memory-store': {}, './shared/prompt-store': {},
    './shared/tracer': { Span: class { begin() { return this; } end() {} } },
  };
  // Execute the real CLI with in-memory results and fake LLM responses.
  await vm.runInNewContext(fs.readFileSync(path.join(AGENTS, 'quality-agent.js'), 'utf8'), {
    __dirname: AGENTS,
    process: {
      env: {}, argv: ['node', 'quality-agent.js', 'verify', ...(dryRun ? ['--dry-run'] : []), ...(localOnly ? ['--local-only'] : [])],
      exit(code) { throw new Error(`Unexpected exit ${code}`); },
    },
    console: { log: (...args) => output.push(args.join(' ')), error: (...args) => output.push(args.join(' ')) },
    require(name) {
      assert.ok(Object.hasOwn(deps, name), `Unexpected dependency: ${name}`);
      return deps[name];
    },
  }, { filename: 'quality-agent.js' });
  return { prompts, extractionPrompts, output: output.join('\n'), writes };
}

test('verify validates complete Allure files locally even when the provider is unavailable', async () => {
  const run = await runVerify({ 'login-result.json': JSON.stringify(result()) });
  assert.equal(run.prompts.length, 0);
  assert.equal(run.extractionPrompts.length, 0);
  const report = JSON.parse(run.writes.get(REPORT));
  assert.equal(report.verdicts[0].verdict, 'VALID');
  assert.equal(report.verdicts[0].method, 'deterministic');
  assert.equal(report.verdicts[0].evidence.checkedResultFiles, 1);
  assert.ok(run.output.includes(report.verdicts[0].reasoning));
});

test('verify cannot let the LLM approve a malformed result file', async () => {
  const run = await runVerify({ 'broken-result.json': '{"status":' });
  assert.equal(run.prompts.length, 0);
  const report = JSON.parse(run.writes.get(REPORT));
  assert.equal(report.verdicts[0].verdict, 'INVALID');
  assert.match(report.verdicts[0].reasoning, /broken-result.json/);
});

test('an empty results directory is not evaluated without a fabricated LLM audit', async () => {
  const run = await runVerify({});
  assert.equal(run.prompts.length, 0);
  assert.equal(JSON.parse(run.writes.get(REPORT)).verdicts[0].verdict, 'NOT_EVALUATED');
});

test('verify dry-run does not write the report', async () => {
  const run = await runVerify({ 'login-result.json': JSON.stringify(result()) }, { dryRun: true });
  assert.equal(run.prompts.length, 0);
  assert.equal(run.writes.size, 0);
});

test('local-only parses Allure files without contacting the LLM', async () => {
  const run = await runVerify({ 'login-result.json': JSON.stringify(result()) }, { localOnly: true });
  assert.equal(run.prompts.length, 0);
  assert.equal(run.extractionPrompts.length, 0);
  const report = JSON.parse(run.writes.get(REPORT));
  assert.equal(report.mode, 'local-only');
  assert.equal(report.verdicts[0].verdict, 'VALID');
  assert.equal(report.verdicts[0].analysisStatus, 'COMPLETE');
});

test('normal SDK output is valid: empty arrays, empty description, passed statusDetails and parameter hash', () => {
  const summary = summarize({ 'passed-result.json': JSON.stringify(result({
    status: 'passed', statusDetails: {}, description: '', titlePath: ['login.feature', 'login'],
    attachments: [], steps: [], labels: [], links: [], parameters: [],
    historyId: 'case-id:d41d8cd98f00b204e9800998ecf8427e',
  })) });
  assert.deepEqual(summary.errors, []);
  assert.equal(allureVerdict(summary).verdict, 'VALID');
});

test('actual SDK-generated empty-parameter historyId is accepted', () => {
  const { getTestResultHistoryId } = require('allure-js-commons/sdk/reporter');
  const data = result({ testCaseId: 'case-id', historyId: undefined, parameters: [] });
  data.historyId = getTestResultHistoryId(data);
  assert.match(data.historyId, /:d41d8cd98f00b204e9800998ecf8427e$/);
  assert.equal(allureVerdict(summarize({ 'a-result.json': JSON.stringify(data) })).verdict, 'VALID');
});

test('all files and nested structures are checked, including defects after the first three files', () => {
  const entries = Object.fromEntries(Array.from({ length: 5 }, (_, i) => [`${i}-result.json`, JSON.stringify(result())]));
  entries['4-result.json'] = JSON.stringify(result({ steps: [{ name: 'outer', steps: [{ status: 'invalid-status', start: 20, stop: 10 }] }] }));
  const summary = summarize(entries);
  assert.equal(summary.checkedResultFiles, 5);
  assert.ok(summary.errors.some(e => e.file === '4-result.json' && e.field === '$.steps[0].steps[0].status'));
  assert.ok(summary.errors.some(e => e.field === '$.steps[0].steps[0].stop'));
  assert.equal(allureVerdict(summary).verdict, 'INVALID');
});

test('duplicate UUIDs fail, while shared historyIds across distinct runs are allowed', () => {
  const first = result({ historyId: 'same-case' });
  const second = result({ historyId: 'same-case' });
  const entries = { 'a-result.json': JSON.stringify(first), 'b-result.json': JSON.stringify(second) };
  assert.equal(allureVerdict(summarize(entries)).verdict, 'VALID');
  second.uuid = first.uuid;
  entries['b-result.json'] = JSON.stringify(second);
  const summary = summarize(entries);
  assert.equal(allureVerdict(summary).verdict, 'INVALID');
  assert.ok(summary.errors.some(e => e.kind === 'duplicate_uuid'));
});

test('incorrect field types and malformed nested objects are concrete defects', () => {
  for (const overrides of [
    { titlePath: 'suite/test' }, { statusDetails: [] }, { labels: [{ name: 'browser', value: 1 }] },
    { stage: 'done' }, { start: '1000' }, { stop: 0 }, { steps: [null] },
    { attachments: [{ name: 'screenshot' }] }, { parameters: [{ name: 'x', value: 'y', mode: 'bad' }] },
    { links: [{ name: 'issue' }] }, { uuid: '' },
  ]) {
    assert.equal(allureVerdict(summarize({ 'a-result.json': JSON.stringify(result(overrides)) })).verdict, 'INVALID', JSON.stringify(overrides));
  }
});

test('optional metadata can be absent and unreadable files are not validated', () => {
  assert.equal(allureVerdict(summarize({ 'a-result.json': '{"uuid":"minimal","status":"unknown"}' })).verdict, 'VALID');
  assert.equal(allureVerdict(summarize({ 'a-result.json': new Error('unreadable') })).verdict, 'NOT_EVALUATED');
});

test('the current Allure directory is checked without modifying its results', t => {
  if (!fs.existsSync(RESULTS)) return t.skip('No local Allure results');
  const files = fs.readdirSync(RESULTS).filter(file => file.endsWith('-result.json'));
  if (!files.length) return t.skip('No local Allure results');
  const summary = buildAllureSummary(files, file => fs.readFileSync(path.join(RESULTS, file), 'utf8'));
  assert.equal(allureVerdict(summary).verdict, 'VALID', JSON.stringify(summary.errors));
  t.diagnostic(`${summary.checkedResultFiles} real Allure result files validated locally`);
});
