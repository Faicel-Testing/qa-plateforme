'use strict';
// Historical entry point retained for npm run rag:check; BM25 requires no embedding server.
require('dotenv').config({ quiet: true });
const path = require('node:path');
const rag = require('./agents/shared/rag');
const embeddings = require('./agents/shared/embedding-client');
const root = path.resolve(__dirname, '..');
if (embeddings.config().mode !== 'bm25') throw new Error('Groq-only retrieval requires RAG_MODE=bm25');
const result = rag.search(root, 'todo');
console.log(JSON.stringify({ mode: 'bm25', sources: result.hits.length, embeddingServiceRequired: false }));
if (!result.hits.length) process.exitCode = 1;
