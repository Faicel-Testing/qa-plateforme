'use strict';
require('dotenv').config({ quiet: true });
const fs = require('node:fs');
const path = require('node:path');
const { rerank } = require('./agents/shared/reranker');
async function main() {
  if (!process.argv.includes('--live')) throw Error('Use --live to run one Groq call on synthetic, non-project evidence');
  const result = await rerank('How do I reset a forgotten password?', [
    { id: 'unrelated', path: 'synthetic/colors.txt', kind: 'test-source', text: 'The dashboard background is blue.', score: 2 },
    { id: 'relevant', path: 'synthetic/password.txt', kind: 'test-source', text: 'To reset a forgotten password, use Forgot password on the login screen and follow the email link.', score: 1 },
  ], { env: { ...process.env, RAG_RERANK_ENABLED: 'true', RAG_RERANK_STRICT: 'true' } });
  if (result.reranking.status !== 'READY' || result.ranked[0].id !== 'relevant') throw Error('Unexpected ranking');
  const report = { status: 'PASS', scope: 'Synthetic connectivity/ranking smoke test; not a business quality benchmark',
    at: new Date().toISOString(), taskId: process.env.QA_METRICS_TASK_ID || null, reranking: result.reranking,
    order: result.ranked.map(h => ({ id: h.id, score: h.rerankScore })) };
  const file = path.join(__dirname, '../logs/reranker/smoke.json');
  fs.mkdirSync(path.dirname(file), { recursive: true }); fs.writeFileSync(file, JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
}
if (require.main === module) main().catch(error => { console.error(error.code || error.cause?.code || 'Reranker smoke failed'); process.exitCode = 1; });
module.exports = { main };
