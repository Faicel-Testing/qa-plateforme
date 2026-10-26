'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { Readable } = require('node:stream');
const { pipeline } = require('node:stream/promises');
const { createHash } = require('node:crypto');
const model = require('./agents/shared/local-embedding-model');
async function main() {
  try { console.log('Embedding artifacts already verified: ' + model.verify()); return; } catch { /* install/repair */ }
  const manifest = { model: model.MODEL, revision: model.REVISION, files: {} };
  for (const file of model.FILES) {
    console.log('[Embeddings] Downloading ' + file);
    const response = await fetch(`https://huggingface.co/${model.MODEL}/resolve/${model.REVISION}/${file}`, { signal: AbortSignal.timeout(900000) });
    if (!response.ok) throw new Error(`Model download failed: HTTP ${response.status}`);
    const destination = path.join(model.DIRECTORY, file);
    fs.mkdirSync(path.dirname(destination), { recursive: true });
    const temporary = destination + '.tmp';
    const digest = createHash('sha256');
    let bytes = 0, last = Date.now();
    const stream = Readable.fromWeb(response.body);
    stream.on('data', chunk => {
      digest.update(chunk); bytes += chunk.length;
      if (bytes > 250000000) stream.destroy(new Error('Model artifact exceeds size limit'));
      if (Date.now() - last > 15000) { console.log(`[Embeddings] ${file}: ${(bytes / 1048576).toFixed(1)} MiB`); last = Date.now(); }
    });
    await pipeline(stream, fs.createWriteStream(temporary));
    manifest.files[file] = digest.digest('hex');
    fs.renameSync(temporary, destination);
    console.log(`[Embeddings] ${file}: complete (${bytes} bytes)`);
  }
  fs.writeFileSync(path.join(model.DIRECTORY, 'manifest.json'), JSON.stringify(manifest, null, 2));
  console.log('Local model ready: ' + model.verify());
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
