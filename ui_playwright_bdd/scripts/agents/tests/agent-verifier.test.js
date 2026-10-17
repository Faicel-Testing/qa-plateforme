'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const vm = require('node:vm');
const verifier = require('../shared/agent-verifier');
function temporary(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-verifier-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 }));
  return root;
}
const cases = [
  ['codegen', 'typescript', 'export class Example {}'],
  ['planning', 'suggest', 'Scenario: Example\n Given a user\n Then access is denied'],
  ['quality', 'triage', { result: 'real_bug', confidence: 1, reasoning: 'Timeout observed' }],
  ['bug', 'analyze', { root_cause: 'Timeout', fix_summary: 'Inspect selector', confidence: 1, fix_applied: false }],
  ['advisor', 'advise', { verdict: 'GO', risk: 'low', blockers: [], warnings: [], reasoning: 'Tests passed' }, { run: { allowed: true } }],
  ['reporting', 'notify', 'All tests passed.'],
  ['ci', 'pr', { title: 'Fix login', body: 'All tests passed.' }],
  ['runner', 'flaky', 'A selector must be wrong.'],
];
for (const [agent, operation, output, context] of cases) {
  test(`${agent}: plausible model output never becomes a proof`, () => {
    const result = verifier.verify({ agent, operation, output, context });
    assert.equal(result.status, 'UNVERIFIED');
    assert.ok(result.limitations.length);
  });
  test(`${agent}: empty output is rejected`, () => {
    assert.equal(verifier.verify({ agent, operation, output: '' }).status, 'REJECTED');
  });
}
test('wrong code, classifications, probabilities and contradictory release decisions are rejected', () => {
  const inputs = [
    { agent: 'codegen', operation: 'typescript', output: 'export class {' },
    { agent: 'codegen', operation: 'gherkin', output: 'Feature: Empty' },
    { agent: 'quality', operation: 'triage', output: { result: 'real_bug', confidence: 1.1, reasoning: 'x' } },
    { agent: 'quality', operation: 'rca', output: { root_cause: 'x', cause_category: 'invented' } },
    { agent: 'bug', operation: 'analyze', output: { root_cause: 'x', fix_summary: 'x', confidence: 0.9, fix_applied: true } },
    { agent: 'advisor', operation: 'predict', output: { tc: 'wrong', failure_risk: 2 }, context: { tc: 'expected' } },
    { agent: 'advisor', operation: 'advise', output: cases[4][2], context: { run: { allowed: false } } },
    { agent: 'ci', operation: 'commit', output: 'test: valid\nsecond line' },
  ];
  for (const input of inputs) assert.equal(verifier.verify(input).status, 'REJECTED', input.agent + '/' + input.operation);
});
test('successful string replacement alone never validates a repair', () => {
  assert.equal(verifier.verify({ agent: 'bug', operation: 'repair', output: { applied: true, error: false } }).status, 'UNVERIFIED');
});
test('only an exact deterministic summary is validated, within its count-only scope', () => {
  const context = { passed: 2, total: 3 };
  const output = verifier.factualSummary(context);
  assert.equal(verifier.verify({ agent: 'reporting', operation: 'factual-summary', output, context }).status, 'VALIDATED');
  assert.equal(verifier.verify({ agent: 'reporting', operation: 'factual-summary', output: 'All tests passed', context }).status, 'REJECTED');
  assert.equal(verifier.verify({ agent: 'runner', operation: 'factual-summary', output: verifier.factualSummary({ passed: 0, total: 0 }), context: { passed: 0, total: 0 } }).status, 'REJECTED');
});
test('audit isolates invocations, binds output/context fingerprints and never stores model content', t => {
  const root = temporary(t);
  const proc = { argv: [], env: { QA_RUN_ID: 'run-1' }, exitCode: 0 };
  const factory = () => verifier.createVerifier({ root, agent: 'ci', runtimeProcess: proc, logger: { log() {} } });
  const first = factory();
  const result = first.check('release', 'private content', { secret: 'do-not-log' });
  assert.throws(() => first.requireValidated(result), /action bloquée/);
  assert.equal(proc.exitCode, 1);
  factory().check('release', 'another draft');
  const files = fs.readdirSync(path.join(root, 'logs/agent-verification'));
  assert.equal(files.length, 2);
  for (const file of files) {
    const raw = fs.readFileSync(path.join(root, 'logs/agent-verification', file), 'utf8');
    assert.doesNotMatch(raw, /private content|do-not-log/);
    const record = JSON.parse(raw);
    assert.equal(record.runId, 'run-1');
    assert.equal(record.outputHash.length, 64);
  }
});
test('dry-run writes nothing, rejection propagates and corrupt audit fails closed', t => {
  const root = temporary(t);
  const proc = { argv: ['--dry-run'], env: {}, exitCode: 0 };
  const check = verifier.createVerifier({ root, agent: 'runner', runtimeProcess: proc, logger: { log() {} } });
  assert.throws(() => check.check('summary', ''), /rejected/);
  assert.equal(proc.exitCode, 1);
  assert.deepEqual(fs.readdirSync(root), []);
  const file = path.join(root, 'audit.jsonl');
  fs.writeFileSync(file, '{');
  assert.equal(verifier.readVerification(file).status, 'REJECTED');
});
test('pipeline blocks an advisor after unverified AI output even when its process returned zero', async t => {
  const root = temporary(t);
  const realRuntime = require('../shared/pipeline-runtime');
  const calls = [];
  const proc = { argv: ['node', 'pipeline-agent.js'], env: {}, execPath: process.execPath, exitCode: 0 };
  const module = { exports: {} };
  const deps = {
    dotenv: { config() {} },
    './shared/agent-verifier': verifier,
    './shared/pipeline-runtime': { ...realRuntime, execute: async (_cmd, args, options) => {
      const agent = path.basename(args[0]); calls.push(agent);
      if (agent === 'runner-agent.js') {
        const dir = options.env.ALLURE_RESULTS_DIR;
        fs.mkdirSync(dir, { recursive: true });
        fs.writeFileSync(path.join(dir, 'one-result.json'), JSON.stringify({ status: 'passed', start: 20, stop: 30 }));
        fs.writeFileSync(path.join(dir, 'run-manifest.json'), JSON.stringify({ runId: options.env.QA_RUN_ID, completed: true, startedAt: 10, finishedAt: 40, exitCode: 0, resultCount: 1 }));
      }
      if (agent === 'quality-agent.js') {
        fs.writeFileSync(options.env.QA_VERIFICATION_FILE, JSON.stringify({ schemaVersion: 1, status: 'UNVERIFIED' }) + '\n');
      }
      return { success: true, exitCode: 0 };
    } },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../pipeline-agent.js'), 'utf8'), {
    __dirname: path.join(root, 'scripts/agents'), module, process: proc, console: { log() {}, error() {} },
    require: name => deps[name] || require(name),
  });
  await module.exports.runPipeline('quick');
  assert.equal(calls.includes('advisor-agent.js'), false);
  assert.equal(proc.exitCode, 1);
  assert.equal(JSON.parse(fs.readFileSync(path.join(root, 'logs/pipeline-summary.json'))).validation, 'BLOCKED');
});

test('candidate compilation rejects type errors before touching project files', t => {
  const root = temporary(t);
  fs.writeFileSync(path.join(root, 'tsconfig.json'), JSON.stringify({ compilerOptions: { strict: true, skipLibCheck: true, types: [] }, include: ['*.ts'] }));
  const file = path.join(root, 'candidate.ts');
  fs.writeFileSync(file, 'export const original = true;');
  const check = output => verifier.verify({ agent: 'codegen', operation: 'typescript', root, output, context: { filePath: file } });
  const invalid = check('export const value: number = "wrong";');
  assert.equal(invalid.status, 'REJECTED');
  assert.ok(invalid.checks.find(c => c.name === 'typescript-project').detail.diagnostics.some(d => d.code === 2322));
  assert.equal(fs.readFileSync(file, 'utf8'), 'export const original = true;');
  const valid = check('export const value: number = 3;');
  assert.equal(valid.status, 'UNVERIFIED');
  assert.equal(valid.checks.find(c => c.name === 'typescript-project').status, 'PASS');
});

function loadAgent(agent, root, extra = {}, env = {}) {
  const proc = { argv: ['node', agent + '-agent.js'], env, exitCode: 0 };
  const module = { exports: {} };
  const output = [];
  const deps = {
    dotenv: { config() {} },
    './shared/agent-verifier': verifier,
    './shared/tracer': { Span: class { begin() { return this; } end() {} } },
    './shared/prompt-store': { get() {}, recordUsage() {} },
    './shared/memory-store': { recordEpisode() {} },
    './shared/pipeline-runtime': { resultDirectory: () => path.join(root, 'results') },
    ...extra,
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, `../${agent}-agent.js`), 'utf8'), {
    __dirname: path.join(root, 'scripts/agents'), module, process: proc, Buffer, URL,
    console: { log: (...args) => output.push(args.join(' ')), error: (...args) => output.push(args.join(' ')) },
    require: name => deps[name] || require(name),
  });
  return { api: module.exports, proc, output };
}

for (const [command, response] of [
  ['cmdPrCreate', JSON.stringify({ title: 'Fix login', body: 'All tests passed' })],
  ['cmdReleaseCreate', 'All problems resolved'],
  ['cmdGitCommit', 'fix: resolve all issues'],
]) test(`CI ${command}: no publication or commit from unverified prose`, async t => {
  const root = temporary(t), commands = [];
  const { api, proc } = loadAgent('ci', root, {
    child_process: { execSync: cmd => { commands.push(cmd); return cmd.includes('rev-parse') ? 'feature\n' : 'some diff\n'; } },
    './llm': { chat: async () => ({ message: { content: response } }) },
  });
  await api[command]('v1.0.0');
  assert.equal(proc.exitCode, 1);
  assert.ok(commands.every(cmd => !/gh (pr|release) create|git (push|add|commit|tag -a)/.test(cmd)));
  const files = fs.readdirSync(path.join(root, 'logs/agent-verification'));
  assert.equal(verifier.readVerification(path.join(root, 'logs/agent-verification', files[0])).status, 'UNVERIFIED');
});

test('notification replaces invented AI conclusions with exact deterministic counts', async t => {
  const root = temporary(t), dir = path.join(root, 'results');
  fs.mkdirSync(dir);
  fs.writeFileSync(path.join(dir, 'one-result.json'), JSON.stringify({ name: 'Login', status: 'failed' }));
  let sent;
  const { api, proc } = loadAgent('reporting', root, {
    './llm': { chat: async () => ({ message: { content: '100% passed, production is ready' } }) },
    https: { request: (_options, done) => ({ on() {}, write: payload => { sent = payload; }, end() { done({ statusCode: 200 }); } }) },
  }, { SLACK_WEBHOOK_URL: 'https://example.invalid/hook' });
  await api.cmdNotify('slack');
  assert.equal(proc.exitCode, 0);
  assert.match(sent, /Run : 0\/1 tests passés/);
  assert.doesNotMatch(sent, /production is ready|100% passed/);
});

test('repair stages a candidate without editing sources or claiming a successful repair', async t => {
  const root = temporary(t), dir = path.join(root, 'results');
  fs.mkdirSync(dir);
  fs.writeFileSync(path.join(dir, 'one-result.json'), JSON.stringify({ name: 'Login', status: 'failed', statusDetails: { message: 'error' } }));
  const source = path.join(root, 'src/pages/page.ts');
  fs.mkdirSync(path.dirname(source), { recursive: true });
  fs.writeFileSync(source, 'export const value = 1;');
  let calls = 0;
  const { api, proc, output } = loadAgent('bug', root, {
    './shared/change-proposals': require('../shared/change-proposals'),
    './llm': { parseArgs: JSON.parse, chat: async () => ({ message: { tool_calls: [calls++ === 0
      ? { id: '1', function: { name: 'apply_fix', arguments: JSON.stringify({ file_path: 'src/pages/page.ts', old_str: 'value = 1', new_str: 'value = 2' }) } }
      : { id: '2', function: { name: 'report_analysis', arguments: JSON.stringify({ root_cause: 'fixed', fix_applied: true }) } }] } }) },
  });
  await api.cmdRepair();
  assert.equal(fs.readFileSync(source, 'utf8'), 'export const value = 1;');
  const proposals = path.join(root, 'logs/change-proposals');
  const files = fs.readdirSync(proposals);
  assert.equal(files.length, 1);
  const candidate = JSON.parse(fs.readFileSync(path.join(proposals, files[0]), 'utf8'));
  assert.match(candidate.content, /value = 2/);
  assert.equal(candidate.status, 'pending');
  assert.equal(proc.exitCode, 1);
  assert.ok(!output.some(line => line.includes('Fix appliqué')));
});

test('provider failure in CI produces a rejected audit and a nonzero exit', async t => {
  const root = temporary(t);
  const { api, proc } = loadAgent('ci', root, {
    child_process: { execSync: () => 'feature\n' },
    './llm': { chat: async () => { throw new Error('Provider unavailable'); } },
  });
  await api.cmdPrCreate();
  assert.equal(proc.exitCode, 1);
  const files = fs.readdirSync(path.join(root, 'logs/agent-verification'));
  assert.equal(verifier.readVerification(path.join(root, 'logs/agent-verification', files[0])).status, 'REJECTED');
});

test('all eight integrated agents and the pipeline have valid JavaScript syntax', () => {
  for (const agent of ['codegen', 'planning', 'quality', 'bug', 'advisor', 'reporting', 'ci', 'runner', 'pipeline']) {
    const file = path.join(__dirname, `../${agent}-agent.js`);
    assert.doesNotThrow(() => new vm.Script(fs.readFileSync(file, 'utf8'), { filename: file }));
  }
});
