'use strict';
require('ts-node/register');
const test = require('node:test');
const assert = require('node:assert/strict');
const { request } = require('@playwright/test');
const { QACartApiClient, apiErrorCode } = require('../../../src/api/QACartApiClient');

test('API diagnostics record response/network evidence without request credentials or response bodies', async () => {
  const original = request.newContext, savedUrl = process.env.BASE_URL, originalLog = console.log;
  const outputs = [];
  console.log = line => outputs.push(line);
  process.env.BASE_URL = 'https://user:URL_SECRET@example.test/private?token=QUERY_SECRET';
  try {
    for (const mode of ['success', 'access-token', 'http', 'network', 'timeout', 'missing-token']) {
      const events = [];
      let disposed = false;
      request.newContext = async () => ({
        post: async (_path, opts) => {
          assert.equal(opts.timeout, 30000); assert.equal(opts.maxRetries, 0);
          if (mode === 'network') throw new Error('apiRequestContext.post: read ECONNRESET BODY_SECRET');
          if (mode === 'timeout') throw new Error('request timeout BODY_SECRET');
          return { status: () => mode === 'http' ? 503 : 200, ok: () => mode !== 'http',
            json: async () => mode === 'missing-token' ? {} : mode === 'access-token'
              ? { access_token: 'RESPONSE_SECRET', firstName: 'Test' } : { token: 'RESPONSE_SECRET' },
            text: () => assert.fail('Never read a sensitive response body into an error') };
        }, dispose: async () => { disposed = true; },
      });
      const client = new QACartApiClient(event => events.push(event));
      const call = client.register({ firstName: 'Test', lastName: 'User', email: 'private@example.test', password: 'PASSWORD_SECRET' });
      if (['success', 'access-token'].includes(mode)) assert.equal(await call, 'RESPONSE_SECRET');
      else await assert.rejects(call, error => !/SECRET|private@example/.test(error.message));
      assert.equal(disposed, true); assert.equal(events.length, 1);
      assert.equal(events[0].target, 'https://example.test');
      assert.equal(events[0].status, ['network', 'timeout'].includes(mode) ? null : mode === 'http' ? 503 : 200);
      assert.equal(events[0].errorCode, { success: null, 'access-token': null, http: 'HTTP_ERROR', network: 'ECONNRESET', timeout: 'TIMEOUT', 'missing-token': 'API_TOKEN_MISSING' }[mode]);
      assert.doesNotMatch(JSON.stringify(events), /SECRET|private@example/);
    }
    assert.equal(apiErrorCode({ cause: { code: 'ENOTFOUND' } }), 'ENOTFOUND');
    assert.doesNotMatch(outputs.join('\n'), /SECRET|private@example/);
  } finally {
    request.newContext = original; console.log = originalLog;
    if (savedUrl === undefined) delete process.env.BASE_URL; else process.env.BASE_URL = savedUrl;
  }
});
