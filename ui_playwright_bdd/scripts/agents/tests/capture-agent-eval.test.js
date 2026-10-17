'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const cb = require('../shared/circuit-breaker');
test('capture preserves actual messages and output, excludes assistant claims and fallback', async () => {
  const execute = cb.execute, write = fs.writeFileSync, mkdir = fs.mkdirSync, log = console.log;
  const files = [];
  let fallback = false;
  try {
    cb.execute = async () => ({ value: JSON.stringify({ message: { content: 'Actual answer' } }), fromCache: true, fallback });
    fs.mkdirSync = () => {};
    fs.writeFileSync = (name, content) => files.push(JSON.parse(content));
    console.log = () => {};
    const modulePath = require.resolve('../../capture-agent-eval');
    delete require.cache[modulePath];
    require(modulePath);
    const messages = [{ role: 'system', content: 'Actual evidence' }, { role: 'user', content: 'Question' }, { role: 'assistant', content: 'Unverified earlier claim' }];
    const result = await cb.execute(null, messages, 'chat', 0);
    assert.equal(JSON.parse(result.value).message.content, 'Actual answer');
    assert.deepEqual(files[0].cases[0].messages, messages);
    assert.deepEqual(files[0].cases[0].retrieval_context, ['Actual evidence', 'Question']);
    assert.equal(files[0].cases[0].actual_output, 'Actual answer');
    assert.equal(files[0].cases[0].fromCache, true);
    fallback = true;
    await cb.execute(null, messages, 'chat', 0);
    assert.equal(files.length, 1);
    delete require.cache[modulePath];
  } finally {
    cb.execute = execute; fs.writeFileSync = write; fs.mkdirSync = mkdir; console.log = log;
  }
});
