'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { randomUUID } = require('node:crypto');
const root = path.resolve(__dirname, '..');
const runtime = require('./agents/shared/pipeline-runtime');
const children = ['chromium', 'firefox'].map(browser => {
  const pointer = JSON.parse(fs.readFileSync(path.join(root, 'logs', `latest-${browser}-run.json`), 'utf8'));
  if (!/^[a-zA-Z0-9_.-]+$/.test(pointer.runId)) throw new Error('Invalid browser run ID');
  const dir = path.join(root, 'allure-runs', pointer.runId, 'results');
  const manifest = JSON.parse(fs.readFileSync(path.join(dir, 'run-manifest.json'), 'utf8'));
  if (manifest.runId !== pointer.runId || manifest.browser !== browser || !manifest.completed) throw new Error(`${browser}: missing or incomplete execution; no combined report created`);
  const data = runtime.readResults(dir);
  if (data.errors.length || data.results.length !== manifest.resultCount || !data.results.length) throw new Error(`${browser}: invalid results`);
  return { dir, manifest };
});
if (children[0].manifest.sourceHash !== children[1].manifest.sourceHash) throw new Error('Browser runs have different source versions; rerun both browsers');
const runId = `multibrowser-${randomUUID()}`;
const target = path.join(root, 'allure-runs', runId, 'results');
fs.mkdirSync(target, { recursive: true });
for (const { dir } of children) for (const file of fs.readdirSync(dir)) {
  if (!/-result\.json$|-container\.json$|-attachment\./.test(file)) continue;
  const source = path.join(dir, file);
  if (!fs.statSync(source).isFile()) continue;
  if (fs.existsSync(path.join(target, file))) throw new Error('Duplicate result or attachment filename');
  if (file.endsWith('-result.json')) {
    const browser = children.find(child => child.dir === dir).manifest.browser;
    const result = require('./agents/shared/browser-result').browserResult(JSON.parse(fs.readFileSync(source, 'utf8')), browser);
    fs.writeFileSync(path.join(target, file), JSON.stringify(result));
  } else fs.copyFileSync(source, path.join(target, file));
}
const manifests = children.map(c => c.manifest);
const manifest = { runId, completed: true, browser: 'multibrowser', sourceHash: manifests[0].sourceHash,
  startedAt: Math.min(...manifests.map(m => m.startedAt)), finishedAt: Math.max(...manifests.map(m => m.finishedAt)),
  exitCode: manifests.every(m => m.exitCode === 0) ? 0 : 1,
  resultCount: manifests.reduce((sum, m) => sum + m.resultCount, 0), childRuns: manifests.map(m => m.runId) };
fs.writeFileSync(path.join(target, 'run-manifest.json'), JSON.stringify(manifest, null, 2));
fs.writeFileSync(path.join(root, 'logs', 'latest-test-run.json'), JSON.stringify({ runId }));
console.log(`Merged only the latest identified browser executions: ${target}`);
console.log('Clear any ALLURE_RESULTS_DIR override, then run npm run allure:generate / allure:open.');
