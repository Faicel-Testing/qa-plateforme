'use strict';
const path = require('node:path');
require('dotenv').config({ path: path.resolve(__dirname, '../.env'), quiet: true });
require('ts-node/register');
const { PostgresDataRepository } = require('../src/data/PostgresDataRepository');
(async () => {
  const [action, ...args] = process.argv.slice(2);
  if (!['init', 'seed', 'prepare', 'status', 'complete'].includes(action)) throw new Error('Use init|seed|prepare|status|complete');
  const runId = args.length === 2 && args[0] === '--run-id' ? args[1] : undefined;
  if (['prepare', 'complete'].includes(action) && !runId) throw new Error('Explicit --run-id required');
  if (!['prepare', 'complete'].includes(action) && args.length) throw new Error('Unexpected arguments');
  const repo = new PostgresDataRepository();
  try {
    if (action === 'init') { await repo.migrate(); await repo.seed(); }
    else if (action === 'seed') await repo.seed();
    else if (action === 'prepare') await repo.prepare(runId);
    else if (action === 'complete') await repo.complete(runId);
    console.log(JSON.stringify({ action, ...(runId ? { runId } : {}), ...await repo.status() }));
  } finally { await repo.close(); }
})().catch(error => {
  // Database error messages can contain connection secrets or submitted data.
  const missing = /^Missing TEST_DATA_PG[A-Z]+;/.test(error.message || '');
  console.error(missing ? error.message : 'Data agent failed: check dedicated database configuration, permissions and migrations.');
  process.exitCode = 1;
});
