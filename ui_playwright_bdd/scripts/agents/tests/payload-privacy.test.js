'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { sanitize } = require('../shared/payload-privacy');
const { gatewayFetch, policy } = require('../shared/ai-gateway');
test('nested content, tool arguments, credentials and URL paths are sanitized without mutation', () => {
  const original = { messages: [{ content: 'https://user:pass@internal.company/path-secret?key=hidden#fragment person@example.com password="short-pass"' }],
    tool_calls: [{ function: { arguments: JSON.stringify({ cookie: 'session=private', email: 'tool@example.com' }) } }] };
  const result = JSON.stringify(sanitize(original));
  assert.doesNotMatch(result, /internal\.company|path-secret|hidden|fragment|person@|tool@|short-pass|session=private/);
  assert.match(original.messages[0].content, /short-pass/);
  assert.match(result, /REDACTED/);
});
test('transport sanitizes before fetch and audit; local-only and secrets fail closed', async () => {
  const calls = [], events = [];
  const deps = { policy: policy(), env: {}, reserve: () => {}, audit: e => events.push(e) };
  const fetch = gatewayFetch('groq', async (url, init) => { calls.push(init); return Response.json({}); }, deps);
  const url = 'https://api.groq.com/openai/v1/chat/completions';
  const req = content => ({ method: 'POST', body: JSON.stringify({ model: 'openai/gpt-oss-120b', messages: [{ role: 'user', content }] }) });
  await fetch(url, req('person@example.com https://private.local/secret?token=short password="small"'));
  assert.doesNotMatch(calls[0].body, /person@|private.local|small|token=short/);
  assert.doesNotMatch(JSON.stringify(events), /person@|private.local|small/);
  deps.env.AI_LOCAL_ONLY = 'true';
  await assert.rejects(fetch(url, req('safe')), /LOCAL_ONLY/);
  deps.env.AI_LOCAL_ONLY = 'false';
  deps.env.API_KEY = 'synthetic-known-secret';
  await assert.rejects(fetch(url, req('synthetic-known-secret')), /SECRET_IN_PAYLOAD/);
  assert.equal(calls.length, 1);
});
