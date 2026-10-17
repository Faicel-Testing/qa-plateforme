'use strict';
const fs = require('fs');
const path = require('path');
const { EventEmitter } = require('events');
const { readResults } = require('./pipeline-runtime');

// Replay recorded formatter events only: no hooks, steps, browser or network execution.
async function recoverAllure(dir) {
  if (readResults(dir).results.length) return 0;
  const journal = path.join(dir, 'cucumber-messages.ndjson');
  if (!fs.existsSync(journal)) throw new Error(`No Allure results or Cucumber journal in ${dir}`);
  const envelopes = fs.readFileSync(journal, 'utf8').split(/\r?\n/).filter(Boolean).map(line => JSON.parse(line));
  if (!envelopes.some(e => e.testRunFinished)) throw new Error('Cannot recover automatically: Cucumber journal incomplete');
  const before = new Map(), after = new Map();
  const hooks = new Map(envelopes.filter(e => e.hook).map(e => [e.hook.id, e.hook]));
  for (const { testCase } of envelopes) {
    if (!testCase) continue;
    let seenStep = false;
    for (const step of testCase.testSteps) {
      if (step.pickleStepId) seenStep = true;
      if (step.hookId) (seenStep ? after : before).set(step.hookId, {
        id: step.hookId, name: hooks.get(step.hookId)?.name || (seenStep ? 'After' : 'Before'),
      });
    }
  }
  const Reporter = require('allure-cucumberjs/reporter');
  const broadcaster = new EventEmitter();
  const reporter = new Reporter({
    eventBroadcaster: broadcaster, parsedArgvOptions: { resultsDir: dir },
    supportCodeLibrary: { beforeTestCaseHookDefinitions: [...before.values()], afterTestCaseHookDefinitions: [...after.values()] },
    log() {}, cleanup: async () => {},
  });
  for (const envelope of envelopes) broadcaster.emit('envelope', envelope);
  await reporter.finished();
  const count = readResults(dir).results.length;
  const expected = envelopes.filter(e => e.testCaseFinished).length;
  if (!count || count !== expected) throw new Error(`Recovered ${count}/${expected} results; inspect the journal`);
  const manifestPath = path.join(dir, 'run-manifest.json');
  if (fs.existsSync(manifestPath)) {
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
    manifest.resultCount = count;
    manifest.recoveredFrom = 'cucumber-messages.ndjson';
    manifest.recoveredAt = new Date().toISOString();
    fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
  }
  return count;
}
module.exports = { recoverAllure };
