'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { walkSources, buildSourceBatches, validateReview, verifySources } = require('../shared/source-verification');

function fixture(t, entries) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-source-audit-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true, maxRetries: 3, retryDelay: 100 }));
  for (const [file, content] of Object.entries(entries)) {
    fs.mkdirSync(path.dirname(path.join(root, file)), { recursive: true });
    fs.writeFileSync(path.join(root, file), content);
  }
  return root;
}

const entries = {
  'src/features/login.feature': 'Feature: Login\n  Scenario: Login\n    Then I am logged in\n',
  'src/steps/login.ts': `import { Then } from '@cucumber/cucumber';\n${'// comment\n'.repeat(80)}Then('I am logged in', async function () { await page.assertLoggedIn(); });\n`,
  'src/hooks/hooks.ts': 'After(async function () { await this.dispose(); });\n',
  'src/core/world.ts': 'export class World { async dispose() { await this.browser.close(); } }\n',
  'src/pages/login.ts': 'async function assertLoggedIn() { await expect(user).toBeVisible(); }\n',
  'src/support/data.ts': 'export const randomUser = () => ({ email: randomEmail() });\n',
};
const localChecks = { typescript: { status: 'PASS', diagnostics: [] }, cucumber: { status: 'PASS', scenarios: 1, steps: 1 } };
const clean = { status: 'COMPLETE', findings: [], suggestions: [], limitations: [] };
function fakeLlm(reply = clean) {
  const prompts = [];
  return { prompts, chat: async messages => {
    prompts.push(messages[0].content);
    return { message: { content: typeof reply === 'string' ? reply : JSON.stringify(reply) } };
  } };
}

test('validated batches resume from cache; source or model changes invalidate it', async t => {
  const root = fixture(t, entries), cacheDir = path.join(root, 'cache');
  const llm = { ...fakeLlm(), MODEL: 'model-a' };
  const first = await verifySources(root, llm, { localChecks, cacheDir });
  assert.ok(first.every(r => r.verdict === 'VALID'));
  const calls = llm.prompts.length;
  const resumed = await verifySources(root, llm, { localChecks, cacheDir });
  assert.equal(llm.prompts.length, calls);
  assert.ok(resumed[0].evidence.reviews.every(r => r.cached && r.attempts === 0));
  fs.appendFileSync(path.join(root, 'src/steps/login.ts'), '\n// changed');
  await verifySources(root, llm, { localChecks, cacheDir });
  assert.ok(llm.prompts.length > calls);
  const count = llm.prompts.length;
  llm.MODEL = 'model-b';
  await verifySources(root, llm, { localChecks, cacheDir });
  assert.ok(llm.prompts.length > count);
});

test('incomplete responses retry and are never cached as complete', async t => {
  const root = fixture(t, entries), cacheDir = path.join(root, 'cache');
  const llm = fakeLlm({ ...clean, status: 'INCOMPLETE' });
  const results = await verifySources(root, llm, { localChecks, cacheDir, retryDelayMs: 0 });
  assert.equal(llm.prompts.length, 2);
  assert.notEqual(llm.prompts[0], llm.prompts[1]);
  assert.equal(results[0].verdict, 'NOT_EVALUATED');
  assert.equal(fs.existsSync(cacheDir), false);
});

test('all complete sources reach the LLM, including nested files, hooks, World and Page Objects', async t => {
  const data = { ...entries, 'src/steps/nested/fourth.ts': '// Fourth file\nexport const lastMarker = true;\n',
    '.env': 'SECRET_DO_NOT_SEND', 'src/fixtures/user.json': '{"password":"SECRET_DO_NOT_SEND"}' };
  const root = fixture(t, data);
  const llm = fakeLlm();
  const results = await verifySources(root, llm, { localChecks });
  const transmitted = llm.prompts.flatMap(prompt => JSON.parse(prompt.split('Fichiers complets de ce lot :\n')[1]));
  for (const [file, content] of Object.entries(data).filter(([file]) => /\.(ts|feature)$/.test(file))) {
    assert.ok(transmitted.some(sent => sent.file === file && sent.content === content), file);
  }
  assert.doesNotMatch(llm.prompts.join('\n'), /SECRET_DO_NOT_SEND/);
  assert.ok(results.every(r => r.verdict === 'VALID'));
  assert.equal(results[0].evidence.reviewedFiles, 7);
  assert.equal(results[1].targetFiles, 2);
});

test('batching respects the budget without truncating or silently dropping any source', t => {
  const data = { ...entries };
  for (let i = 0; i < 7; i++) data[`src/steps/large${i}.ts`] = '// whole file\n'.repeat(150) + `// end-${i}`;
  const { files } = walkSources(fixture(t, data));
  const { batches, omitted } = buildSourceBatches(files, localChecks, 8000);
  assert.ok(batches.length > 1);
  assert.deepEqual(omitted, []);
  const seen = new Set();
  for (const batch of batches) {
    assert.ok(batch.prompt.length <= 8000);
    assert.ok(batch.files.some(f => f.file === 'src/hooks/hooks.ts'));
    assert.ok(batch.files.some(f => f.file === 'src/core/world.ts'));
    batch.files.forEach(f => { assert.equal(f.content, data[f.file]); seen.add(f.file); });
  }
  assert.equal(seen.size, files.length);
});

test('an oversized file makes coverage incomplete instead of approving an excerpt', async t => {
  const root = fixture(t, { ...entries, 'src/steps/large.ts': '// long\n'.repeat(5000) });
  const llm = fakeLlm();
  const results = await verifySources(root, llm, { localChecks, maxChars: 8000 });
  assert.equal(results[0].verdict, 'VALID');
  assert.equal(results[1].verdict, 'NOT_EVALUATED');
  assert.ok(results[0].evidence.omitted.some(f => f.file === 'src/steps/large.ts'));
  assert.ok(results[0].evidence.unreviewedFiles.includes('src/steps/large.ts'));
  assert.ok(llm.prompts.every(p => !p.includes('// long')));
});

test('a concrete defect beyond character 300 and after the first three files is preserved', async t => {
  const source = '// context\n'.repeat(100) + 'doSomethingIncorrect();\n';
  const root = fixture(t, { ...entries, 'src/steps/z-last.ts': source });
  const finding = { file: 'src/steps/z-last.ts', line: 101, quote: 'doSomethingIncorrect();', severity: 'error', message: 'Concrete defect' };
  const results = await verifySources(root, fakeLlm({ ...clean, findings: [finding] }), { localChecks });
  assert.equal(results[0].verdict, 'VALID');
  assert.equal(results[1].verdict, 'INVALID');
  assert.deepEqual(results[1].findings, [finding]);
});

test('style suggestions do not lower a valid verdict', async t => {
  const root = fixture(t, entries);
  const results = await verifySources(root, fakeLlm({ ...clean, suggestions: ['Prefer a different tag order'] }), { localChecks });
  assert.ok(results.every(r => r.verdict === 'VALID'));
  assert.deepEqual(results[0].evidence.reviews[0].suggestions, ['Prefer a different tag order']);
});

test('invented file/line/quote references cannot produce a defect verdict', () => {
  const files = [{ file: 'src/steps/example.ts', content: 'await page.assertReady();\nawait page.assertReady();\n' }];
  for (const finding of [
    { file: 'src/steps/other.ts', line: 1, quote: 'await page.assertReady();' },
    { file: files[0].file, line: 8, quote: 'await page.assertReady();' },
    { file: files[0].file, line: 1, quote: 'page.click();' },
  ]) {
    const review = validateReview(JSON.stringify({ ...clean, findings: [{ ...finding, severity: 'error', message: 'Missing await' }] }), files);
    assert.equal(review.status, 'COMPLETE');
    assert.equal(review.reviewStatus, 'NEEDS_REVIEW');
    assert.equal(review.findings.length, 0);
    assert.equal(review.rejectedFindings.length, 1);
  }
});

test('provider fallback is not a quality warning and stops remaining source calls', async t => {
  const root = fixture(t, { ...entries, 'src/steps/extra.ts': '// whole file\n'.repeat(500) });
  const llm = fakeLlm('Service LLM temporairement indisponible.');
  const results = await verifySources(root, llm, { localChecks, maxChars: 10000, retryDelayMs: 0 });
  assert.ok(results[0].evidence.plannedBatches > 1);
  assert.equal(llm.prompts.length, 2);
  assert.ok(results.every(r => r.verdict === 'NOT_EVALUATED' && r.analysisStatus === 'UNAVAILABLE'));
  assert.equal(results[0].evidence.localChecks.typescript.status, 'PASS');
});

test('a unique exact quote corrects a miscounted line while preserving the reported line', () => {
  const files = [{ file: 'src/steps/example.ts', content: '\nawait page.assertReady();\n' }];
  const finding = { file: files[0].file, line: 1, quote: 'await page.assertReady();', severity: 'warning', message: 'Example' };
  const corrected = validateReview(JSON.stringify({ ...clean, findings: [finding] }), files);
  assert.equal(corrected.reviewStatus, 'COMPLETE');
  assert.equal(corrected.findings[0].line, 2);
  assert.equal(corrected.findings[0].reportedLine, 1);
  finding.line = 2;
  assert.equal(validateReview(JSON.stringify({ ...clean, findings: [finding] }), files).status, 'COMPLETE');
});

test('compiler-proven void calls refute a guessed missing await', () => {
  const source = { file: 'src/hooks/hooks.ts', content: 'writeExecutorFile();\n' };
  const finding = { file: source.file, line: 1, quote: 'writeExecutorFile();', severity: 'warning', message: 'La fonction est probablement asynchrone et doit être awaitée.' };
  const checks = { typescript: { status: 'PASS', synchronousCalls: [{ file: source.file, line: 1, quote: finding.quote, returnType: 'void' }] } };
  const review = validateReview(JSON.stringify({ ...clean, findings: [finding] }), [source], checks);
  assert.equal(review.findings.length, 0);
  assert.equal(review.dismissedFindings.length, 1);
  assert.equal(review.status, 'COMPLETE');
});

test('a temporary provider outage retries once and can complete coverage', async t => {
  const root = fixture(t, entries);
  let calls = 0;
  const llm = { chat: async () => ({ message: { content: ++calls === 1 ? 'Service LLM temporairement indisponible.' : JSON.stringify(clean) } }) };
  const results = await verifySources(root, llm, { localChecks, retryDelayMs: 0 });
  assert.ok(results.every(r => r.verdict === 'VALID'));
  assert.equal(results[0].evidence.reviews[0].attempts, 2);
  assert.equal(calls, 2);
});

test('empty driver and compiler-accepted BOM suggestions do not erase completed source coverage', async t => {
  const bomLine = "\uFEFFimport { When, Then } from '@cucumber/cucumber';";
  const root = fixture(t, { ...entries, 'src/core/driver.ts': '', 'src/steps/bom.ts': bomLine });
  const reply = { ...clean, findings: [
    { file: 'src/core/driver.ts', line: 1, quote: '', severity: 'warning', message: 'Le fichier est vide ; si importé il pourrait échouer.' },
    { file: 'src/steps/bom.ts', line: 1, quote: bomLine, severity: 'warning', message: 'Le BOM U+FEFF pourrait poser problème.' },
  ] };
  const results = await verifySources(root, fakeLlm(reply), { localChecks });
  assert.ok(results.every(r => r.verdict === 'VALID' && r.analysisStatus === 'COMPLETE'));
  assert.equal(results[0].evidence.reviewedFiles, results[0].evidence.totalFiles);
  assert.equal(results[0].evidence.reviews[0].dismissedFindings.length, 2);
  assert.equal(results[0].evidence.reviews[0].rejectedFindings.length, 0);
});

test('BOM quotes are checked faithfully even without compiler facts', () => {
  const source = { file: 'src/steps/bom.ts', content: '\uFEFFexport const marker = true;\n' };
  const finding = { file: source.file, line: 1, quote: source.content, severity: 'warning', message: 'BOM present' };
  const review = validateReview(JSON.stringify({ ...clean, findings: [finding] }), [source]);
  assert.deepEqual(review.findings, [finding]);
  assert.deepEqual(review.rejectedFindings, []);
});

test('an unverified step finding needs review without invalidating covered Gherkin or erasing counts', async t => {
  const root = fixture(t, entries);
  const reply = { ...clean, findings: [
    { file: 'src/steps/login.ts', line: 999, quote: 'nonexistent();', severity: 'error', message: 'Unverified defect' },
  ] };
  const results = await verifySources(root, fakeLlm(reply), { localChecks });
  assert.equal(results[0].verdict, 'VALID');
  assert.equal(results[1].verdict, 'NOT_EVALUATED');
  assert.equal(results[1].analysisStatus, 'NEEDS_REVIEW');
  assert.equal(results[0].evidence.reviewedFiles, results[0].evidence.totalFiles);
  assert.equal(results[0].evidence.unresolvedFindings.length, 1);
});

test('an incomplete TS batch does not erase a completed Gherkin assessment', async t => {
  const root = fixture(t, { ...entries, 'src/steps/zlarge.ts': '// long file\n'.repeat(350) });
  const llm = { chat: async messages => {
    const batch = JSON.parse(messages[0].content.split('Fichiers complets de ce lot :\n')[1]);
    const status = batch.some(f => f.file === 'src/steps/zlarge.ts') ? 'INCOMPLETE' : 'COMPLETE';
    return { message: { content: JSON.stringify({ ...clean, status }) } };
  } };
  const results = await verifySources(root, llm, { localChecks, maxChars: 8000 });
  assert.equal(results[0].verdict, 'VALID');
  assert.equal(results[1].verdict, 'NOT_EVALUATED');
  assert.ok(results[0].evidence.plannedBatches > 1);
});

test('malformed JSON and fake empty verdicts never validate sources', async t => {
  const root = fixture(t, entries);
  for (const reply of ['{}', '{"status":"COMPLETE"', 'null', '{"status":"COMPLETE","findings":[]}']) {
    const results = await verifySources(root, fakeLlm(reply), { localChecks });
    assert.ok(results.every(r => r.verdict === 'NOT_EVALUATED' && r.analysisStatus === 'INCOMPLETE'));
  }
});

test('local compiler failures override an approving LLM', async t => {
  const root = fixture(t, entries);
  const checks = { ...localChecks, typescript: { status: 'FAIL', diagnostics: [{ code: 6133, message: 'Unused import' }] } };
  const results = await verifySources(root, fakeLlm(), { localChecks: checks });
  assert.equal(results[1].verdict, 'INVALID');
  assert.equal(results[1].evidence.localChecks.typescript.diagnostics[0].code, 6133);
});

test('local-only never calls the LLM and distinguishes local checks from a complete audit', async t => {
  const root = fixture(t, entries);
  const llm = { chat: () => { throw new Error('Must not be called'); } };
  const results = await verifySources(root, llm, { localOnly: true, localChecks });
  assert.ok(results.every(r => r.analysisStatus === 'SKIPPED' && r.verdict === 'NOT_EVALUATED'));
  assert.equal(results[0].evidence.localChecks.cucumber.status, 'PASS');
});

test('missing source directories remain visible and cannot reduce the category count', async t => {
  const root = fixture(t, {});
  const results = await verifySources(root, fakeLlm(), { localChecks });
  assert.equal(results.length, 2);
  assert.ok(results.every(r => r.verdict === 'NOT_EVALUATED'));
  assert.equal(results[0].evidence.errors[0].file, 'src');
});

test('real framework local checks and complete-source batching work without a provider', { timeout: 120000 }, async t => {
  const root = path.resolve(__dirname, '../../..');
  const results = await verifySources(root, fakeLlm());
  const evidence = results[0].evidence;
  assert.equal(evidence.localChecks.typescript.status, 'PASS', JSON.stringify(evidence.localChecks.typescript));
  assert.ok(evidence.localChecks.typescript.synchronousCalls.some(call => call.quote === 'writeExecutorFile();' && call.returnType === 'void'));
  assert.equal(evidence.localChecks.cucumber.status, 'PASS', JSON.stringify(evidence.localChecks.cucumber));
  assert.ok(evidence.localChecks.cucumber.scenarios > 0);
  assert.deepEqual(evidence.errors, []);
  assert.deepEqual(evidence.omitted, []);
  assert.equal(evidence.reviewedFiles, evidence.totalFiles);
  assert.ok(results.every(r => r.verdict === 'VALID'));
  t.diagnostic(`${results[0].targetFiles} features / ${results[1].targetFiles} steps files / ${evidence.totalFiles} complete sources / ${evidence.plannedBatches} batches`);
  t.diagnostic(evidence.localChecks.cucumber.output.trim());
});
