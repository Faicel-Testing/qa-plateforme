'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { InMemorySpanExporter } = require('@opentelemetry/sdk-trace-base');
const exporter = new InMemorySpanExporter();
const actual = require('@langfuse/otel');
const saved = require.cache[require.resolve('@langfuse/otel')].exports;
require.cache[require.resolve('@langfuse/otel')].exports = { ...actual,
  LangfuseSpanProcessor: class extends actual.LangfuseSpanProcessor {
    constructor(options) { super({ ...options, exporter }); }
  } };
process.env.LANGFUSE_ENABLED = 'true';
process.env.LANGFUSE_PUBLIC_KEY = 'pk-lf-unit';
process.env.LANGFUSE_SECRET_KEY = 'sk-lf-unit';
process.env.LANGFUSE_BASE_URL = 'http://127.0.0.1:3000';
const observations = require('../shared/langfuse-observability');
test.after(async () => { await observations.flush(); require.cache[require.resolve('@langfuse/otel')].exports = saved; });

test('only allowed metadata is exported; exceptions never retain raw messages', async () => {
  await assert.rejects(observations.span('unit.failure', {
    input: 'SECRET-input', output: 'SECRET-output', headers: 'SECRET-auth', 'qa.chunks': 12,
  }, async () => { throw new Error('SECRET-business-error'); }), /SECRET-business-error/);
  await observations.flush();
  const spans = exporter.getFinishedSpans();
  assert.ok(spans.length > 0, 'The real Langfuse processor must export our scope');
  const failure = spans.find(s => s.name === 'unit.failure');
  assert.equal(failure.attributes['qa.chunks'], 12);
  assert.equal(failure.status.message, 'OPERATION_FAILED');
  assert.doesNotMatch(JSON.stringify(failure.attributes), /SECRET/);
  assert.equal(failure.events.length, 0);
});

test('nested spans and child processes share the W3C trace context', async () => {
  let carrier, rootId;
  await observations.span('unit.parent', {}, async () => {
    rootId = observations.traceId();
    carrier = observations.childEnvironment();
    await observations.span('unit.child', {}, () => assert.equal(observations.traceId(), rootId));
  });
  assert.match(carrier.QA_TRACEPARENT, new RegExp('^00-' + rootId + '-[0-9a-f]{16}-01$'));
  await observations.flush();
  const spans = exporter.getFinishedSpans(), parent = spans.find(s => s.name === 'unit.parent'), child = spans.find(s => s.name === 'unit.child');
  assert.equal(child.parentSpanContext?.spanId || child.parentSpanId, parent.spanContext().spanId);
});

test('disabled tracing preserves operation results and creates no span', async () => {
  process.env.LANGFUSE_ENABLED = 'false';
  assert.equal(await observations.span('unit.disabled', {}, () => 42), 42);
  process.env.LANGFUSE_ENABLED = 'true';
  await observations.flush();
  assert.ok(!exporter.getFinishedSpans().some(s => s.name === 'unit.disabled'));
});

test('credentials in URLs and unencrypted remote endpoints are rejected', () => {
  assert.throws(() => observations.endpoint({ LANGFUSE_BASE_URL: 'http://remote.invalid' }), /Invalid/);
  assert.throws(() => observations.endpoint({ LANGFUSE_BASE_URL: 'https://user:password@remote.invalid' }), /Invalid/);
  assert.equal(observations.endpoint({ LANGFUSE_BASE_URL: 'http://localhost:3000' }), 'http://localhost:3000');
});

test('simulated provider observations cannot be mistaken for a priced real model call', async () => {
  const fetcher = require('../shared/task-metrics').meteredFetch('groq', async () => Response.json({
    usage: { prompt_tokens: 3, completion_tokens: 2 }, choices: [{ message: { content: 'SECRET-response' } }],
  }), { simulated: true, emit: () => {} });
  await fetcher('https://api.groq.com/openai/v1/chat/completions', { body: JSON.stringify({ model: 'openai/gpt-oss-20b', messages: [{ role: 'user', content: 'SECRET-prompt' }] }) });
  await observations.flush();
  const span = exporter.getFinishedSpans().findLast(s => s.name === 'groq.request');
  assert.equal(span.attributes['qa.simulated'], true);
  assert.equal(span.attributes['gen_ai.request.model'], 'synthetic-installation-model');
  assert.equal(span.attributes['gen_ai.usage.input_tokens'], 3);
  assert.equal(span.attributes['qa.estimated_cost_usd'], undefined);
  assert.doesNotMatch(JSON.stringify(span.attributes), /SECRET/);
});

test('a failed child result stays failed without changing its return value', async () => {
  const result = { success: false, exitCode: 1 };
  assert.equal(await observations.span('unit.failed-process', {}, () => result), result);
  await observations.flush();
  const span = exporter.getFinishedSpans().find(s => s.name === 'unit.failed-process');
  assert.equal(span.status.code, 2);
  assert.equal(span.attributes['qa.exit_code'], 1);
});
