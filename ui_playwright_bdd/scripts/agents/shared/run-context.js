'use strict';
const path = require('node:path');
const { randomUUID } = require('node:crypto');

// Only an orchestrator may supply an execution identity. Shell/.env selections
// used to inspect old results must never become the identity of a new test run.
function newExecution(root, env = process.env) {
  const managed = env.QA_EXECUTION_MANAGED === 'true';
  if (managed && (!env.QA_RUN_ID || !env.ALLURE_RESULTS_DIR)) throw new Error('Managed execution requires run ID and results directory');
  const runId = managed ? env.QA_RUN_ID : `${Date.now()}-${randomUUID()}`;
  if (!/^[a-zA-Z0-9_.-]+$/.test(runId)) throw new Error('Invalid execution run ID');
  const resultsDir = managed ? path.resolve(env.ALLURE_RESULTS_DIR) : path.join(root, 'allure-runs', runId, 'results');
  return { runId, resultsDir, env: { ...env, QA_RUN_ID: runId, ALLURE_RESULTS_DIR: resultsDir, QA_EXECUTION_MANAGED: 'true' } };
}
module.exports = { newExecution };
