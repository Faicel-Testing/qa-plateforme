-- Run as the dedicated qa_rag owner after an administrator enables vector.
CREATE SCHEMA IF NOT EXISTS qa_rag;
CREATE TABLE IF NOT EXISTS qa_rag.chunks (
  corpus_id text NOT NULL,
  model_key text NOT NULL,
  chunk_id text NOT NULL,
  fingerprint text NOT NULL,
  source_path text NOT NULL,
  start_line integer NOT NULL,
  end_line integer NOT NULL,
  content text NOT NULL,
  source_kind text NOT NULL,
  text_hash text NOT NULL,
  embedding vector(384) NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(corpus_id, model_key, chunk_id)
);
CREATE INDEX IF NOT EXISTS qa_rag_chunks_scope ON qa_rag.chunks(corpus_id,model_key,fingerprint);
-- Exact cosine search initially: deterministic recall for the current small corpus.
-- Add an approximate HNSW index only after measuring recall with scope filters.
