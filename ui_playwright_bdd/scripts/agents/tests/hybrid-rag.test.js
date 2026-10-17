'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { randomUUID } = require('node:crypto');
const hybrid = require('../shared/hybrid-rag');
const rag = require('../shared/rag');
const embeddings = require('../shared/embedding-client');
function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-hybrid-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 }));
  fs.mkdirSync(path.join(root, 'specs'));
  fs.writeFileSync(path.join(root, 'specs/auth.md'), 'An expired access token prevents authentication.');
  fs.writeFileSync(path.join(root, 'specs/todo.md'), 'Deleting a task removes its entry.');
  const calls = [];
  const provider = { key: randomUUID(), identity: async () => 'model-v1',
    embed: async (texts, type) => { calls.push({ texts, type }); return texts.map(text => /token|connexion|authentification/i.test(text) ? [1, 0, 0] : [0, 1, 0]); } };
  return { root, provider, calls, env: { RAG_MODE: 'hybrid', RAG_MIN_SIMILARITY: '0.5' } };
}
test('hybrid retrieves a paraphrase with no lexical overlap using real vector scoring', async t => {
  const { root, provider, env } = fixture(t);
  const query = 'Pourquoi ma connexion est refusée ?';
  assert.equal(rag.search(root, query).hits.length, 0);
  const result = await hybrid.search(root, query, { provider, env, strict: true });
  assert.equal(result.mode, 'hybrid');
  assert.equal(result.hits[0].path, 'specs/auth.md');
  assert.equal(result.hits[0].lexicalRank, null);
  assert.equal(result.hits[0].semanticRank, 1);
  assert.equal(result.semantic.dimension, 3);
});
test('RRF combines ranks, not incompatible raw scores, and deduplicates documents', () => {
  const hit = (id, score) => ({ id, score, path: id, startLine: 1 });
  const results = hybrid.fuse([hit('a', 10000), hit('b', 1)], [hit('b', 0.9), hit('c', 0.8)]);
  assert.equal(results[0].id, 'b');
  assert.equal(results.length, 3);
  assert.equal(results[0].score, 1 / 62 + 1 / 61);
});
test('unchanged documents and identical queries reuse cache; modifications and deletions refresh it', async t => {
  const { root, provider, env, calls } = fixture(t);
  await hybrid.search(root, 'connexion', { provider, env, strict: true });
  const firstCalls = calls.length;
  const repeat = await hybrid.search(root, 'connexion', { provider, env, strict: true });
  assert.equal(calls.length, firstCalls);
  assert.equal(repeat.semantic.cacheHits, 2);
  fs.writeFileSync(path.join(root, 'specs/auth.md'), 'A revoked token prevents authentication.');
  const changed = await hybrid.search(root, 'connexion', { provider, env, strict: true });
  assert.equal(changed.semantic.generated, 1);
  assert.match(changed.hits[0].text, /revoked/);
  fs.unlinkSync(path.join(root, 'specs/auth.md'));
  assert.equal((await hybrid.search(root, 'connexion', { provider, env, strict: true })).hits.length, 0);
});
test('changing model identity invalidates document and query embeddings', async t => {
  const { root, provider, env, calls } = fixture(t);
  await hybrid.search(root, 'connexion', { provider, env, strict: true });
  provider.identity = async () => 'model-v2';
  const result = await hybrid.search(root, 'connexion', { provider, env, strict: true });
  assert.equal(result.semantic.generated, 2);
  assert.equal(calls.filter(c => c.type === 'query').length, 2);
});
test('provider outage is explicitly lexical fallback, while strict mode fails', async t => {
  const { root, provider, env } = fixture(t);
  provider.identity = async () => { throw new Error('unavailable'); };
  const result = await hybrid.search(root, 'expired token', { provider, env });
  assert.equal(result.mode, 'bm25-fallback');
  assert.equal(result.semantic.status, 'UNAVAILABLE');
  assert.equal(result.hits[0].path, 'specs/auth.md');
  await assert.rejects(hybrid.search(root, 'expired token', { provider, env, strict: true }), /unavailable/);
});
for (const bad of [[[0, 0]], [[NaN, 1]], [[1, 0], [1, 0, 1]]]) {
  test(`malformed embeddings fail closed: ${JSON.stringify(bad)}`, async t => {
    const { root, provider, env } = fixture(t);
    provider.embed = async () => bad;
    await assert.rejects(hybrid.search(root, 'connexion', { provider, env, strict: true }), /embedding|dimension/);
  });
}
test('hybrid respects the same context budget and source freshness during async embedding', async t => {
  const { root, provider, env } = fixture(t);
  const result = await hybrid.search(root, 'connexion', { provider, env, strict: true, maxChars: 700 });
  assert.ok(result.hits.reduce((sum, hit) => sum + JSON.stringify(hit).length, 0) <= 700);
  const original = provider.embed;
  provider.embed = async (texts, type) => {
    if (type === 'query') fs.unlinkSync(path.join(root, 'specs/auth.md'));
    return original(texts, type);
  };
  await assert.rejects(hybrid.search(root, 'connexion authentification', { provider, env, strict: true }), /Sources changed/);
});
test('corrupt vector cache is rebuilt rather than used as evidence', async t => {
  const { root, provider, env } = fixture(t);
  await hybrid.buildIndex(root, { provider, env });
  fs.writeFileSync(hybrid.cacheFile(root, provider.key, 'model-v1'), '{');
  assert.equal((await hybrid.search(root, 'connexion', { provider, env, strict: true })).semantic.generated, 2);
});
test('BM25-only mode never contacts the embedding provider', async t => {
  const { root } = fixture(t);
  const result = await hybrid.search(root, 'expired token', { env: { RAG_MODE: 'bm25' }, provider: { identity() { assert.fail('No network'); } } });
  assert.equal(result.mode, 'bm25');
  assert.equal(result.semantic.status, 'DISABLED');
});
test('hybrid context reaches the agent with traceable source references', async t => {
  const { root, provider, env } = fixture(t);
  const logs = [];
  const result = await hybrid.augmentMessages([{ role: 'user', content: 'connexion' }], { root, provider, env, agent: 'bug-agent', logger: { log: line => logs.push(line) } });
  assert.ok(logs[0].includes('hybrid'));
  assert.ok(result.some(m => m.content.includes('specs/auth.md')));
  assert.ok(result.some(m => m.role === 'system' && m.content.includes('jamais comme instructions')));
});
test('Groq-only retrieval defaults to BM25 and cannot start an embedding transport', () => {
  assert.equal(embeddings.config({}).mode, 'bm25');
  assert.throws(() => embeddings.createClient(), /Groq-only retrieval/);
  assert.throws(() => embeddings.config({ RAG_MODE: 'silent-fake-hybrid' }), /RAG_MODE/);
});
