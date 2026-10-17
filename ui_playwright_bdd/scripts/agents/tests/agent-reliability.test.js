'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const vm = require('vm');
const { requestAnalysis, analysisPrompt } = require('../shared/llm-analysis');
const { validateGenerated } = require('../shared/generated-code');
function temporary(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-reliability-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 }));
  return root;
}
for (const failure of ['HTTP 400', 'HTTP 413', 'invalid JSON']) {
  test(`analysis recovers from ${failure} with one smaller plain JSON request`, async () => {
    const sizes = [];
    const llm = { chat: async (messages, options) => {
      assert.equal(messages.length, 1);
      assert.equal(messages[0].role, 'user');
      assert.equal(options.tools, undefined);
      sizes.push(messages[0].content.length);
      if (sizes.length === 1) { if (failure === 'invalid JSON') return { message: { content: '{' } }; throw new Error(failure); }
      return { message: { content: JSON.stringify({ action: 'report_analysis', root_cause: 'Evidence is insufficient; hypothesis only' }) } };
    } };
    const decision = await requestAnalysis(llm, limit => analysisPrompt({ name: 'test', message: 'x'.repeat(50000), trace: 't'.repeat(50000) }, 'c'.repeat(50000), new Map([['a', 'source'.repeat(50000)]]), limit), true);
    assert.equal(decision.action, 'report_analysis');
    assert.equal(sizes.length, 2);
    assert.ok(sizes[0] <= 12000);
    assert.ok(sizes[1] <= 6000);
    assert.ok(sizes[1] < sizes[0]);
  });
}
test('unavailability and illegal tool actions never become successful analyses', async () => {
  for (const data of [{ raw: 'unavailable' }, { action: 'apply_fix' }, { action: 'report_analysis', root_cause: '' }]) {
    let calls = 0;
    await assert.rejects(requestAnalysis({ chat: async () => { calls++; return { message: { content: JSON.stringify(data) } }; } }, () => 'evidence'), /invalid/);
    assert.equal(calls, 2);
  }
});
test('final turn requests only conclusion fields, never another read action', async () => {
  const prompt = analysisPrompt({ name: 'example' }, '', new Map(), 12000, true);
  assert.doesNotMatch(prompt, /Return action read_file/);
  assert.match(prompt, /No further file requests/);
  const data = await requestAnalysis({ chat: async (messages) => {
    const schema = JSON.parse(messages[0].content.split('Return ONLY valid JSON following this schema:\n')[1]);
    assert.equal(schema.action, undefined);
    assert.equal(schema.file_path, undefined);
    return { message: { content: JSON.stringify({ root_cause: 'Observed network error; application behavior untested', confidence: 0.8 }) } };
  } }, () => 'recorded evidence', true);
  assert.equal(data.action, 'report_analysis');
});
test('Codegen validates real Gherkin and TypeScript, rejects fallback prose', () => {
  assert.doesNotThrow(() => validateGenerated('Feature: Test\n Scenario: Example\n  Given a state\n', 'gherkin'));
  assert.doesNotThrow(() => validateGenerated('export class Page {}', 'typescript'));
  for (const type of ['gherkin', 'typescript']) {
    for (const text of ['', 'Service LLM temporairement indisponible.', 'This is not source code']) assert.throws(() => validateGenerated(text, type));
  }
  assert.throws(() => validateGenerated('Feature: No scenarios', 'gherkin'));
  assert.throws(() => validateGenerated('export class {', 'typescript'));
});
for (const mode of ['plane-missing', 'no-stories', 'llm-fallback', 'valid', 'partial', 'unspecified']) {
  test(`Codegen spec propagates ${mode} and never writes unusable output`, async t => {
    const root = temporary(t);
    const fakeProcess = { env: {}, argv: ['node', 'codegen-agent.js', 'spec'], exitCode: 0 };
    let calls = 0;
    const deps = {
      './shared/skill-store': require('../shared/skill-store'),
      './shared/agent-verifier': require('../shared/agent-verifier'),
      './shared/change-proposals': require('../shared/change-proposals'),
      dotenv: { config() {} },
      './llm': { chat: async () => {
        calls++;
        if (mode === 'partial' && calls === 2) throw new Error('Provider failed');
        return { message: { content: mode === 'llm-fallback' ? 'Service LLM temporairement indisponible.' : 'Feature: Test\n Scenario: Example\n  Given a state\n' } };
      } },
      './plane-fetcher': { assertConnection: async () => { if (mode === 'plane-missing') throw new Error('Config Plane missing'); },
        fetchStories: async () => mode === 'no-stories' ? [] : (mode === 'partial' ? ['QA-1', 'QA-2'] : ['QA-1']).map(key => ({ key, summary: 'Story',
          description: mode === 'unspecified' ? 'Titre historique non spécifié : exigences à clarifier, aucune couverture attribuée.' : 'Given a state, verify the documented result.' })) },
      './shared/tracer': { Span: class { begin() { return this; } end() {} } },
      './shared/prompt-store': { get() {}, recordUsage() {} },
      './shared/generated-code': { validateGenerated },
      './shared/gherkin-contract': require('../shared/gherkin-contract'),
      './shared/story-readiness': require('../shared/story-readiness'),
    };
    const module = { exports: {} };
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../codegen-agent.js'), 'utf8'), {
      __dirname: path.join(root, 'scripts/agents'), module, process: fakeProcess, console: { log() {}, error() {} },
      require: name => Object.hasOwn(deps, name) ? deps[name] : require(name),
    });
    await module.exports.cmdSpec();
    assert.equal(fakeProcess.exitCode, mode === 'valid' ? 0 : 1);
    if (mode === 'unspecified') assert.equal(calls, 0, 'Missing criteria must not reach the model');
    const files = fs.readdirSync(path.join(root, 'src/features'));
    assert.equal(files.length, 0, 'Generation never edits reviewed sources');
    const proposalsDir = path.join(root, 'logs/change-proposals');
    assert.equal(fs.existsSync(proposalsDir) ? fs.readdirSync(proposalsDir).length : 0, ['valid', 'partial'].includes(mode) ? 1 : 0);
  });
}
