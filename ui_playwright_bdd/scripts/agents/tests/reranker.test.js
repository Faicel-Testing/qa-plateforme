'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const reranker = require('../shared/reranker');
const hybrid = require('../shared/hybrid-rag');
const enabled = { RAG_RERANK_ENABLED: 'true', RAG_RERANK_CANDIDATES: '2', RAG_MODE: 'bm25' };
const hits = [0, 1, 2].map(i => ({ id: 'id-' + i, text: 'evidence-' + i, sourceHash: 'hash-' + i, score: 3 - i }));
test('invalid reranking configuration is rejected', () => {
  for (const env of [{ RAG_RERANK_ENABLED: 'yes' }, { RAG_RERANK_STRICT: 'typo' }, { RAG_RERANK_CANDIDATES: '21' }]) assert.throws(() => reranker.config(env));
});
test('reranks a bounded candidate pool, preserves evidence and reports truncation', async () => {
  const result = await reranker.rerank('q'.repeat(4500), hits, { env: enabled, topK: 1,
    scorer: async (query, candidates) => {
      assert.equal(query.length, 4000); assert.equal(candidates.length, 2);
      return { scores: [{ id: 'id-0', relevance: 20 }, { id: 'id-1', relevance: 95 }] };
    } });
  assert.equal(result.ranked[0].id, 'id-1');
  assert.equal(result.ranked[0].text, hits[1].text);
  assert.equal(result.ranked[0].sourceHash, hits[1].sourceHash);
  assert.equal(result.ranked[0].score, hits[1].score);
  assert.equal(result.reranking.queryTruncated, true);
  assert.equal(result.reranking.status, 'READY');
});
test('rejects hallucinated IDs, duplicates, missing scores and invalid ranges', () => {
  for (const scores of [[], [{ id: 'other', relevance: 100 }, { id: 'id-1', relevance: 10 }],
    [{ id: 'id-0', relevance: 10 }, { id: 'id-0', relevance: 10 }],
    [{ id: 'id-0', relevance: 101 }, { id: 'id-1', relevance: 10 }],
    [{ id: 'id-0', relevance: 0.9 }, { id: 'id-1', relevance: 10 }]]) {
    assert.throws(() => reranker.applyScores(hits.slice(0, 2), { scores }));
  }
});
test('disabled and single-candidate requests never call a model', async () => {
  const scorer = async () => assert.fail('unexpected model call');
  assert.equal((await reranker.rerank('Q', hits, { env: {}, scorer })).reranking.status, 'DISABLED');
  assert.equal((await reranker.rerank('Q', hits.slice(0, 1), { env: enabled, scorer })).reranking.status, 'SKIPPED');
});
test('outage retains original order, strict mode and gateway rejection propagate', async () => {
  const scorer = async () => { throw Error('sensitive provider body'); };
  const result = await reranker.rerank('Q', hits, { env: enabled, scorer });
  assert.deepEqual(result.ranked, hits);
  assert.equal(result.reranking.status, 'UNAVAILABLE');
  assert.doesNotMatch(JSON.stringify(result), /sensitive/);
  await assert.rejects(reranker.rerank('Q', hits, { env: { ...enabled, RAG_RERANK_STRICT: 'true' }, scorer }));
  await assert.rejects(reranker.rerank('Q', hits, { env: enabled, scorer: async () => {
    throw Object.assign(Error('blocked'), { code: 'AI_GATEWAY_BLOCKED' });
  } }), /blocked/);
});
test('unverified history remains penalized and ties preserve retrieval order', () => {
  const result = reranker.applyScores([{ ...hits[0], kind: 'ai-history-unverified' }, hits[1]],
    { scores: [{ id: 'id-0', relevance: 100 }, { id: 'id-1', relevance: 80 }] });
  assert.equal(result[0].id, 'id-1');
  assert.equal(result[1].rerankAdjustedScore, 60);
});
test('RAG reranks before final top-k and detects sources changed during scoring', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'rerank-rag-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.mkdirSync(path.join(root, 'specs'));
  fs.writeFileSync(path.join(root, 'specs/a.md'), 'login failure login failure authentication');
  fs.writeFileSync(path.join(root, 'specs/b.md'), 'login failure: inspect the actual error before changing the test');
  const result = await hybrid.search(root, 'login failure', { env: enabled, topK: 1,
    rerankScorer: async (query, candidates) => {
      assert.equal(candidates.length, 2);
      return { scores: candidates.map(h => ({ id: h.id, relevance: h.path === 'specs/b.md' ? 100 : 10 })) };
    } });
  assert.equal(result.hits.length, 1);
  assert.equal(result.hits[0].path, 'specs/b.md');
  assert.equal(result.reranking.status, 'READY');
  assert.ok(JSON.stringify(result.hits[0]).length <= 4500);
  const semanticResult = await hybrid.search(root, 'login failure', { env: { ...enabled, RAG_MODE: 'hybrid' }, topK: 1,
    provider: { key: root, identity: async () => 'synthetic-v1', embed: async texts => texts.map(() => [1, 0]) },
    rerankScorer: async (q, candidates) => {
      assert.ok(candidates.every(h => h.semanticRank !== null && h.lexicalRank !== null));
      return { scores: candidates.map(h => ({ id: h.id, relevance: h.path === 'specs/b.md' ? 100 : 10 })) };
    } });
  assert.equal(semanticResult.mode, 'hybrid');
  assert.equal(semanticResult.hits[0].path, 'specs/b.md');
  assert.equal(semanticResult.reranking.status, 'READY');
  await assert.rejects(hybrid.search(root, 'login failure', { env: enabled, rerankScorer: async (q, candidates) => {
    fs.writeFileSync(path.join(root, 'specs/b.md'), 'changed');
    return { scores: candidates.map(h => ({ id: h.id, relevance: 50 })) };
  } }), /Sources changed/);
});
test('reranker uses actual Groq SDK, security gateway and separate metering', async () => {
  const previous = { ...process.env }, original = globalThis.fetch;
  let sent;
  try {
    process.env.GROQ_API_KEY = 'synthetic-reranker-key'; process.env.NODE_TLS_REJECT_UNAUTHORIZED = '1';
    globalThis.fetch = async (url, init) => {
      assert.equal(init.redirect, 'error'); sent = JSON.parse(init.body);
      return Response.json({ choices: [{ finish_reason: 'stop', message: { content: JSON.stringify({ scores: [{ id: 'id-0', relevance: 50 }] }) } }], usage: { prompt_tokens: 5, completion_tokens: 3 } });
    };
    const result = await reranker.score('Q', hits.slice(0, 1), { model: 'openai/gpt-oss-20b' });
    assert.equal(result.scores[0].id, 'id-0');
    assert.equal(sent.response_format.type, 'json_schema');
    assert.equal(JSON.parse(sent.messages[1].content).excerpts[0].text, hits[0].text);
    const events = [];
    await require('../shared/task-metrics').meteredFetch('groq', async () => Response.json({ usage: { prompt_tokens: 5, completion_tokens: 3 } }),
      { kind: 'reranking', emit: e => events.push(e) })('https://api.groq.com/openai/v1/chat/completions', { body: '{"model":"openai/gpt-oss-20b"}' });
    assert.equal(require('../shared/metrics-report').aggregate(events).byCategory.reranking.calls, 1);
  } finally {
    globalThis.fetch = original;
    for (const key of Object.keys(process.env)) if (!(key in previous)) delete process.env[key];
    Object.assign(process.env, previous);
  }
});
