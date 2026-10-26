'use strict';
const { Pool } = require('pg');
const path = require('node:path');
const { createHash } = require('node:crypto');
const sha = value => createHash('sha256').update(value).digest('hex');
function storage(env = process.env) {
  const value = env.RAG_VECTOR_STORE || 'file';
  if (!['file', 'pgvector'].includes(value)) throw new Error('RAG_VECTOR_STORE must be file or pgvector');
  return value;
}
function config(env = process.env) {
  for (const key of ['RAG_PGDATABASE', 'RAG_PGUSER', 'RAG_PGPASSWORD']) {
    if (!env[key]) throw new Error(`Missing ${key}; run npm run rag:pg:setup`);
  }
  if (['postgres', 'template0', 'template1'].includes(env.RAG_PGDATABASE) || env.RAG_PGDATABASE === env.TEST_DATA_PGDATABASE) throw new Error('Use a dedicated RAG database');
  const port = Number(env.RAG_PGPORT || 5433);
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Invalid RAG_PGPORT');
  const host = env.RAG_PGHOST || '127.0.0.1';
  return { host, port, database: env.RAG_PGDATABASE, user: env.RAG_PGUSER, password: env.RAG_PGPASSWORD,
    ssl: ['127.0.0.1', 'localhost', '::1'].includes(host) ? undefined : { rejectUnauthorized: true },
    max: 2, connectionTimeoutMillis: 5000, statement_timeout: 15000, idleTimeoutMillis: 1000, application_name: 'qa-rag-pgvector' };
}
function create(root, providerKey, identity, env = process.env) {
  const pool = new Pool(config(env));
  const namespace = env.RAG_CORPUS_ID || sha(path.resolve(root));
  const modelKey = sha(providerKey + identity);
  return { namespace, modelKey,
    async load() {
      const result = await pool.query('SELECT chunk_id, text_hash, embedding::text AS embedding, fingerprint FROM qa_rag.chunks WHERE corpus_id=$1 AND model_key=$2', [namespace, modelKey]);
      if (!result.rows.length) return null;
      const vectors = Object.fromEntries(result.rows.map(r => [r.chunk_id, { textHash: r.text_hash, vector: JSON.parse(r.embedding) }]));
      return { version: 1, identity, providerKey, dimension: 384, fingerprint: result.rows[0].fingerprint, vectors };
    },
    async save(index, vectors) {
      const rows = index.chunks.map(chunk => ({ id: chunk.id, path: chunk.path, start: chunk.startLine, end: chunk.endLine,
        text: chunk.text, kind: chunk.kind || 'document', hash: vectors[chunk.id].textHash, embedding: JSON.stringify(vectors[chunk.id].vector) }));
      if (rows.some(r => JSON.parse(r.embedding).length !== 384)) throw new Error('pgvector requires 384-dimensional embeddings');
      const client = await pool.connect();
      try {
        await client.query('BEGIN');
        await client.query('SELECT pg_advisory_xact_lock(hashtextextended($1,0))', [namespace]);
        await client.query('DELETE FROM qa_rag.chunks WHERE corpus_id=$1 AND model_key=$2', [namespace, modelKey]);
        await client.query(`INSERT INTO qa_rag.chunks(corpus_id,model_key,chunk_id,fingerprint,source_path,start_line,end_line,content,source_kind,text_hash,embedding)
          SELECT $1,$2,r.id,$3,r.path,r.start,r.end,r.text,r.kind,r.hash,r.embedding::vector
          FROM jsonb_to_recordset($4::jsonb) AS r(id text,path text,start integer,"end" integer,text text,kind text,hash text,embedding text)`,
        [namespace, modelKey, index.fingerprint, JSON.stringify(rows)]);
        await client.query('COMMIT');
      } catch (error) { await client.query('ROLLBACK'); throw error; }
      finally { client.release(); }
    },
    async search(index, vector, minSimilarity, limit = 40) {
      if (vector.length !== 384 || !vector.every(Number.isFinite)) throw new Error('Invalid pgvector query dimension');
      const snapshot = await pool.query('SELECT count(*)::int AS count FROM qa_rag.chunks WHERE corpus_id=$1 AND model_key=$2 AND fingerprint=$3', [namespace, modelKey, index.fingerprint]);
      if (snapshot.rows[0].count !== index.chunks.length) throw new Error('pgvector snapshot changed; rebuild the corpus index');
      const result = await pool.query(`SELECT chunk_id, text_hash, 1-(embedding <=> $4::vector) AS score
        FROM qa_rag.chunks WHERE corpus_id=$1 AND model_key=$2 AND fingerprint=$3
          AND 1-(embedding <=> $4::vector) >= $5
        ORDER BY embedding <=> $4::vector,chunk_id LIMIT $6`, [namespace, modelKey, index.fingerprint, JSON.stringify(vector), minSimilarity, limit]);
      const current = new Map(index.chunks.map(c => [c.id, c]));
      return result.rows.map(row => {
        const chunk = current.get(row.chunk_id);
        if (!chunk || sha(chunk.text) !== row.text_hash) throw new Error('pgvector evidence differs from current sources');
        return { ...chunk, score: Number(row.score) };
      });
    },
    close: () => pool.end(),
  };
}
async function status(env = process.env) {
  const pool = new Pool(config(env));
  try {
    const extension = await pool.query("SELECT extversion FROM pg_extension WHERE extname='vector'");
    const count = await pool.query('SELECT count(*)::int AS chunks, count(DISTINCT corpus_id)::int AS corpora FROM qa_rag.chunks');
    return { storage: 'pgvector', connected: true, version: extension.rows[0]?.extversion, dimension: 384, ...count.rows[0] };
  } finally { await pool.end(); }
}
module.exports = { storage, config, create, status };
