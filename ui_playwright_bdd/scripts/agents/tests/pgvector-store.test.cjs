'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { randomUUID } = require('node:crypto');
const { Pool } = require('pg');
require('dotenv').config({ quiet: true, path: path.resolve(__dirname, '../../../.env') });
const store = require('../shared/pgvector-store');
const hybrid = require('../shared/hybrid-rag');
const rag = require('../shared/rag');
const configured = Boolean(process.env.RAG_PGPASSWORD);
async function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-pgvector-'));
  const env = { ...process.env, RAG_VECTOR_STORE: 'pgvector', RAG_MODE: 'hybrid', RAG_CORPUS_ID: 'test-' + randomUUID(), RAG_RERANK_ENABLED: 'false', CONFLUENCE_RAG_ENABLED: 'false' };
  fs.mkdirSync(path.join(root, 'specs'));
  fs.writeFileSync(path.join(root, 'specs/auth.md'), 'An expired access token prevents authentication.');
  fs.writeFileSync(path.join(root, 'specs/todo.md'), 'Deleting a task removes its entry.');
  let calls = 0;
  const provider = { key: randomUUID(), identity: async () => 'test-model-384', embed: async texts => {
    calls++;
    return texts.map(text => Array.from({ length: 384 }, (_, i) => i === (/token|connexion|auth/i.test(text) ? 0 : 1) ? 1 : 0));
  } };
  t.after(async () => {
    const pool = new Pool(store.config(env));
    try { await pool.query('DELETE FROM qa_rag.chunks WHERE corpus_id=$1', [env.RAG_CORPUS_ID]); }
    finally { await pool.end(); fs.rmSync(root, { recursive: true, force: true }); }
  });
  return { root, env, provider, calls: () => calls };
}
test('pgvector configuration is explicit, dedicated and TLS-verified remotely', () => {
  assert.equal(store.storage({}), 'file');
  assert.throws(() => store.storage({ RAG_VECTOR_STORE: 'other' }), /RAG_VECTOR_STORE/);
  assert.throws(() => store.config({}), /Missing/);
  const env = { RAG_PGDATABASE: 'qa_rag', RAG_PGUSER: 'qa_rag', RAG_PGPASSWORD: 'synthetic', RAG_PGHOST: 'db.internal' };
  assert.equal(store.config(env).ssl.rejectUnauthorized, true);
  assert.throws(() => store.config({ ...env, RAG_PGDATABASE: 'postgres' }), /dedicated/);
});
test('real SQL cosine search finds a paraphrase and persistent cache survives a new provider instance', { skip: !configured }, async t => {
  const f = await fixture(t);
  assert.equal(rag.search(f.root, 'connexion').hits.length, 0);
  const first = await hybrid.search(f.root, 'connexion', { env: f.env, provider: f.provider, strict: true });
  assert.equal(first.semantic.storage, 'pgvector');
  assert.equal(first.hits[0].path, 'specs/auth.md');
  assert.equal(first.hits[0].semanticRank, 1);
  const repeat = await hybrid.buildIndex(f.root, { env: f.env, provider: { ...f.provider, embed: () => assert.fail('Stored document vectors must be reused') } });
  assert.equal(repeat.cacheHits, 2);
  assert.equal(repeat.generated, 0);
});
test('source edits and deletions replace the SQL snapshot; corpora remain isolated', { skip: !configured }, async t => {
  const a = await fixture(t), b = await fixture(t);
  await hybrid.buildIndex(a.root, { env: a.env, provider: a.provider });
  await hybrid.buildIndex(b.root, { env: b.env, provider: b.provider });
  fs.writeFileSync(path.join(a.root, 'specs/auth.md'), 'A revoked token prevents authentication.');
  fs.unlinkSync(path.join(a.root, 'specs/todo.md'));
  const changed = await hybrid.buildIndex(a.root, { env: a.env, provider: a.provider });
  assert.equal(changed.generated, 1);
  const sa = store.create(a.root, a.provider.key, await a.provider.identity(), a.env);
  const sb = store.create(b.root, b.provider.key, await b.provider.identity(), b.env);
  try {
    assert.equal(Object.keys((await sa.load()).vectors).length, 1);
    assert.equal(Object.keys((await sb.load()).vectors).length, 2);
  } finally { await sa.close(); await sb.close(); }
});
test('failed snapshot insert rolls back deletion; stale fingerprints are rejected', { skip: !configured }, async t => {
  const f = await fixture(t);
  await hybrid.buildIndex(f.root, { env: f.env, provider: f.provider });
  const s = store.create(f.root, f.provider.key, await f.provider.identity(), f.env);
  try {
    const saved = await s.load(), index = rag.currentIndex(f.root);
    const broken = { ...index, chunks: index.chunks.map(c => ({ ...c, startLine: undefined })) };
    await assert.rejects(s.save(broken, saved.vectors), /null/);
    assert.equal(Object.keys((await s.load()).vectors).length, 2);
    const vector = Array.from({ length: 384 }, (_, i) => i === 0 ? 1 : 0);
    await assert.rejects(s.search({ ...index, fingerprint: 'stale' }, vector, 0), /snapshot changed/);
  } finally { await s.close(); }
});
test('removing every document clears the stored corpus without touching other corpora', { skip: !configured }, async t => {
  const f = await fixture(t);
  await hybrid.buildIndex(f.root, { env: f.env, provider: f.provider });
  fs.unlinkSync(path.join(f.root, 'specs/auth.md'));
  fs.unlinkSync(path.join(f.root, 'specs/todo.md'));
  const empty = await hybrid.buildIndex(f.root, { env: f.env, provider: f.provider });
  assert.equal(empty.storage, 'pgvector');
  const s = store.create(f.root, f.provider.key, await f.provider.identity(), f.env);
  try { assert.equal(await s.load(), null); } finally { await s.close(); }
});
test('SQL outage reports explicit lexical fallback and fails in strict mode', { skip: !configured }, async t => {
  const f = await fixture(t), env = { ...f.env, RAG_PGPORT: '1' };
  const result = await hybrid.search(f.root, 'expired token', { provider: f.provider, env });
  assert.equal(result.mode, 'bm25-fallback');
  assert.equal(result.semantic.status, 'UNAVAILABLE');
  await assert.rejects(hybrid.search(f.root, 'expired token', { provider: f.provider, env, strict: true }));
});
