'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function load(env, behavior) {
  let calls = 0;
  const module = { exports: {} };
  const deps = {
    dotenv: { config() {} },
    './shared/ai-gateway': { preflight: value => value, isGatewayError: () => false },
    './shared/circuit-breaker': { execute: behavior },
    './shared/task-metrics': { meteredFetch() {} },
    'groq-sdk': class { constructor() { calls++; } },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../llm.js'), 'utf8'), {
    module, __dirname: path.resolve(__dirname, '..'), console,
    process: { env: { RAG_ENABLED: 'false', ...env }, argv: [] },
    require: name => { assert.ok(name in deps, `Unexpected dependency: ${name}`); return deps[name]; },
  });
  return { llm: module.exports, calls: () => calls };
}

test('missing Groq key fails explicitly instead of selecting another provider', async () => {
  const { llm, calls } = load({}, () => assert.fail('No provider call'));
  assert.equal(llm.PROVIDER, 'groq');
  await assert.rejects(llm.chat([]), /GROQ_API_KEY missing/);
  await assert.rejects(llm.chatStream([]), /GROQ_API_KEY missing/);
  await assert.rejects(llm.assertRunning(), /GROQ_API_KEY missing/);
  assert.equal(calls(), 0);
});

test('Groq outage and open circuit never return a fabricated answer or another provider', async () => {
  for (const tools of [undefined, [{ name: 'check' }]]) {
    for (const behavior of [async () => { throw Object.assign(new Error('SECRET'), { status: 429 }); },
      async () => ({ fallback: true })]) {
      const { llm, calls } = load({ GROQ_API_KEY: 'synthetic-key' }, behavior);
      await assert.rejects(llm.chat([], { tools }), e =>
        e.code === (tools ? 'LLM_TOOL_CALL_FAILED' : 'LLM_UNAVAILABLE') && !e.message.includes('SECRET'));
      assert.equal(calls(), 0);
    }
  }
});

test('local-only flag blocks cloud access without a local provider', async () => {
  const { llm } = load({ GROQ_API_KEY: 'synthetic-key', AI_LOCAL_ONLY: 'true' }, () => assert.fail('No cloud call'));
  await assert.rejects(llm.chat([]), /AI_LOCAL_ONLY/);
});

test('project gateway policy allows only Groq', () => {
  const policy = require('../../../config/ai-gateway.json');
  assert.deepEqual(Object.keys(policy.providers), ['groq']);
});
