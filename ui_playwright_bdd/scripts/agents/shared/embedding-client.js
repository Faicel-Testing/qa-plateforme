'use strict';

function number(value, fallback, min, max, integer = false) {
  const n = value === undefined ? fallback : Number(value);
  if (!Number.isFinite(n) || n < min || n > max || integer && !Number.isInteger(n)) throw new Error('Invalid embedding configuration');
  return n;
}
function config(env = process.env) {
  const mode = env.RAG_MODE || 'bm25';
  if (!['hybrid', 'bm25'].includes(mode)) throw new Error('RAG_MODE must be hybrid or bm25');
  const model = env.RAG_EMBEDDING_MODEL || '';
  const endpoint = (env.RAG_EMBEDDING_HOST || 'https://embeddings-not-configured.invalid').replace(/\/$/, '');
  const url = new URL(endpoint);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) throw new Error('Invalid embedding endpoint');
  return { mode, model, endpoint, timeoutMs: number(env.RAG_EMBEDDING_TIMEOUT_MS, 30000, 100, 120000, true),
    minSimilarity: number(env.RAG_MIN_SIMILARITY, 0.35, -1, 1),
    batchSize: number(env.RAG_EMBEDDING_BATCH_SIZE, 8, 1, 32, true),
    queryPrefix: env.RAG_QUERY_PREFIX ?? (model.startsWith('embeddinggemma') ? 'task: search result | query: ' : ''),
    documentPrefix: env.RAG_DOCUMENT_PREFIX ?? (model.startsWith('embeddinggemma') ? 'title: none | text: ' : ''),
  };
}
function normalize(vector, dimension) {
  if (!Array.isArray(vector) || !vector.length || vector.length > 16384 || dimension && vector.length !== dimension
    || !vector.every(n => typeof n === 'number' && Number.isFinite(n))) throw new Error('Invalid embedding vector or dimension');
  const norm = Math.hypot(...vector);
  if (!Number.isFinite(norm) || norm === 0) throw new Error('Invalid zero embedding');
  return vector.map(n => n / norm);
}
function createClient() {
  throw new Error('Embeddings are not configured: Groq-only retrieval uses RAG_MODE=bm25');
}
module.exports = { config, normalize, createClient };
