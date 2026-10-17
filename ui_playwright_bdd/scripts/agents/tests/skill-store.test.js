'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const store = require('../shared/skill-store');
test('all registered skills load with identity and revision; only selected instructions enter messages', () => {
  for (const name of store.ALLOWED) {
    const skill = store.load(name);
    assert.equal(skill.name, name);
    assert.match(skill.sha256, /^[a-f0-9]{64}$/);
    const messages = store.messages(name, 'Task evidence');
    assert.equal(messages.length, 2);
    assert.equal(messages[0].role, 'system');
    assert.ok(messages[0].content.includes(skill.body));
    assert.equal(messages[1].content, 'Task evidence');
  }
  for (const name of ['../.env', 'https://example.test', 'unregistered', '__proto__']) {
    assert.throws(() => store.load(name), { code: 'AGENT_SKILL_INVALID' });
  }
});
test('missing, malformed, oversized and escaped skill files fail closed', () => {
  const file = path.join(__dirname, '../shared/skill-store.js');
  for (const mode of ['missing', 'invalid', 'oversized', 'escape']) {
    const module = { exports: {} };
    vm.runInNewContext(fs.readFileSync(file, 'utf8'), {
      module, __dirname: path.dirname(file),
      require: name => name !== 'node:fs' ? require(name) : {
        realpathSync: p => { if (mode === 'missing') throw Error('missing'); return mode === 'escape' && p.endsWith('SKILL.md') ? path.resolve(__dirname, 'outside.md') : p; },
        statSync: () => ({ size: mode === 'oversized' ? 16001 : 100 }),
        readFileSync: () => '---\nname: wrong-name\ndescription: test\n---\ntext',
      },
    });
    assert.throws(() => module.exports.load('analyse-echec'), { code: 'AGENT_SKILL_INVALID' });
  }
});
test('bug procedure reaches the actual analysis request within its budget', async () => {
  const { analysisPrompt, requestAnalysis } = require('../shared/llm-analysis');
  let received;
  await requestAnalysis({ chat: async messages => { received = messages[0].content; return { message: { content: '{"root_cause":"Hypothesis only"}' } }; } },
    limit => analysisPrompt({ name: 'Failure', message: 'Timeout', trace: '' }, '', new Map(), limit, true), true);
  assert.ok(received.includes(store.load('analyse-echec').body));
  assert.ok(received.includes('FINAL TURN'));
  assert.ok(received.length <= 12000);
});
