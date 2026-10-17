'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { createHash, randomUUID } = require('node:crypto');
const rag = require('./rag');
const embeddings = require('./embedding-client');
const reranker = require('./reranker');
const hash = value => createHash('sha256').update(value).digest('hex');
const cooldowns = new Map();
const queries = new Map();

function fuse(lexical, semantic, limit = 40) {
  const combined = new Map();
  for (const [channel, list] of [['lexical', lexical], ['semantic', semantic]]) {
    list.slice(0, limit).forEach((hit, i) => {
      const entry = combined.get(hit.id) || { ...hit, score: 0, lexicalRank: null, semanticRank: null, lexicalScore: null, semanticScore: null };
      entry[channel + 'Rank'] = i + 1;
      entry[channel + 'Score'] = hit.score;
      entry.score += 1 / (60 + i + 1);
      combined.set(hit.id, entry);
    });
  }
  return [...combined.values()].map(hit => ({ ...hit, score: hit.score * (hit.kind === 'ai-history-unverified' ? 0.6 : 1) }))
    .sort((a, b) => b.score - a.score || a.path.localeCompare(b.path) || a.startLine - b.startLine);
}
function cacheFile(root, providerKey, identity) {
  return path.join(root, '.qa-rag', `vectors-${hash(providerKey + identity).slice(0, 24)}.json`);
}
async function vectorsFor(root, index, provider, settings, signal) {
  const identity = await provider.identity(signal);
  const file = cacheFile(root, provider.key, identity);
  let saved;
  try { saved = JSON.parse(fs.readFileSync(file, 'utf8')); } catch { saved = null; }
  if (saved?.version !== 1 || saved.identity !== identity || saved.providerKey !== provider.key) saved = null;
  const vectors = {}, pending = [];
  let dimension = null, cacheHits = 0;
  for (const chunk of index.chunks) {
    const entry = saved?.vectors?.[chunk.id];
    try {
      if (!entry || entry.textHash !== hash(chunk.text)) throw new Error('Not cached');
      const vector = embeddings.normalize(entry.vector, dimension || saved.dimension);
      dimension = vector.length; vectors[chunk.id] = { textHash: entry.textHash, vector }; cacheHits++;
    } catch { pending.push(chunk); }
  }
  for (let offset = 0; offset < pending.length; offset += settings.batchSize) {
    const batch = pending.slice(offset, offset + settings.batchSize);
    const values = await provider.embed(batch.map(c => c.text), 'document', signal);
    if (!Array.isArray(values) || values.length !== batch.length) throw new Error('Incomplete embedding batch');
    batch.forEach((chunk, i) => {
      const vector = embeddings.normalize(values[i], dimension);
      dimension = vector.length; vectors[chunk.id] = { textHash: hash(chunk.text), vector };
    });
  }
  if (rag.currentIndex(root).fingerprint !== index.fingerprint) throw new Error('Sources changed during embedding; retry retrieval');
  if (pending.length || !saved || saved.fingerprint !== index.fingerprint) {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    const temporary = file + '.' + randomUUID() + '.tmp';
    fs.writeFileSync(temporary, JSON.stringify({ version: 1, providerKey: provider.key, identity,
      fingerprint: index.fingerprint, dimension, vectors }));
    fs.renameSync(temporary, file);
  }
  return { vectors, identity, dimension, cacheHits, generated: pending.length, file };
}
async function search(root, query, options = {}) {
  await require('./confluence-rag').ensureFresh(root, options.env || process.env);
  const settings = embeddings.config(options.env);
  const index = rag.currentIndex(root);
  const lexical = rag.lexicalRank(index, query);
  const limits = { topK: options.topK ?? 4, maxChars: options.maxChars ?? 4500 };
  rag.selectHits(index, lexical, limits); // Validate limits before any network call.
  async function finish(snapshot, ranked, metadata) {
    const result = await reranker.rerank(query, ranked, { env: { ...(options.env || process.env), ...(options.strict ? { RAG_RERANK_STRICT: 'true' } : {}) }, scorer: options.rerankScorer, topK: limits.topK });
    if (result.reranking.status !== 'DISABLED' && rag.currentIndex(root).fingerprint !== snapshot.fingerprint) throw new Error('Sources changed during reranking; retry retrieval');
    return { ...rag.selectHits(snapshot, result.ranked, limits), ...metadata, reranking: result.reranking };
  }
  if (settings.mode === 'bm25' || !index.chunks.length || !String(query).trim()) {
    return finish(index, lexical, { mode: 'bm25', requestedMode: settings.mode, semantic: { status: settings.mode === 'bm25' ? 'DISABLED' : 'EMPTY' } });
  }
  const provider = options.provider || embeddings.createClient(settings);
  try {
    if (!options.strict && (cooldowns.get(provider.key) || 0) > Date.now()) throw new Error('Embedding service cooling down after failure');
    const signal = AbortSignal.timeout(options.indexing ? 120000 : settings.timeoutMs);
    const data = await vectorsFor(root, index, provider, settings, signal);
    // Bound model input explicitly; no silent provider truncation.
    const sanitizedQuery = rag.redact(String(query));
    const queryText = sanitizedQuery.slice(0, 4000);
    const queryKey = hash(provider.key + data.identity + queryText);
    let vector = queries.get(queryKey);
    if (!vector) {
      const values = await provider.embed([queryText], 'query', signal);
      if (!Array.isArray(values) || values.length !== 1) throw new Error('Missing query embedding');
      vector = embeddings.normalize(values[0], data.dimension);
      queries.set(queryKey, vector);
      if (queries.size > 64) queries.delete(queries.keys().next().value);
    }
    vector = embeddings.normalize(vector, data.dimension);
    if (rag.currentIndex(root).fingerprint !== index.fingerprint) throw new Error('Sources changed during query embedding');
    const semantic = index.chunks.map(chunk => ({ ...chunk,
      score: data.vectors[chunk.id].vector.reduce((sum, value, i) => sum + value * vector[i], 0),
    })).filter(hit => hit.score >= settings.minSimilarity).sort((a, b) => b.score - a.score || a.id.localeCompare(b.id));
    cooldowns.delete(provider.key);
    return finish(index, fuse(lexical, semantic), { mode: 'hybrid', requestedMode: settings.mode,
      semantic: { status: 'READY', model: settings.model, identity: data.identity, dimension: data.dimension,
        matched: semantic.length, cacheHits: data.cacheHits, generated: data.generated, queryTruncated: sanitizedQuery.length > 4000 } });
  } catch (error) {
    cooldowns.set(provider.key, Date.now() + 15000);
    if (options.strict) throw error;
    // Refresh lexical evidence too if files changed during embedding requests.
    if (require('./ai-gateway').isGatewayError(error)) throw error;
    const fresh = rag.currentIndex(root);
    return finish(fresh, rag.lexicalRank(fresh, query), { mode: 'bm25-fallback', requestedMode: 'hybrid',
      semantic: { status: 'UNAVAILABLE', reason: error.message } });
  }
}
async function buildIndex(root, options = {}) {
  await require('./confluence-rag').ensureFresh(root, options.env || process.env);
  const index = rag.buildIndex(root), settings = embeddings.config(options.env);
  if (settings.mode === 'bm25' || !index.chunks.length) return { index, mode: 'bm25' };
  const provider = options.provider || embeddings.createClient(settings);
  const data = await vectorsFor(root, index, provider, settings, AbortSignal.timeout(120000));
  return { index, mode: 'hybrid', model: settings.model, dimension: data.dimension, cacheHits: data.cacheHits, generated: data.generated };
}
async function augmentMessages(messages, { root, agent, env = process.env, provider, logger = console, maxChars = 4500 } = {}) {
  if (env.RAG_ENABLED === 'false' || !rag.ELIGIBLE.has(agent)
    || messages.some(m => typeof m.content === 'string' && m.content.startsWith(rag.MARKER))) return messages;
  const query = messages.filter(m => m.role === 'user' && typeof m.content === 'string').map(m => m.content).join('\n');
  const result = await search(root, query, { env, provider, maxChars });
  logger.log(`[RAG] ${result.mode}: ${result.hits.length} extrait(s)${result.semantic.reason ? ' — ' + result.semantic.reason : ''}`);
  logger.log(`[RERANK] ${result.reranking.status}${result.reranking.model ? ': ' + result.reranking.model : ''}`);
  return rag.withContext(messages, result);
}
module.exports = { search, buildIndex, augmentMessages, fuse, vectorsFor, cacheFile };
