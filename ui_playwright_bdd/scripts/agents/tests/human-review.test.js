'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const vm = require('vm');
const context = require('../shared/review-context');
const proposals = require('../shared/change-proposals');
const { analyze } = require('../../ci-ai');
function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-human-review-'));
  t.after(async () => {
    assert.equal(path.dirname(path.resolve(root)), path.resolve(os.tmpdir()));
    await fs.promises.rm(root, { recursive: true, force: true, maxRetries: 10, retryDelay: 200 });
  });
  fs.mkdirSync(path.join(root, 'src/pages'), { recursive: true });
  fs.writeFileSync(path.join(root, 'src/pages/Page.ts'), 'export class Page {}');
  const results = path.join(root, 'allure-results');
  fs.mkdirSync(results);
  fs.writeFileSync(path.join(results, 'one-result.json'), JSON.stringify({ status: 'passed', start: 20, stop: 30 }));
  const manifest = { runId: 'run1', commit: 'abc', sourceHash: context.sourceHash(root), startedAt: 10, finishedAt: 40, completed: true, exitCode: 0, resultCount: 1 };
  fs.writeFileSync(path.join(results, 'run-manifest.json'), JSON.stringify(manifest));
  const env = { QA_RUN_ID: 'run1', ALLURE_RESULTS_DIR: results, GITHUB_SHA: 'abc' };
  const module = { exports: {} };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../shared/qa-workflow-engine.js'), 'utf8'), {
    __dirname: path.join(root, 'scripts/agents/shared'), module, process: { env },
    require: name => name.startsWith('./') ? require(path.join(__dirname, '../shared', name)) : require(name),
  });
  const api = module.exports;
  return { root, results, manifest, env, api };
}
function approveAll(api) {
  api.createWorkflow('QA-1');
  for (const stage of api.VALID_STAGES) api.approveStage('QA-1', stage, 'reviewer@example');
}
test('missing prerequisites, omitted reviewer and completed final decision are blocked', t => {
  const { api } = fixture(t);
  api.createWorkflow('QA-1');
  assert.throws(() => api.approveStage('QA-1', 'decision', 'reviewer'), /prerequisite/);
  assert.throws(() => api.approveStage('QA-1', 'gherkin'), /reviewer/);
  assert.throws(() => api.updateStage('QA-1', 'decision', 'completed', 'reviewer'), /human approval/);
  assert.throws(() => api.createWorkflow('QA-1'), /exists/);
  assert.equal(api.requireHumanApprovalBeforeFinalDecision('QA-1').blocked, true);
  assert.equal(api.requireHumanApprovalBeforeFinalDecision('QA-1').status, 'PENDING_APPROVAL');
});
test('rejecting an earlier stage invalidates final approval', t => {
  const { api } = fixture(t);
  approveAll(api);
  assert.equal(api.requireHumanApprovalBeforeFinalDecision('QA-1').ok, true);
  const result = api.rejectStage('QA-1', 'script', 'reviewer', 'Incorrect assertion');
  assert.equal(result.status, 'rejected');
  assert.equal(result.stages.decision.status, 'pending');
  assert.equal(api.requireHumanApprovalBeforeFinalDecision('QA-1').blocked, true);
  assert.equal(api.requireHumanApprovalBeforeFinalDecision('QA-1').status, 'REJECTED');
});
for (const changed of ['source', 'result', 'manifest', 'corrupt-registry']) {
  test(`final gate rejects changed ${changed}`, t => {
    const { api, root, results } = fixture(t);
    approveAll(api);
    const file = changed === 'source' ? path.join(root, 'src/pages/Page.ts') : changed === 'result' ? path.join(results, 'one-result.json')
      : changed === 'manifest' ? path.join(results, 'run-manifest.json') : api.WORKFLOW_FILE;
    fs.writeFileSync(file, '{}');
    assert.equal(api.requireHumanApprovalBeforeFinalDecision('QA-1').blocked, true);
  });
}
test('proposals do not edit sources and require the exact reviewed digest', t => {
  const { root } = fixture(t), file = 'src/pages/Page.ts';
  const p = proposals.propose(root, file, 'export class Page { ready = true; }', 'test');
  assert.equal(fs.readFileSync(path.join(root, file), 'utf8'), 'export class Page {}');
  assert.throws(() => proposals.applyReviewed(root, p.id, '', p.digest), /reviewer/);
  assert.throws(() => proposals.applyReviewed(root, p.id, 'reviewer', 'wrong'), /digest/);
  proposals.applyReviewed(root, p.id, 'reviewer', p.digest);
  assert.match(fs.readFileSync(path.join(root, file), 'utf8'), /ready/);
  assert.throws(() => proposals.applyReviewed(root, p.id, 'reviewer', p.digest));
  assert.throws(() => proposals.propose(root, '../outside.ts', 'bad', 'test'), /outside/);
});
test('source changes invalidate a pending proposal', t => {
  const { root } = fixture(t);
  const p = proposals.propose(root, 'src/pages/Page.ts', 'export class Page { ready = true; }', 'test');
  fs.writeFileSync(path.join(root, 'src/pages/Page.ts'), 'export class Other {}');
  assert.throws(() => proposals.applyReviewed(root, p.id, 'reviewer', p.digest), /Source changed/);
});
test('usage counters do not invalidate review, but prompt changes do', t => {
  const { root } = fixture(t);
  fs.mkdirSync(path.join(root, 'prompts'));
  const file = path.join(root, 'prompts/example.json');
  fs.writeFileSync(file, JSON.stringify({ template: 'Review evidence', metrics: { calls: 1 } }));
  const initial = context.sourceHash(root);
  fs.writeFileSync(file, JSON.stringify({ template: 'Review evidence', metrics: { calls: 2 } }));
  assert.equal(context.sourceHash(root), initial);
  fs.writeFileSync(file, JSON.stringify({ template: 'Different instruction', metrics: { calls: 2 } }));
  assert.notEqual(context.sourceHash(root), initial);
});
test('Python agent changes invalidate review; generated bytecode does not', t => {
  const { root, api, results, manifest } = fixture(t);
  const directory = path.join(root, 'qa_agents');
  fs.mkdirSync(directory);
  const source = path.join(directory, 'prompts.py');
  fs.writeFileSync(source, 'VERSION = "1.0.0"');
  const initial = context.sourceHash(root);
  fs.writeFileSync(path.join(results, 'run-manifest.json'), JSON.stringify({ ...manifest, sourceHash: initial }));
  approveAll(api);
  fs.mkdirSync(path.join(directory, '__pycache__'));
  fs.writeFileSync(path.join(directory, '__pycache__/prompts.cpython-312.pyc'), 'bytecode');
  assert.equal(context.sourceHash(root), initial);
  assert.equal(api.requireHumanApprovalBeforeFinalDecision('QA-1').ok, true);
  fs.writeFileSync(source, 'VERSION = "2.0.0"');
  assert.notEqual(context.sourceHash(root), initial);
  assert.equal(api.requireHumanApprovalBeforeFinalDecision('QA-1').blocked, true);
});
test('direct repair produces a proposal and cannot claim it was applied', t => {
  const { root } = fixture(t), module = { exports: {} };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../bug-agent.js'), 'utf8'), {
    __dirname: path.join(root, 'scripts/agents'), module, console,
    process: { env: {}, argv: ['node', 'bug-agent.js', 'repair'] },
    require: name => name === 'dotenv' ? { config() {} } : ['./llm', './shared/tracer', './shared/memory-store', './shared/prompt-store'].includes(name) ? {}
      : name.startsWith('./') ? require(path.join(__dirname, '..', name)) : require(name),
  });
  const output = module.exports.executeTool('apply_fix', { file_path: 'src/pages/Page.ts', old_str: 'class Page', new_str: 'class NewPage' });
  assert.match(output, /REVIEW REQUIRED/);
  assert.equal(fs.readFileSync(path.join(root, 'src/pages/Page.ts'), 'utf8'), 'export class Page {}');
  assert.match(module.exports.executeTool('report_analysis', { fix_applied: true }), /"fix_applied":false/);
  assert.throws(() => module.exports.executeTool('apply_fix', { file_path: '../outside.ts', old_str: 'a', new_str: 'b' }), /outside/);
});
test('CI workflow separates tests and AI secrets and preserves analysis after failures', () => {
  const yaml = require('yaml');
  const workflow = yaml.parse(fs.readFileSync(path.join(__dirname, '../../../../.github/workflows/ci-playwright.yml'), 'utf8'));
  assert.equal(workflow.jobs['ai-analysis'].needs, 'test');
  assert.match(workflow.jobs['ai-analysis'].if, /always\(\)/);
  assert.match(workflow.jobs['ai-analysis'].if, /event_name != 'pull_request'/);
  assert.doesNotMatch(JSON.stringify(workflow.jobs.test), /secrets\.GROQ_API_KEY/);
  assert.equal(workflow.permissions.contents, 'read');
  const steps = workflow.jobs.test.steps;
  const lint = steps.findIndex(step => step.run === 'npm run lint');
  const typecheck = steps.findIndex(step => step.run === 'npm run typecheck');
  const tests = steps.findIndex(step => step.run === 'npm run test:review');
  assert.ok(lint >= 0 && typecheck > lint && tests > typecheck);
  for (const step of [steps[lint], steps[typecheck]]) {
    assert.equal(step['continue-on-error'], undefined);
    assert.equal(step.if, undefined, 'Quality checks must not be optional');
  }
  assert.match(workflow.jobs['ai-analysis'].if, /needs.test.outputs.quality_checks == 'success'/);
});
test('CI analyzes failed tests without authorizing a release; provider failure remains visible', async t => {
  const { root, results, manifest, env } = fixture(t);
  fs.writeFileSync(path.join(results, 'one-result.json'), JSON.stringify({ status: 'failed', start: 20, stop: 30 }));
  fs.writeFileSync(path.join(results, 'run-manifest.json'), JSON.stringify({ ...manifest, exitCode: 1 }));
  let calls = 0;
  const report = await analyze(root, { ...env, GROQ_API_KEY: 'fake-test-only' }, async () => { calls++; return { success: false, exitCode: 1 }; });
  assert.equal(calls, 2);
  assert.equal(report.testsPassed, false);
  assert.equal(report.releaseAuthorized, false);
  assert.equal(report.status, 'FAILED');
});
test('CI reports missing provider and rejects incomplete or wrong execution', async t => {
  const { root, results, manifest, env } = fixture(t);
  const forbidden = () => { throw new Error('Should not call provider'); };
  assert.equal((await analyze(root, env, forbidden)).status, 'UNAVAILABLE');
  assert.equal((await analyze(root, { ...env, QA_RUN_ID: 'other' }, forbidden)).status, 'BLOCKED');
  fs.writeFileSync(path.join(results, 'run-manifest.json'), JSON.stringify({ ...manifest, completed: false }));
  assert.equal((await analyze(root, env, forbidden)).status, 'BLOCKED');
});
