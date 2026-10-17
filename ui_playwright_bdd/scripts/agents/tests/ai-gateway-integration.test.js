'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
test('real Groq SDK paths for agent, streaming and judge traverse the gateway', async () => {
  const previous = { ...process.env }, originalFetch = globalThis.fetch;
  const cb = require('../shared/circuit-breaker'), execute = cb.execute;
  const calls = [];
  try {
    require('dotenv').config({ quiet: true });
    process.env.NODE_TLS_REJECT_UNAUTHORIZED = '1';
    process.env.GROQ_API_KEY = 'synthetic-integration-api-key';
    process.env.GROQ_MODEL = 'openai/gpt-oss-120b';
    process.env.DEEPEVAL_JUDGE_PROVIDER = 'groq';
    process.env.DEEPEVAL_JUDGE_MODEL = 'openai/gpt-oss-120b';
    process.env.RAG_ENABLED = 'false';
    globalThis.fetch = async (url, init) => {
      calls.push({ url, init });
      const body = JSON.parse(init.body);
      if (body.stream) return new Response('data: {"choices":[{"delta":{"content":"ok"},"finish_reason":null}]}\n\ndata: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n', { headers: { 'content-type': 'text/event-stream' } });
      return Response.json({ choices: [{ message: { content: '{"reason":"ok"}' }, finish_reason: 'stop' }] });
    };
    cb.execute = async (fn, messages) => {
      assert.doesNotMatch(JSON.stringify(messages), /private\.local|person@example\.com/);
      return { value: JSON.stringify(await fn()), fallback: false };
    };
    const llm = require('../llm');
    await llm.chat([{ role: 'user', content: 'Return ok person@example.com https://private.local/secret' }]);
    const stream = await llm.chatStream([{ role: 'user', content: 'Return ok person@example.com https://private.local/secret' }]);
    for await (const chunk of stream) assert.equal(typeof chunk.message.content, 'string');
    await require('../../deepeval-judge').generate({ prompt: 'Return ok' });
    const embeddings = require('../shared/embedding-client');
    assert.throws(() => embeddings.createClient(embeddings.config({})), /Groq-only/);
    assert.equal(calls.length, 3);
    assert.doesNotMatch(JSON.stringify(calls.map(c => c.init.body)), /private\.local|person@example\.com/);
    for (const call of calls) { assert.equal(call.init.redirect, 'error'); assert.ok(call.init.signal); }
    for (const call of calls.slice(0, 3)) assert.equal(JSON.parse(call.init.body).max_completion_tokens, 4096);
    await assert.rejects(llm.chat([{ role: 'user', content: 'synthetic-integration-api-key' }]), /SECRET_IN_PAYLOAD/);
    assert.equal(calls.length, 3);
    cb.execute = async () => { throw Object.assign(new Error('SDK wrapper'), { cause: { code: 'AI_GATEWAY_BLOCKED' } }); };
    await assert.rejects(llm.chat([{ role: 'user', content: 'Return ok' }]), /SDK wrapper/);
    assert.equal(calls.length, 3, 'security failure must not call a fallback provider');
  } finally {
    globalThis.fetch = originalFetch; cb.execute = execute;
    for (const key of Object.keys(process.env)) if (!(key in previous)) delete process.env[key];
    Object.assign(process.env, previous);
  }
});
