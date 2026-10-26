-- Connect to qa_rag as qa_rag in pgAdmin or DBeaver. Read-only inspection.
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
SELECT current_database(), current_user;
SELECT corpus_id, count(*) AS passages, min(vector_dims(embedding)) AS dimensions
FROM qa_rag.chunks GROUP BY corpus_id;
SELECT source_path, start_line, end_line, source_kind, updated_at
FROM qa_rag.chunks ORDER BY source_path, start_line LIMIT 30;
-- Cosine nearest neighbours of one stored passage. For a question, the framework
-- generates its embedding locally and binds the vector as a SQL parameter.
WITH question AS (SELECT embedding FROM qa_rag.chunks LIMIT 1)
SELECT c.source_path, c.start_line, 1 - (c.embedding <=> q.embedding) AS similarity
FROM qa_rag.chunks c CROSS JOIN question q
ORDER BY c.embedding <=> q.embedding LIMIT 5;
