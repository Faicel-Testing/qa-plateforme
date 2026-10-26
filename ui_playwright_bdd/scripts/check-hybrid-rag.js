'use strict';
require('dotenv').config({ quiet: true });
const path = require('node:path');
const hybrid = require('./agents/shared/hybrid-rag');
async function main() {
  const result = await hybrid.search(path.resolve(__dirname, '..'), 'Comment retirer une tâche de la liste ?', {
    strict: true, env: { ...process.env, RAG_RERANK_ENABLED: 'false', CONFLUENCE_RAG_ENABLED: 'false' },
  });
  console.log(JSON.stringify({ mode: result.mode, semantic: result.semantic, hits: result.hits.map(h => ({ path: h.path, semanticRank: h.semanticRank })) }, null, 2));
  if (!result.hits.length || result.mode === 'hybrid' && result.semantic.status !== 'READY') throw new Error('Retrieval check failed');
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
