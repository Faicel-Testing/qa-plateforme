'use strict';
const { fork } = require('node:child_process');
const path = require('node:path');
const local = require('./local-embedding-model');
const engines = new Map();

function number(value, fallback, min, max, integer = false) {
  const n = value === undefined ? fallback : Number(value);
  if (!Number.isFinite(n) || n < min || n > max || integer && !Number.isInteger(n)) throw new Error('Invalid embedding configuration');
  return n;
}
function config(env = process.env) {
  const mode = env.RAG_MODE || 'bm25';
  if (!['hybrid', 'bm25'].includes(mode)) throw new Error('RAG_MODE must be hybrid or bm25');
  const model = env.RAG_EMBEDDING_MODEL || local.MODEL;
  const endpoint = (env.RAG_EMBEDDING_HOST || 'https://embeddings-not-configured.invalid').replace(/\/$/, '');
  const url = new URL(endpoint);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) throw new Error('Invalid embedding endpoint');
  return { mode, model, endpoint, timeoutMs: number(env.RAG_EMBEDDING_TIMEOUT_MS, 30000, 100, 120000, true),
    minSimilarity: number(env.RAG_MIN_SIMILARITY, 0.35, -1, 1),
    batchSize: number(env.RAG_EMBEDDING_BATCH_SIZE, 8, 1, 32, true),
    queryPrefix: env.RAG_QUERY_PREFIX ?? 'query: ',
    documentPrefix: env.RAG_DOCUMENT_PREFIX ?? 'passage: ',
  };
}
function normalize(vector, dimension) {
  if (!Array.isArray(vector) || !vector.length || vector.length > 16384 || dimension && vector.length !== dimension
    || !vector.every(n => typeof n === 'number' && Number.isFinite(n))) throw new Error('Invalid embedding vector or dimension');
  const norm = Math.hypot(...vector);
  if (!Number.isFinite(norm) || norm === 0) throw new Error('Invalid zero embedding');
  return vector.map(n => n / norm);
}
function createClient(settings = config()) {
  if (settings.model !== local.MODEL) throw new Error('Unsupported local embedding model');
  const key = `local-onnx:${settings.model}:${settings.queryPrefix}:${settings.documentPrefix}:windows400-v1`;
  let identity;
  async function identify(signal) {
    signal?.throwIfAborted();
    identity ||= local.verify();
    return identity;
  }
  return { key, identity: identify, async embed(texts, type, signal) {
    if (!['query', 'document'].includes(type) || !Array.isArray(texts) || !texts.length || texts.length > 32
      || texts.some(t => typeof t !== 'string' || !t.trim() || t.length > 16000)) throw new Error('Invalid local embedding input');
    await identify(signal);
    signal ||= AbortSignal.timeout(settings.timeoutMs);
    signal.throwIfAborted();
    let engine = engines.get(key);
    if (!engine) {
      const worker = fork(path.join(__dirname, 'embedding-worker.cjs'), [], { windowsHide: true, stdio: ['ignore', 'ignore', 'inherit', 'ipc'], execArgv: [] });
      engine = { worker, pending: new Map(), id: 0 };
      engines.set(key, engine);
      const fail = error => {
        if (engines.get(key) === engine) engines.delete(key);
        for (const pending of engine.pending.values()) pending.reject(error);
        engine.pending.clear();
      };
      worker.on('error', fail);
      worker.on('exit', () => fail(new Error('Local embedding worker stopped')));
      worker.on('message', result => {
        const pending = engine.pending.get(result.id);
        if (!pending) return;
        engine.pending.delete(result.id);
        if (!engine.pending.size) { worker.unref(); worker.channel?.unref(); }
        if (result.error) pending.reject(new Error(result.error)); else pending.resolve(result.vectors);
      });
      worker.unref();
      worker.channel?.unref();
    }
    return new Promise((resolve, reject) => {
      const id = ++engine.id;
      const abort = () => { engine.worker.kill(); };
      const cleanup = () => signal.removeEventListener('abort', abort);
      engine.pending.set(id, { resolve: values => {
        cleanup();
        try { resolve(values.map(v => normalize(v))); } catch (error) { reject(error); }
      },
        reject: error => { cleanup(); reject(error); } });
      signal.addEventListener('abort', abort, { once: true });
      engine.worker.ref();
      engine.worker.channel?.ref();
      const prefix = type === 'query' ? settings.queryPrefix : settings.documentPrefix;
      const privacy = require('./payload-privacy');
      engine.worker.send({ id, texts: texts.map(t => prefix + privacy.cleanText(t)) });
    });
  } };
}
module.exports = { config, normalize, createClient };
