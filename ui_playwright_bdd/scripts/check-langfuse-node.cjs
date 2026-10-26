'use strict';
// Installation proof: real retrieval, simulated provider, no paid model call.
const path = require('node:path');
require('dotenv').config({ quiet: true });
const observations = require('./agents/shared/langfuse-observability');
async function main() {
  console.log = (...values) => console.error(...values);
  const result = await observations.span('installation.node', { 'qa.operation': 'installation-check' }, async () => {
    const coverage = await require('./python-bridge.cjs').dispatch({ operation: 'coverage', agent: 'quality' });
    const retrieval = await require('./agents/shared/hybrid-rag').search(path.resolve(__dirname, '..'),
      'Comment retirer une tâche de la liste ?', { strict: true, env: { ...process.env, RAG_RERANK_ENABLED: 'false' } });
    const simulated = require('./agents/shared/task-metrics').meteredFetch('groq', async () =>
      Response.json({ model: 'openai/gpt-oss-20b', usage: { prompt_tokens: 3, completion_tokens: 2 }, choices: [{ message: { content: 'OK' } }] }),
    { emit: () => {}, simulated: true });
    const guarded = require('./agents/shared/ai-gateway').gatewayFetch('groq', simulated);
    await observations.span('installation.simulated-provider', { 'qa.operation': 'simulation', 'qa.simulated': true }, () => guarded('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST', body: JSON.stringify({ model: 'openai/gpt-oss-20b', messages: [{ role: 'user', content: 'Synthetic installation check' }], max_completion_tokens: 8 }),
    }));
    return { traceId: observations.traceId(), storage: retrieval.semantic.storage,
      semanticStatus: retrieval.semantic.status, hits: retrieval.hits.length, features: coverage.length, simulatedProvider: true };
  });
  await observations.flush();
  process.stdout.write(JSON.stringify(result));
}
main().catch(async () => { await observations.flush(); process.stderr.write('LANGFUSE_NODE_CHECK_FAILED\n'); process.exitCode = 1; });
