'use strict';
const path = require('node:path');
const fs = require('node:fs');
const { createHash } = require('node:crypto');
const MODEL = 'Xenova/multilingual-e5-small';
const REVISION = '761b726dd34fb83930e26aab4e9ac3899aa1fa78';
const FILES = ['config.json', 'tokenizer.json', 'tokenizer_config.json', 'special_tokens_map.json', 'onnx/model_quantized.onnx'];
const DIRECTORY = path.resolve(__dirname, '../../../.qa-rag/local-models', MODEL);
const hash = data => createHash('sha256').update(data).digest('hex');
function verify() {
  let manifest;
  try { manifest = JSON.parse(fs.readFileSync(path.join(DIRECTORY, 'manifest.json'), 'utf8')); }
  catch { throw new Error('Local embedding model missing; run npm run rag:setup'); }
  if (manifest.model !== MODEL || manifest.revision !== REVISION) throw new Error('Unexpected local embedding model revision');
  for (const file of FILES) {
    const bytes = fs.readFileSync(path.join(DIRECTORY, file));
    if (hash(bytes) !== manifest.files[file]) throw new Error('Local embedding artifact checksum mismatch: ' + file);
  }
  return `${MODEL}@${REVISION}:q8:${hash(JSON.stringify(manifest.files))}`;
}
module.exports = { MODEL, REVISION, FILES, DIRECTORY, hash, verify };
