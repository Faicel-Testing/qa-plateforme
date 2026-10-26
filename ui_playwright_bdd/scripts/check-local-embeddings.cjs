'use strict';
// Real model, synthetic documents only. No Groq call or remote corpus transfer.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const hybrid = require('./agents/shared/hybrid-rag');
const embeddings = require('./agents/shared/embedding-client');
async function main() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-local-embeddings-'));
  try {
    fs.mkdirSync(path.join(root, 'specs'));
    fs.writeFileSync(path.join(root, 'specs/auth.md'), 'An expired access token prevents authentication. The visitor must sign in again.');
    fs.writeFileSync(path.join(root, 'specs/todo.md'), 'Deleting a task permanently removes its entry from the list.');
    fs.writeFileSync(path.join(root, 'specs/style.md'), 'The header has a blue background and rounded buttons.');
    const env = { RAG_MODE: 'hybrid', RAG_RERANK_ENABLED: 'false', CONFLUENCE_RAG_ENABLED: 'false' };
    const provider = embeddings.createClient(embeddings.config(env));
    const cases = [
      ['Pourquoi ma connexion est refusée après expiration de ma session ?', 'specs/auth.md'],
      ['Comment retirer définitivement une activité de ma liste ?', 'specs/todo.md'],
    ];
    const evidence = [];
    for (const [query, expected] of cases) {
      const result = await hybrid.search(root, query, { provider, env, strict: true });
      assert.equal(result.mode, 'hybrid');
      assert.equal(result.semantic.status, 'READY');
      assert.equal(result.semantic.dimension, 384);
      assert.equal(result.hits[0].path, expected);
      evidence.push({ query, topHit: result.hits[0].path, semanticRank: result.hits[0].semanticRank, dimension: result.semantic.dimension });
    }
    const cached = await hybrid.search(root, cases[0][0], { provider, env, strict: true });
    assert.equal(cached.semantic.generated, 0);
    assert.equal(cached.semantic.cacheHits, 3);
    await assert.rejects(provider.embed(['test'], 'query', AbortSignal.abort()), /abort/i);
    const controller = new AbortController();
    const pending = provider.embed(['A document about authentication. '.repeat(200)], 'query', controller.signal);
    const timer = setTimeout(() => controller.abort(), 10);
    await assert.rejects(pending, /stopped/);
    clearTimeout(timer);
    const recovered = await provider.embed(['A new document about authentication.'], 'document');
    assert.equal(recovered[0].length, 384);
    const report = { status: 'PASS', model: embeddings.config(env).model, inference: 'local-cpu-offline', evidence, cacheHits: cached.semantic.cacheHits, cancellationAndRecovery: 'PASS' };
    const logs = path.resolve(__dirname, '../.qa-rag');
    fs.mkdirSync(logs, { recursive: true });
    fs.writeFileSync(path.join(logs, 'local-embedding-check.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
