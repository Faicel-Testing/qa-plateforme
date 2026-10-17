'use strict';
require('dotenv').config({ quiet: true });
require('ts-node/register');
const test = require('node:test');
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { PostgresDataRepository } = require('../../../src/data/PostgresDataRepository');
const { TestDataService } = require('../../../src/data/TestDataService');
const { postgresConfig } = require('../../../src/config/data.config');
const { Pool } = require('pg');

test('dedicated DB: migrations, SQL generation, parallel isolation and run-scoped release', async () => {
  const a = new PostgresDataRepository(), b = new PostgresDataRepository();
  const run = 'data-check-' + randomUUID(), other = 'data-check-' + randomUUID();
  try {
    await a.migrate(); await a.seed(); await a.seed();
    await a.prepare(run); await b.prepare(other);
    const rows = await Promise.all(Array.from({ length: 16 }, (_, i) =>
      (i % 2 ? a : b).reserve(run, `scenario-${i}`)));
    assert.equal(new Set(rows.map(r => r.email)).size, 16);
    assert.equal(new Set(rows.map(r => r.id)).size, 16);
    const isolated = await b.reserve(other, "scenario'; DROP TABLE qa_test_data.data_sets; --");
    await a.release(isolated.id, run, 'wrong-run');
    const pool = new Pool(postgresConfig());
    try {
      const reservation = await pool.query('SELECT status FROM qa_test_data.data_allocations WHERE id=$1', [isolated.id]);
      assert.equal(reservation.rows[0].status, 'reserved');
      const profiles = await pool.query('SELECT count(DISTINCT dataset_id)::int AS count FROM qa_test_data.data_allocations WHERE run_id=$1', [run]);
      assert.equal(profiles.rows[0].count, 16);
      assert.equal(await a.negativeValue('invalid-email', 'email'), 'invalid-email');
      await assert.rejects(a.negativeValue("missing'; DROP TABLE x; --", 'email'));
    } finally { await pool.end(); }
    await a.complete(run);
    await assert.rejects(a.reserve(run, 'late-scenario'), /Prepare/);
    assert.equal((await a.status()).connected, true);
  } finally { await a.complete(run); await b.complete(other); await a.close(); await b.close(); }
});

test('scenario service supplies PostgreSQL profiles without storing application credentials', async () => {
  const saved = { provider: process.env.TEST_DATA_PROVIDER, run: process.env.QA_RUN_ID };
  process.env.TEST_DATA_PROVIDER = 'postgres';
  process.env.QA_RUN_ID = 'service-check-' + randomUUID();
  const service = new TestDataService('offline-scenario');
  try {
    const user = await service.createUser();
    assert.match(user.email, /^qa[a-f0-9]+@mail.com$/);
    assert.ok(user.password.length >= 8);
    assert.equal(await service.negativeValue('weak-password', 'password'), '123');
  } finally {
    await service.dispose('offline-verification');
    const repo = new PostgresDataRepository();
    try { await repo.complete(process.env.QA_RUN_ID); } finally { await repo.close(); }
    if (saved.provider === undefined) delete process.env.TEST_DATA_PROVIDER; else process.env.TEST_DATA_PROVIDER = saved.provider;
    if (saved.run === undefined) delete process.env.QA_RUN_ID; else process.env.QA_RUN_ID = saved.run;
  }
});
