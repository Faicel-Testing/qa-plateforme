'use strict';
// Opt-in preload: capture the real messages after RAG augmentation, including cache hits.
// Does not change llm.js or persist authentication headers. Files stay under ignored logs/.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '..');
const cb = require('./agents/shared/circuit-breaker');
const original = cb.execute;
const agent = path.basename(process.argv[1] || 'unknown', '.js');
const directory = path.join(root, 'logs/deepeval', 'capture-' + Date.now() + '-' + crypto.randomUUID().slice(0, 8));
const cases = [];
cb.execute = async function (fn, messages, fnName, variant) {
  const snapshot = JSON.parse(JSON.stringify(messages));
  const result = await original.call(this, fn, messages, fnName, variant);
  if (!result.fallback) {
    let response;
    try { response = JSON.parse(result.value); } catch { return result; }
    const output = response?.message?.content;
    const userMessages = snapshot.filter(m => m.role === 'user' && typeof m.content === 'string');
    if (typeof output === 'string' && output.trim() && userMessages.length) {
      cases.push({ id: agent + '-' + (cases.length + 1), agent, operation: fnName, status: 'READY',
        input: userMessages.map(m => m.content).join('\n\n'), actual_output: output,
        retrieval_context: snapshot.filter(m => m.role !== 'assistant' && typeof m.content === 'string' && m.content.trim()).map(m => m.content),
        messages: snapshot, fromCache: Boolean(result.fromCache), capturedAt: new Date().toISOString(),
        contextScope: 'Exact non-assistant messages: task instructions, supplied evidence and any RAG excerpts. Prior assistant claims excluded as evidence.' });
      fs.mkdirSync(directory, { recursive: true });
      fs.writeFileSync(path.join(directory, 'samples.json'), JSON.stringify({ schemaVersion: 1, datasetReviewStatus: 'DRAFT',
        captureScope: 'Individual LLM answers used by agent; not validation of final aggregated decisions.', cases }, null, 2));
      console.log('[DeepEval capture] ' + path.join(directory, 'samples.json'));
    }
  }
  return result;
};
