'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { browserResult } = require('../shared/browser-result');

test('browser executions stay distinct while retries share their browser history', () => {
  const original = { uuid: 'one', historyId: 'same-scenario', name: 'Login', status: 'passed', start: 1, stop: 2 };
  const chromium = browserResult(original, 'chromium');
  const firefox = browserResult({ ...original, uuid: 'two' }, 'firefox');
  const retry = browserResult({ ...original, uuid: 'three', status: 'failed', start: 0, stop: 1 }, 'chromium');
  assert.notEqual(chromium.historyId, firefox.historyId);
  assert.equal(chromium.historyId, retry.historyId);
  assert.equal(chromium.name, original.name);
  assert.equal(original.parameters, undefined);
  // Allure groups retries using historyId: two browsers must remain two cases.
  assert.equal(new Set([chromium, firefox, retry].map(r => r.historyId)).size, 2);
  assert.equal(chromium.parameters.find(p => p.name === 'browser').value, 'chromium');
  assert.equal(firefox.parameters.find(p => p.name === 'browser').value, 'firefox');
});
