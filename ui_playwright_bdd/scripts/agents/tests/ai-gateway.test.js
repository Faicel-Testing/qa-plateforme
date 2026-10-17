'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { gatewayFetch, policy, reserve, isGatewayError } = require('../shared/ai-gateway');
const endpoint = 'https://api.groq.com/openai/v1/chat/completions';

test('Windows transient lock release failures retry without resetting quotas', () => {
  const { releaseQuotaLock } = require('../shared/ai-gateway');
  let closed = 0, removed = 0;
  const delays = [];
  releaseQuotaLock(42, 'owned-lock', { closeSync: () => { closed++; }, unlinkSync: () => {
    if (++removed < 3) throw Object.assign(Error('sharing violation'), { code: 'EPERM' });
  } }, ms => delays.push(ms));
  assert.equal(closed, 1); assert.equal(removed, 3); assert.deepEqual(delays, [50, 100]);
});

test('permanent lock release failure stays blocked with a precise reason', async () => {
  const { releaseQuotaLock } = require('../shared/ai-gateway');
  let attempts = 0;
  const release = () => releaseQuotaLock(42, 'owned-lock', { closeSync() {}, unlinkSync() {
    attempts++; throw Object.assign(Error('private-path'), { code: 'EBUSY' });
  } }, () => {});
  const f = fixture({ reserve: release });
  await assert.rejects(f.fetch(endpoint, request()), /QUOTA_RELEASE_FAILED/);
  assert.equal(attempts, 5); assert.equal(f.calls.length, 0);
  assert.doesNotMatch(JSON.stringify(f.events), /private-path/);
});
test('quota contention retries but quota refusals remain immediate', async () => {
  const { reserveWithRetry } = require('../shared/ai-gateway');
  let calls = 0;
  await reserveWithRetry({}, 1, 'test', () => { if (++calls === 1) throw Object.assign(new Error('busy'), { reason: 'QUOTA_BUSY_OR_UNAVAILABLE' }); });
  assert.equal(calls, 2);
  calls = 0;
  await assert.rejects(reserveWithRetry({}, 1, 'test', () => { calls++; throw Object.assign(new Error('budget'), { reason: 'TASK_BUDGET' }); }), /budget/);
  assert.equal(calls, 1);
});
const request = (extra = {}) => ({ method: 'POST', body: JSON.stringify({ model: 'openai/gpt-oss-120b', messages: [{ role: 'user', content: 'Explain a test failure' }], ...extra }) });
function fixture(overrides = {}) {
  const calls = [], events = [], reservations = [];
  const fetch = gatewayFetch('groq', async (url, init) => { calls.push({ url, init }); return Response.json({ ok: true }); },
    { policy: policy(), env: {}, audit: e => events.push(e), reserve: (...args) => reservations.push(args), ...overrides });
  return { fetch, calls, events, reservations };
}
test('authorized streaming call is bounded, cancellable, audited without payload or headers', async () => {
  const f = fixture();
  const controller = new AbortController();
  await f.fetch(endpoint, { ...request({ stream: true }), signal: controller.signal, headers: { Authorization: 'Bearer credential-not-in-payload' } });
  assert.equal(f.calls.length, 1);
  assert.equal(f.calls[0].init.redirect, 'error');
  assert.equal(JSON.parse(f.calls[0].init.body).max_completion_tokens, 4096);
  assert.equal(JSON.parse(f.calls[0].init.body).stream, true);
  controller.abort();
  assert.equal(f.calls[0].init.signal.aborted, true);
  assert.equal(f.events[0].decision, 'ALLOW');
  assert.doesNotMatch(JSON.stringify(f.events), /credential|Explain/);
});
test('destinations, routes, query strings and unsupported bodies fail before any network', async () => {
  const f = fixture();
  for (const url of ['https://evil.test/openai/v1/chat/completions', 'http://api.groq.com/openai/v1/chat/completions', endpoint + '?token=x', 'https://api.groq.com/other', 'https://user:pass@api.groq.com/openai/v1/chat/completions']) {
    await assert.rejects(f.fetch(url, request()), isGatewayError);
  }
  await assert.rejects(f.fetch(endpoint, { method: 'POST', body: '{}' }), isGatewayError);
  await assert.rejects(f.fetch(endpoint, { method: 'POST', body: '{bad' }), isGatewayError);
  await assert.rejects(f.fetch(new Request(endpoint), request()), isGatewayError);
  assert.equal(f.calls.length, 0);
});
test('blocks secrets even in escaped JSON, tools and embeddings without logging values', async () => {
  const f = fixture({ env: { GROQ_API_KEY: 'synthetic-private-credential' } });
  for (const body of [request({ messages: [{ role: 'user', content: 'synthetic-private-credential' }] }),
    request({ tools: [{ description: 'gsk_1234567890abcdefghijklmnop' }] }),
    request({ tools: [{ description: 'plane_api_00000000000000000000000000000000' }] }),
    { method: 'POST', body: JSON.stringify({ model: 'openai/gpt-oss-120b', input: 'synthetic-private-credential' }).replace('synthetic', '\\u0073ynthetic') }]) {
    await assert.rejects(f.fetch(endpoint, body), /SECRET_IN_PAYLOAD/);
  }
  assert.equal(f.calls.length, 0);
  assert.doesNotMatch(JSON.stringify(f.events), /synthetic-private|gsk_/);
});
test('rejects insecure TLS, custom transports, unknown models and oversized output', async () => {
  const f = fixture();
  await assert.rejects(fixture({ env: { NODE_TLS_REJECT_UNAUTHORIZED: '0' } }).fetch(endpoint, request()), /TLS_DISABLED/);
  await assert.rejects(f.fetch(endpoint, { ...request(), dispatcher: {} }), /CUSTOM_TLS_TRANSPORT/);
  await assert.rejects(f.fetch(endpoint, request({ model: 'not-approved' })), /MODEL_NOT_ALLOWED/);
  await assert.rejects(f.fetch(endpoint, request({ max_completion_tokens: 99999 })), /OUTPUT_LIMIT/);
  await assert.rejects(f.fetch(endpoint, request({ n: 2 })), /MULTIPLE_COMPLETIONS/);
  await assert.rejects(f.fetch(endpoint, request({ messages: ['x'.repeat(200001)] })), /REQUEST_TOO_LARGE/);
  assert.equal(f.calls.length, 0);
});
test('redirects and unavailable audit never silently pass', async () => {
  const fetch = gatewayFetch('groq', async () => new Response(null, { status: 302, headers: { Location: 'https://evil.test' } }),
    { policy: policy(), env: {}, audit: () => {}, reserve: () => {} });
  await assert.rejects(fetch(endpoint, request()), /REDIRECT/);
  const f = fixture({ audit: () => { throw Error('disk failed'); } });
  await assert.rejects(f.fetch(endpoint, request()));
  assert.equal(f.calls.length, 0);
});
test('removed Ollama provider is blocked before health or embedding requests', async () => {
  let count = 0;
  const fetch = gatewayFetch('ollama', async () => { count++; return Response.json({}); },
    { policy: policy(), env: {}, audit: () => {}, reserve: () => {} });
  await assert.rejects(fetch('http://127.0.0.1:11434/api/tags'), /PROVIDER_NOT_ALLOWED/);
  await assert.rejects(fetch('http://127.0.0.1:11434/api/embed', { method: 'POST', body: JSON.stringify({ model: 'embeddinggemma:300m-qat-q4_0', input: ['QA'] }) }), /PROVIDER_NOT_ALLOWED/);
  assert.equal(count, 0);
});
test('file quotas persist across callers and fail closed on corrupt or locked ledger', t => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'gateway-test-'));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const rules = { ...policy(), maxRequestsPerMinute: 2, maxReservedUnitsPerTask: 10 };
  reserve(rules, 6, 'task-a', dir, 100000);
  assert.throws(() => reserve(rules, 5, 'task-a', dir, 100001), /TASK_BUDGET/);
  reserve(rules, 1, 'task-b', dir, 100002);
  assert.throws(() => reserve(rules, 1, 'task-c', dir, 100003), /RATE_LIMIT/);
  fs.writeFileSync(path.join(dir, 'quota.json'), 'broken');
  assert.throws(() => reserve(rules, 1, 'task-c', dir, 200000), /QUOTA_UNAVAILABLE/);
  fs.writeFileSync(path.join(dir, 'quota.lock'), '');
  assert.throws(() => reserve(rules, 1, 'task-c', dir, 200000), /QUOTA_BUSY_OR_UNAVAILABLE/);
});
test('SDK wrappers preserve recognizable gateway rejection through causes', () => {
  assert.equal(isGatewayError({ cause: { cause: { code: 'AI_GATEWAY_BLOCKED' } } }), true);
  assert.equal(isGatewayError(new Error('ordinary outage')), false);
});
