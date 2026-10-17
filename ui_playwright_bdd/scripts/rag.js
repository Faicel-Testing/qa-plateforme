'use strict';
const path = require('node:path');
const rag = require('./agents/shared/rag');
const hybrid = require('./agents/shared/hybrid-rag');
const embeddings = require('./agents/shared/embedding-client');
require('dotenv').config();
const root = path.join(__dirname, '..');
async function main(args = process.argv.slice(2)) {
  const [command, ...query] = args;
  if (command === 'index') {
    const { index, ...semantic } = await hybrid.buildIndex(root);
    console.log(JSON.stringify({ ...semantic, sources: index.sources.length, chunks: index.chunks.length, skipped: index.skipped, omittedLines: index.omittedLines, file: rag.indexPath(root) }, null, 2));
  } else if (command === 'search' && query.length) {
    const strict = query.includes('--strict');
    console.log(JSON.stringify(await hybrid.search(root, query.filter(q => q !== '--strict').join(' '), { strict }), null, 2));
  }
  else if (command === 'status') {
    const index = rag.currentIndex(root);
    const settings = embeddings.config();
    let semantic = { status: 'DISABLED' };
    if (settings.mode === 'hybrid') {
      try { semantic = { status: 'AVAILABLE', identity: await embeddings.createClient(settings).identity() }; }
      catch (error) { semantic = { status: 'UNAVAILABLE', reason: error.message }; }
    }
    console.log(JSON.stringify({ mode: settings.mode, model: settings.model, semantic, reranking: require('./agents/shared/reranker').config(), sources: index.sources.length, chunks: index.chunks.length, fingerprint: index.fingerprint, skipped: index.skipped, omittedLines: index.omittedLines }, null, 2));
  } else throw new Error('Usage: node scripts/rag.js index | status | search <question> [--strict]');
}
if (require.main === module) main().catch(error => { console.error(error.message); process.exitCode = 1; });
module.exports = { main };
