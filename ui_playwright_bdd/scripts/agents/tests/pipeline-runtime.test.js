'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const os = require('os');
const vm = require('vm');
const runtime = require('../shared/pipeline-runtime');
const agents = path.join(__dirname, '..');
function temporary(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-pipeline-'));
  t.after(async () => {
    assert.equal(path.dirname(path.resolve(root)), path.resolve(os.tmpdir()));
    await fs.promises.rm(root, { recursive: true, force: true, maxRetries: 10, retryDelay: 200 });
  });
  return root;
}
function fixture(dir, overrides = {}) {
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'test-result.json'), JSON.stringify({ status: 'passed', start: 20, stop: 30 }));
  fs.writeFileSync(path.join(dir, 'run-manifest.json'), JSON.stringify({ runId: 'current', completed: true, startedAt: 10, finishedAt: 40, exitCode: 0, resultCount: 1, ...overrides }));
}
function loadAgent(file, root, deps, argv = []) {
  const module = { exports: {} };
  const output = [];
  const fakeProcess = { argv: ['node', file, ...argv], env: {}, execPath: process.execPath, exitCode: 0 };
  vm.runInNewContext(fs.readFileSync(path.join(agents, file), 'utf8'), {
    __dirname: path.join(root, 'scripts', 'agents'), module, process: fakeProcess,
    console: { log: (...args) => output.push(args.join(' ')), error: (...args) => output.push(args.join(' ')) },
    require: name => name === 'dotenv' ? { config() {} } : name === './shared/agent-verifier' ? require('../shared/agent-verifier') : Object.hasOwn(deps, name) ? deps[name] : name.startsWith('./shared/') ? require(path.join(agents, name)) : require(name),
  }, { filename: file });
  return { api: module.exports, process: fakeProcess, output };
}

for (const outcome of ['pending', 'rejected', 'missing-record', 'wrong-run', 'timeout', 'invalid-ai']) {
  test(`approval reporting: ${outcome} remains distinct from successful tests`, async t => {
    const root = temporary(t);
    const { api, process: proc, output } = loadAgent('pipeline-agent.js', root, {
      './shared/pipeline-runtime': { ...runtime, execute: async (_command, args, options) => {
        const file = path.basename(args[0]);
        if (file === 'runner-agent.js') fixture(options.env.ALLURE_RESULTS_DIR, { runId: options.env.QA_RUN_ID });
        if (file !== 'advisor-agent.js') return { success: true, exitCode: 0 };
        if (outcome !== 'missing-record') fs.writeFileSync(options.env.QA_DECISION_FILE, JSON.stringify({
          schemaVersion: 1, runId: outcome === 'wrong-run' ? 'old-run' : options.env.QA_RUN_ID,
          status: outcome === 'rejected' ? 'REJECTED' : 'PENDING_APPROVAL', reason: 'Revue humaine requise.',
        }));
        if (outcome === 'invalid-ai') fs.writeFileSync(options.env.QA_VERIFICATION_FILE,
          JSON.stringify({ schemaVersion: 1, status: 'REJECTED' }) + '\n');
        return { success: false, exitCode: outcome === 'rejected' ? 1 : 2, timedOut: outcome === 'timeout' };
      } },
    });
    await api.runPipeline('quick');
    const report = JSON.parse(fs.readFileSync(path.join(root, 'logs/pipeline-summary.json')));
    assert.equal(report.ok, 4);
    assert.equal(report.testSummary.passed, 1);
    assert.equal(report.testSummary.total, 1);
    assert.equal(report.pendingApproval, outcome === 'pending' ? 1 : 0);
    assert.equal(report.rejected, outcome === 'rejected' ? 1 : 0);
    assert.equal(report.ko, ['pending', 'rejected'].includes(outcome) ? 0 : 1);
    assert.equal(report.validation, outcome === 'pending' ? 'PENDING_APPROVAL' : outcome === 'rejected' ? 'REJECTED' : 'BLOCKED');
    assert.equal(proc.exitCode, outcome === 'pending' ? 2 : 1);
    const html = fs.readFileSync(path.join(root, 'docs/pipeline-dashboard.html'), 'utf8');
    assert.match(html, /Tests BDD : 1\/1 réussis/);
    if (outcome === 'pending') {
      assert.match(html, /Statut global : <strong>EN ATTENTE D’APPROBATION<\/strong>/);
      assert.match(output.join('\n'), /STATUT GLOBAL : EN ATTENTE D’APPROBATION/);
      assert.match(output.join('\n'), /Motif : Revue humaine requise/);
      assert.doesNotMatch(output.join('\n'), /Échec \(/);
    }
  });
}

test('direct advisor records pending approval without invoking the model', async t => {
  const root = temporary(t);
  fixture(path.join(root, 'allure-results'));
  const { api, process: proc, output } = loadAgent('advisor-agent.js', root, {
    './shared/pipeline-runtime': runtime,
    './shared/qa-workflow-engine': { requireHumanApprovalBeforeFinalDecision: () => ({ ok: false,
      blocked: true, status: 'PENDING_APPROVAL', reason: 'Revue humaine requise.' }) },
    './llm': { chatStructured() { assert.fail('No model call before review'); } },
    './shared/tracer': {}, './shared/memory-store': {}, './shared/prompt-store': {}, './shared/ai-governance': {},
  });
  proc.env.QA_RUN_ID = 'current';
  proc.env.QA_DECISION_FILE = path.join(root, 'decision.json');
  await api.cmdGate();
  assert.equal(proc.exitCode, 2);
  const record = JSON.parse(fs.readFileSync(proc.env.QA_DECISION_FILE, 'utf8'));
  assert.equal(record.status, 'PENDING_APPROVAL');
  assert.equal(record.runId, 'current');
  assert.match(output.join('\n'), /EN ATTENTE D’APPROBATION/);
});

test('legacy pipeline uses the legacy advisor when Python runtime is selected', async t => {
  const root = temporary(t), calls = [];
  const { api } = loadAgent('pipeline-agent.js', root, {
    './shared/pipeline-runtime': { ...runtime, execute: async (_cmd, args) => {
      calls.push(args);
      return { success: true, exitCode: 0 };
    } },
  });
  await api.runAgent('advisor-agent.js', ['gate'], '', { QA_AGENT_RUNTIME: 'python' });
  assert.equal(path.basename(calls[0][0]), 'python-agents.cjs');
  assert.equal(calls[0][1], 'advisor-legacy');
  assert.equal(calls[0][2], 'gate');
});

test('gate requires fresh, complete, nonempty passing results with a matching manifest', t => {
  const root = temporary(t);
  fixture(root);
  assert.equal(runtime.checkRun(root, 'current').allowed, true);
  assert.equal(runtime.checkRun(root, 'other').allowed, false);
  for (const overrides of [{ completed: false }, { completed: 'true' }, { exitCode: 1 }, { resultCount: 2 }, { startedAt: 25 }, { finishedAt: 29 }, { finishedAt: undefined }]) {
    fixture(root, overrides);
    assert.equal(runtime.checkRun(root).allowed, false, JSON.stringify(overrides));
  }
  fixture(root);
  fs.writeFileSync(path.join(root, 'bad-result.json'), '{');
  assert.equal(runtime.checkRun(root).allowed, false);
});

test('process execution distinguishes failure, spawn error and timeout', async () => {
  const failed = await runtime.execute(process.execPath, ['-e', 'process.exit(3)'], { timeout: 10000 });
  assert.equal(failed.exitCode, 3);
  assert.equal(failed.success, false);
  const missing = await runtime.execute('qa-no-such-command', [], { timeout: 10000 });
  assert.equal(missing.success, false);
  assert.ok(missing.error);
  const hung = await runtime.execute(process.execPath, ['-e', 'setInterval(()=>{},1000)'], { timeout: 300 });
  assert.equal(hung.timedOut, true);
  assert.equal(hung.success, false);
});

for (const outcome of ['pass', 'failure', 'timeout', 'empty', 'allure-error']) {
  test(`quick pipeline: ${outcome}, current results only, Allure attempted, gate fails closed`, async t => {
    const root = temporary(t), calls = [];
    fixture(path.join(root, 'allure-results')); // Old passing data must never rescue this run.
    const { api, process: proc } = loadAgent('pipeline-agent.js', root, {
      './shared/pipeline-runtime': { ...runtime, execute: async (_command, args, options) => {
        const file = path.basename(args[0]); calls.push({ file, args, options });
        if (file === 'runner-agent.js') {
          assert.equal(args[1], 'smoke');
          if (outcome !== 'empty') fixture(options.env.ALLURE_RESULTS_DIR, {
            runId: options.env.QA_RUN_ID, completed: outcome !== 'timeout', exitCode: outcome === 'failure' ? 1 : 0,
          });
        }
        const failure = file === 'runner-agent.js' && ['failure', 'timeout'].includes(outcome) || file === 'allure-agent.js' && outcome === 'allure-error';
        return { success: !failure, exitCode: failure ? 1 : 0, timedOut: file === 'runner-agent.js' && outcome === 'timeout', durationMs: 1 };
      } },
    });
    await api.runPipeline('quick');
    const report = JSON.parse(fs.readFileSync(path.join(root, 'logs/pipeline-summary.json')));
    assert.ok(calls.some(c => c.file === 'allure-agent.js'));
    assert.equal(calls.some(c => c.file === 'advisor-agent.js'), outcome === 'pass');
    assert.equal(report.validation, outcome === 'pass' ? 'PASS' : 'BLOCKED');
    assert.equal(proc.exitCode, outcome === 'pass' ? 0 : 1);
    assert.ok(calls.every(c => c.options.env.ALLURE_RESULTS_DIR === report.resultsDir));
    assert.notEqual(report.resultsDir, path.join(root, 'allure-results'));
    assert.ok(calls[0].options.timeout > 300000);
  });
}

test('no-tests pipeline cannot approve old data; dry-run does not create run results', async t => {
  for (const flag of ['--no-tests', '--dry-run']) {
    const root = temporary(t);
    fixture(path.join(root, 'allure-results'));
    let advisor = false;
    const { api } = loadAgent('pipeline-agent.js', root, {
      './shared/pipeline-runtime': { ...runtime, execute: async (_cmd, args) => {
        if (args[0].endsWith('advisor-agent.js')) advisor = true;
        return { success: true, exitCode: 0 };
      } },
    }, [flag]);
    await api.runPipeline('quick');
    assert.equal(advisor, false);
    assert.equal(fs.existsSync(path.join(root, 'allure-runs')), false);
    if (flag !== '--dry-run') assert.equal(JSON.parse(fs.readFileSync(path.join(root, 'logs/pipeline-summary.json'))).validation, 'NOT_EVALUATED');
  }
});

for (const mode of ['gate', 'advise']) {
  for (const decision of ['positive', 'negative', 'unavailable', 'malformed', 'governance']) {
    test(`advisor ${mode} propagates ${decision}`, async t => {
      const root = temporary(t);
      fixture(path.join(root, 'allure-results'));
      const fail = () => { throw new Error('LLM unavailable'); };
      const { api, process: proc } = loadAgent('advisor-agent.js', root, {
        './shared/pipeline-runtime': runtime,
        './shared/qa-workflow-engine': { requireHumanApprovalBeforeFinalDecision: () => ({ ok: true, blocked: false }) },
        './llm': {
          MODEL: 'test',
          chatStructured: async () => decision === 'unavailable' ? fail() : { verdict: decision === 'malformed' ? 'WARNING' : decision === 'negative' ? 'FAIL' : 'PASS', score: 90, blockers: [], improvement: 'Review requirements' },
          chatSelfConsistent: async () => decision === 'unavailable' ? fail() : { responses: [], n_votes: 3, winner: decision === 'malformed' ? null : { verdict: decision === 'negative' ? 'NO-GO' : 'GO', blockers: [], risk: 'low', warnings: [], reasoning: 'All observed tests passed' } },
        },
        './shared/ai-governance': { checkDecisionGate: () => ({ blocked: decision === 'governance', blockers: [] }) },
        './shared/tracer': { Span: class { begin() { return this; } end() {} } },
        './shared/memory-store': { getAgentSummary: () => '', recordEpisode() {} },
        './shared/prompt-store': { get() {}, recordUsage() {} },
      });
      await api[mode === 'gate' ? 'cmdGate' : 'cmdAdvise']();
      assert.equal(proc.exitCode, 1, 'An unverified model opinion cannot authorize a release');
    });
  }
}

for (const mode of ['cmdGate', 'cmdAdvise']) {
  test(`direct ${mode} refuses missing human review before calling the LLM`, async t => {
    const root = temporary(t);
    fixture(path.join(root, 'allure-results'));
    const { api, process: proc } = loadAgent('advisor-agent.js', root, {
      './shared/pipeline-runtime': runtime,
      './shared/qa-workflow-engine': { requireHumanApprovalBeforeFinalDecision: () => ({ ok: false, blocked: true, reason: 'Review required' }) },
      './llm': { chatStructured() { assert.fail('LLM must not authorize a missing review'); } },
      './shared/ai-governance': {}, './shared/tracer': {}, './shared/memory-store': {}, './shared/prompt-store': {},
    });
    await api[mode]();
    assert.equal(proc.exitCode, 1);
  });
}

for (const outcome of ['passed', 'failed', 'timeout', 'no-finish', 'spawn-error']) {
  test(`runner ${outcome}: direct Cucumber execution, manifest and exit status without LLM`, async t => {
    const root = temporary(t);
    const { api, process: proc } = loadAgent('runner-agent.js', root, {
      './llm': { assertRunning() { throw new Error('Must not contact LLM'); } },
      './shared/tracer': {}, './shared/memory-store': {}, './shared/prompt-store': {},
      './shared/pipeline-runtime': { ...runtime, execute: async (command, args, options) => {
        assert.equal(command, process.execPath);
        assert.ok(args[0].endsWith(path.join('bin', 'cucumber.js')));
        assert.equal(args[args.indexOf('--tags') + 1], '@smoke');
        const dir = options.env.ALLURE_RESULTS_DIR;
        assert.equal(JSON.parse(args[args.indexOf('--format-options') + 1]).resultsDir, dir);
        const now = Date.now();
        fs.writeFileSync(path.join(dir, 'case-result.json'), JSON.stringify({ status: outcome === 'passed' ? 'passed' : 'broken', start: now, stop: now }));
        if (outcome !== 'no-finish') fs.writeFileSync(path.join(dir, 'cucumber-messages.ndjson'), '{"testRunFinished":{"success":true}}\n');
        return { success: outcome === 'passed' || outcome === 'no-finish', exitCode: outcome === 'passed' || outcome === 'no-finish' ? 0 : 1,
          timedOut: outcome === 'timeout', error: outcome === 'spawn-error' ? 'ENOENT' : null };
      } },
    }, ['smoke']);
    await api.main();
    const dir = runtime.resultDirectory(root);
    const manifest = JSON.parse(fs.readFileSync(path.join(dir, 'run-manifest.json')));
    assert.equal(manifest.completed, ['passed', 'failed'].includes(outcome));
    assert.equal(proc.exitCode, outcome === 'passed' ? 0 : 1);
    assert.equal(runtime.checkRun(dir).allowed, outcome === 'passed');
  });
}

test('real Cucumber produces isolated Allure files and a completion message even for a failed scenario', async t => {
  const root = temporary(t);
  const project = path.join(agents, '..', '..');
  const feature = path.join(root, 'sample.feature');
  const steps = path.join(root, 'steps.cjs');
  const config = path.join(root, 'cucumber.cjs');
  const output = path.join(root, 'isolated-results');
  const messages = path.join(root, 'messages.ndjson');
  fs.writeFileSync(feature, 'Feature: Local fixture\n  Scenario: Failure reporting\n    Given a deliberate local failure\n');
  fs.writeFileSync(steps, `const { Given, After } = require(${JSON.stringify(require.resolve('@cucumber/cucumber'))}); Given('a deliberate local failure', function() { throw new Error('LOCAL_FIXTURE_FAILURE'); }); After(function() { this.attach('RECOVERY_ATTACHMENT', 'text/plain'); });`);
  fs.writeFileSync(config, `module.exports = { default: { paths: [${JSON.stringify(feature)}], require: [${JSON.stringify(steps)}] } };`);
  const result = await runtime.execute(process.execPath, [
    path.join(project, 'node_modules/@cucumber/cucumber/bin/cucumber.js'),
    '--config', path.relative(project, config), '--format', 'progress',
    '--format', `"allure-cucumberjs/reporter":"${path.join(root, 'allure-formatter.log')}"`, '--format', `"message":"${messages}"`,
    '--format-options', JSON.stringify({ resultsDir: output }),
  ], { cwd: project, timeout: 60000 });
  assert.equal(result.exitCode, 1, result.stderr);
  const data = runtime.readResults(output);
  assert.equal(data.results.length, 1, result.stderr);
  assert.match(data.results[0].statusDetails.message, /LOCAL_FIXTURE_FAILURE/);
  assert.ok(fs.readFileSync(messages, 'utf8').split('\n').filter(Boolean).some(line => JSON.parse(line).testRunFinished));
  const recoveredDir = path.join(root, 'recovered');
  fs.mkdirSync(recoveredDir);
  fs.copyFileSync(messages, path.join(recoveredDir, 'cucumber-messages.ndjson'));
  const { recoverAllure } = require('../shared/recover-allure');
  assert.equal(await recoverAllure(recoveredDir), 1);
  const recovered = runtime.readResults(recoveredDir).results[0];
  assert.equal(recovered.status, data.results[0].status);
  assert.match(recovered.statusDetails.message, /LOCAL_FIXTURE_FAILURE/);
  assert.ok(fs.readdirSync(recoveredDir).some(file => file.includes('-attachment') && fs.readFileSync(path.join(recoveredDir, file), 'utf8') === 'RECOVERY_ATTACHMENT'));
  assert.equal(await recoverAllure(recoveredDir), 0); // No duplicates on repeat.
  const generated = await runtime.execute(process.execPath, [path.join(agents, 'allure-agent.js'), 'generate'], {
    cwd: project, env: { ...process.env, ALLURE_RESULTS_DIR: output }, timeout: 180000,
  });
  assert.equal(generated.success, true, generated.stderr || generated.stdout);
  assert.ok(fs.existsSync(path.join(root, 'allure-report', 'index.html')));
});

test('full pipeline includes Allure and a real gate, skips external sync by default', async t => {
  const root = temporary(t), calls = [];
  const { api } = loadAgent('pipeline-agent.js', root, {
    './shared/pipeline-runtime': { ...runtime, execute: async (_cmd, args, options) => {
      calls.push([path.basename(args[0]), args[1]]);
      if (args[0].endsWith('runner-agent.js')) fixture(options.env.ALLURE_RESULTS_DIR, { runId: options.env.QA_RUN_ID });
      return { success: true, exitCode: 0 };
    } },
  });
  await api.runPipeline('full');
  assert.ok(calls.some(([f, arg]) => f === 'runner-agent.js' && arg === 'run'));
  assert.ok(calls.some(([f]) => f === 'allure-agent.js'));
  assert.ok(calls.some(([f, arg]) => f === 'advisor-agent.js' && arg === 'gate'));
  assert.equal(calls.some(([f, arg]) => f === 'reporting-agent.js' && arg === 'sync'), false);
});
