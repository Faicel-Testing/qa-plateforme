'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const os = require('os');
const vm = require('vm');
const evidence = require('../shared/analysis-evidence');
function temp(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-evidence-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 }));
  return root;
}
test('source reader preserves late content and reports line ranges and EOF accurately', t => {
  const root = temp(t);
  fs.writeFileSync(path.join(root, 'page.ts'), Array.from({ length: 600 }, (_, i) => `line${i + 1}: ` + 'x'.repeat(80)).join('\n'));
  const first = evidence.readSource(root, { file_path: 'page.ts' });
  assert.match(first, /next_line=401/);
  assert.match(first, /line400:/);
  const last = evidence.readSource(root, { file_path: 'page.ts', line_start: 401, line_end: 800 });
  assert.match(last, /401-600\/600; EOF/);
  assert.match(last, /line600:/);
  assert.doesNotMatch(last, /line1:/);
  assert.match(evidence.readSource(root, { file_path: 'page.ts', line_start: 801 }), /EOF; total_lines=600/);
  assert.match(evidence.readSource(root, { file_path: '../.env' }), /ERROR/);
  fs.writeFileSync(path.join(root, 'requirements.md'), 'Proposed maximum: 200 characters.');
  assert.match(evidence.readSource(root, { file_path: 'requirements.md' }), /Proposed maximum: 200/);
});
test('RCA receives actual test names and complete error and trace, never the shortened grouping key', () => {
  const message = 'x'.repeat(500) + ' Expected: 0 Received: 1 [data-testid="todo-item"]';
  const trace = 'y'.repeat(500) + ' src/pages/TodoPage.ts:90';
  const vars = evidence.rcaVariables(message.slice(0, 80), [{ name: 'Todo', message, trace, status: 'failed' }]);
  assert.equal(vars.test_name, 'Todo');
  assert.equal(vars.error_message, message);
  assert.equal(vars.stack_trace, trace);
  assert.ok(vars.fail_list.includes(trace));
});

test('bug context lists real filenames and preloads files cited in a Windows stack trace', t => {
  const root = temp(t);
  fs.mkdirSync(path.join(root, 'src/pages'), { recursive: true });
  fs.writeFileSync(path.join(root, 'src/pages/TodoPage.ts'), 'const evidenceAfter3000 = true;');
  const context = evidence.sourceContext(root, { trace: 'at C:\\repo\\src\\pages\\TodoPage.ts:80:40' });
  assert.match(context, /src\/pages\/TodoPage.ts/);
  assert.match(context, /const evidenceAfter3000 = true/);
});

test('source bundle includes API client and timeouts without importing current .env as old run evidence', t => {
  const root = temp(t);
  fs.mkdirSync(path.join(root, 'src/api'), { recursive: true });
  fs.writeFileSync(path.join(root, 'src/api/QACartApiClient.ts'), 'const timeout = 30000; const retries = 0;');
  fs.writeFileSync(path.join(root, '.env'), 'BASE_URL=https://SECRET.invalid\nPASSWORD=SECRET');
  const bundle = evidence.sourceBundle(root, { trace: 'api.register ECONNRESET' });
  assert.ok(bundle.reads.some(([file, content]) => file.endsWith('QACartApiClient.ts') && content.includes('30000')));
  assert.equal(bundle.recorded_api.status, 'NOT_RECORDED');
  assert.doesNotMatch(JSON.stringify(bundle), /SECRET/);
});

test('API evidence is scoped to test UUID/run and rejects external attachment paths', t => {
  const root = temp(t), directory = path.join(root, 'results');
  fs.mkdirSync(directory);
  const write = (file, data) => fs.writeFileSync(path.join(directory, file), JSON.stringify(data));
  write('run-manifest.json', { runId: 'one' });
  const event = { schemaVersion: 1, kind: 'qa-api-diagnostic', target: 'https://user:SECRET@example.test/?token=SECRET',
    method: 'POST', path: '/api/v1/users/register', status: null, errorCode: 'ECONNRESET', timeoutMs: 30000, durationMs: 100, mode: 'real-http' };
  write('api.json', event);
  write('one-result.json', { uuid: 'test-one', attachments: [{ type: 'application/json', source: 'api.json' },
    { type: 'application/json', source: '../secret.json' }] });
  write('two-result.json', { uuid: 'test-two', attachments: [{ type: 'application/json', source: 'api.json' }] });
  const result = evidence.recordedApi(root, { uuid: 'test-one' }, { directory, runId: 'one' });
  assert.equal(result.events.length, 1); assert.equal(result.events[0].target, 'https://example.test');
  assert.doesNotMatch(JSON.stringify(result), /SECRET/);
  assert.equal(evidence.recordedApi(root, { uuid: 'absent' }, { directory, runId: 'one' }).status, 'NOT_RECORDED');
  assert.equal(evidence.recordedApi(root, { uuid: 'test-one' }, { directory, runId: 'other' }).status, 'NOT_RECORDED');
});

for (const unavailable of [false, true, 'rate-limited']) test(`bug analysis persists ${unavailable || 'final'} conclusion without editing source`, async t => {
  const root = temp(t), dir = path.join(root, 'results');
  fs.mkdirSync(dir);
  fs.writeFileSync(path.join(root, 'page.ts'), 'UNCHANGED');
  fs.writeFileSync(path.join(dir, 'test-result.json'), JSON.stringify({ name: 'failed test', status: 'failed', statusDetails: { message: 'error'.repeat(200), trace: 'trace'.repeat(200) } }));
  if (unavailable === 'rate-limited') for (let i = 0; i < 10; i++) fs.writeFileSync(path.join(dir, `${i}-result.json`), JSON.stringify({ name: `failure-${i}`, status: 'broken' }));
  const fakeProcess = { argv: ['node', 'bug-agent.js', 'analyze', '--max-iter=2'], env: {}, exitCode: 0 };
  let calls = 0;
  const dependencies = {
    './shared/agent-verifier': require('../shared/agent-verifier'),
    dotenv: { config() {} },
    './shared/pipeline-runtime': { resultDirectory: () => dir },
    './shared/analysis-evidence': evidence,
    './shared/llm-analysis': require('../shared/llm-analysis'),
    './shared/provider-errors': require('../shared/provider-errors'),
    './shared/tracer': { Span: class { begin() { return this; } end() {} } },
    './shared/memory-store': { getContextFor() { return ''; }, recordEpisode() {} },
    './shared/prompt-store': {},
    './llm': { parseArgs: JSON.parse,
      chat: async (messages, options) => {
        assert.equal(options.tools, undefined);
        calls++;
        if (unavailable === 'rate-limited') throw Object.assign(new Error('HTTP 429'), { status: 429 });
        if (unavailable) return { message: { content: 'Service LLM temporairement indisponible.' } };
        if (calls === 1) return { message: { content: '{"action":"read_file","file_path":"page.ts"}' } };
        assert.ok(messages[0].content.includes('EOF'));
        return { message: { content: JSON.stringify({ action: 'report_analysis', root_cause: 'Observed mismatch; requirement needs review', fix_summary: 'Reproduce against the requirement', confidence: 0.6 }) } };
      },
    },
  };
  const module = { exports: {} };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../bug-agent.js'), 'utf8'), {
    __dirname: path.join(root, 'scripts/agents'), module, process: fakeProcess, console: { log() {}, error() {} },
    require: name => Object.hasOwn(dependencies, name) ? dependencies[name] : require(name),
  });
  assert.equal(module.exports.loadFailures().find(f => f.name === 'failed test').message.length, 1000);
  await module.exports.cmdAnalyze();
  const report = JSON.parse(fs.readFileSync(path.join(dir, 'bug-analysis.json')));
  assert.equal(report.analyses[0].status, unavailable ? 'NOT_EVALUATED' : 'HYPOTHESIS');
  if (unavailable === 'rate-limited') { assert.equal(calls, 1); assert.equal(report.analyses.length, 11); }
  if (!unavailable) assert.equal(report.analyses[0].verification.status, 'UNVERIFIED');
  assert.equal(fakeProcess.exitCode, unavailable ? 1 : 0);
  assert.equal(fs.readFileSync(path.join(root, 'page.ts'), 'utf8'), 'UNCHANGED');
});
