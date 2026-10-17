'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { options, collect } = require('../../deepeval');
const { meteredFetch } = require('../shared/task-metrics');
const { aggregate } = require('../shared/metrics-report');
test('DeepEval options reject silent fallbacks, invalid limits and unknown metrics', () => {
  assert.equal(options([]).limit, 2);
  assert.equal(options([]).mode, 'bm25');
  for (const args of [['--limit', '0'], ['--threshold', 'NaN'], ['--mode', 'fake'], ['--metrics', 'accuracy'], ['--top-k', '200'], ['--unknown', 'x']])
    assert.throws(() => options(args));
});
test('collection passes exactly retrieved context to production LLM without injecting RAG twice', async () => {
  let messages;
  const hit = { path: 'specs/example.md', startLine: 1, endLine: 2, sourceHash: 'abc', text: 'A deleted task is absent.', kind: 'reference-unreviewed' };
  const result = await collect({ cases: [{ id: 'one', input: 'Delete?' }] }, options([]), {
    search: async (_root, _query, settings) => { assert.equal(settings.strict, true); return { status: 'FOUND', mode: 'bm25', hits: [hit] }; },
    llm: { chat: async (m, opts) => { messages = m; assert.equal(opts.rag, false); return { message: { content: 'The task disappears.' } }; } },
  });
  assert.equal(result.cases[0].status, 'READY');
  assert.deepEqual(result.cases[0].retrieval_context, [hit.text]);
  assert.ok(messages.some(m => m.content.includes(hit.text)));
  assert.equal(result.cases[0].sources[0].text, undefined);
});
test('retrieval failure produces an error sample and never a fake score or model call', async () => {
  let calls = 0;
  const result = await collect({ cases: [{ id: 'one', input: 'Delete?' }] }, options([]), {
    search: async () => ({ mode: 'bm25-fallback', hits: [] }), llm: { chat: async () => { calls++; } },
  });
  assert.equal(result.cases[0].status, 'ERROR');
  assert.equal(calls, 0);
});
test('judge calls have a separate evaluation cost category', async () => {
  const events = [];
  const fetcher = meteredFetch('groq', async () => Response.json({ usage: { prompt_tokens: 12, completion_tokens: 4 } }),
    { kind: 'evaluation', emit: event => events.push(event), catalog: { models: {} } });
  await fetcher('https://example.test/chat/completions', { body: '{"model":"judge"}' });
  const result = aggregate(events);
  assert.equal(result.byCategory.evaluation.calls, 1);
  assert.equal(result.byCategory.generation.calls, 0);
  assert.equal(result.byCategory.evaluation.inputTokens, 12);
});

test('unavailable embeddings explain BM25 alternative without leaking provider errors', async () => {
  for (const message of ['Embedding service unavailable or timed out', 'provider failed SECRET']) {
    let calls = 0;
    const result = await collect({ cases: [{ id: 'one', input: 'Delete?' }] }, options([]), {
      search: async () => { throw Error(message); },
      llm: { chat: async () => { calls++; } },
    });
    assert.equal(calls, 0);
    assert.equal(result.cases[0].status, 'ERROR');
    assert.equal(result.cases[0].diagnostic.code, message.startsWith('Embedding') ? 'EMBEDDING_UNAVAILABLE' : 'RETRIEVAL_FAILED');
    assert.equal(JSON.stringify(result).includes('SECRET'), false);
  }
});
