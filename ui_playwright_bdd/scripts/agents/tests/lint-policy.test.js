'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { ESLint } = require('eslint');
const root = path.resolve(__dirname, '../../..');
const eslint = new ESLint({ cwd: root });

test('JavaScript lint rejects an undefined variable in an agent', async () => {
  const [result] = await eslint.lintText('missingConfiguration.run();', {
    filePath: path.join(root, 'scripts/agents/ci-agent.js'),
  });
  assert.ok(result.messages.some(message => message.ruleId === 'no-undef' && message.severity === 2));
});

test('typed lint rejects an unhandled promise in a page object', async () => {
  const [result] = await eslint.lintText('export function check() { Promise.resolve(42); }', {
    filePath: path.join(root, 'src/pages/BasePage.ts'),
  });
  assert.ok(result.messages.some(message => message.ruleId === '@typescript-eslint/no-floating-promises' && message.severity === 2));
});

test('lint includes maintained sources but excludes generated artifacts', async () => {
  assert.equal(await eslint.isPathIgnored(path.join(root, 'src/hooks/hooks.ts')), false);
  assert.equal(await eslint.isPathIgnored(path.join(root, 'scripts/agents/bug-agent.js')), false);
  assert.equal(await eslint.isPathIgnored(path.join(root, 'allure-report/app.js')), true);
  assert.equal(await eslint.isPathIgnored(path.join(root, 'logs/proposal.js')), true);
});
