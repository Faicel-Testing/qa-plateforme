'use strict';
// Inspect a run locally without calling a model or changing its analysis report.
const fs = require('node:fs');
const path = require('node:path');
const { sourceBundle } = require('./agents/shared/analysis-evidence');
const { readResults } = require('./agents/shared/pipeline-runtime');
const root = path.resolve(__dirname, '..');
const runId = process.argv[2];
if (!runId || !/^[A-Za-z0-9_-]+$/.test(runId)) throw new Error('Provide one run ID');
const directory = path.join(root, 'allure-runs', runId, 'results');
const manifest = JSON.parse(fs.readFileSync(path.join(directory, 'run-manifest.json'), 'utf8'));
if (manifest.runId !== runId) throw new Error('Run identity mismatch');
const results = readResults(directory);
if (results.errors.length) throw new Error('Unreadable run evidence');
const summary = results.results.filter(r => ['failed', 'broken'].includes(r.status)).map(failure => {
  const bundle = sourceBundle(root, failure, { directory, runId });
  const observed = String(failure.statusDetails?.message || '') + '\n' + String(failure.statusDetails?.trace || '');
  return { test: failure.name, sourceFiles: bundle.reads.map(([file]) => file),
    recordedApiStatus: bundle.recorded_api.status, recordedTargets: bundle.recorded_api.targets || [],
    recordedErrorCode: observed.match(/\b(?:ECONNRESET|ECONNREFUSED|ENOTFOUND|ETIMEDOUT)\b/)?.[0] || null,
    timedOut: /timed out|timeout/i.test(observed),
    currentSourceIsHistoricalProof: false };
});
fs.writeFileSync(path.join(directory, 'bug-context-summary.json'), JSON.stringify({ runId, modelCalled: false, summary }, null, 2));
console.log(JSON.stringify({ runId, modelCalled: false, summary }, null, 2));
