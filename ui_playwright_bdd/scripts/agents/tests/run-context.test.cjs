'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { newExecution } = require('../shared/run-context');
const { requestAnalysis } = require('../shared/llm-analysis');
const { rcaVariables } = require('../shared/analysis-evidence');

test('standalone executions ignore stale report selections and get distinct identities', () => {
  const old = { QA_RUN_ID: 'completed-run', ALLURE_RESULTS_DIR: path.resolve('allure-results') };
  const a = newExecution(process.cwd(), old), b = newExecution(process.cwd(), old);
  assert.notEqual(a.runId, old.QA_RUN_ID);
  assert.notEqual(a.runId, b.runId);
  assert.notEqual(a.resultsDir, b.resultsDir);
  assert.equal(a.env.QA_RUN_ID, a.runId);
  assert.equal(a.env.ALLURE_RESULTS_DIR, a.resultsDir);
  assert.equal(old.QA_RUN_ID, 'completed-run');
});
test('managed pipelines preserve explicit identity and reject incomplete configuration', () => {
  const env = { QA_EXECUTION_MANAGED: 'true', QA_RUN_ID: 'pipeline-one', ALLURE_RESULTS_DIR: path.resolve('results') };
  assert.equal(newExecution(process.cwd(), env).runId, env.QA_RUN_ID);
  assert.throws(() => newExecution(process.cwd(), { QA_EXECUTION_MANAGED: 'true' }), /requires/);
});
test('analysis does not retry provider rate limits or open circuits', async () => {
  for (const error of [Object.assign(new Error('HTTP 429'), { status: 429 }), new Error('Groq : circuit ouvert')]) {
    let calls = 0;
    await assert.rejects(requestAnalysis({ chat: async () => { calls++; throw error; } }, () => 'evidence'));
    assert.equal(calls, 1);
  }
});
test('RCA retains unique evidence and affected names without repeating identical traces', () => {
  const group = Array.from({ length: 30 }, (_, i) => ({ name: `case-${i}`, status: 'broken', message: 'Already completed', trace: 'SAME_TRACE'.repeat(1000) }));
  const compact = rcaVariables('group', group, { compact: true });
  assert.equal(compact.stack_trace, group[0].trace);
  assert.equal(compact.error_message, 'Already completed');
  assert.match(compact.test_name, /case-29/);
  assert.equal(compact.count, 30);
});
