'use strict';
const path = require('node:path');
const model = require('./local-embedding-model');
let extractor;
async function load() {
  if (!extractor) extractor = (async () => {
    const { pipeline, env } = await import('@huggingface/transformers');
    env.allowRemoteModels = false;
    env.allowLocalModels = true;
    env.localModelPath = path.resolve(model.DIRECTORY, '../..') + path.sep;
    env.backends.onnx.wasm.numThreads = 2;
    // Inference never downloads files or sends inputs to a network service.
    globalThis.fetch = async () => { throw new Error('Embedding worker network is disabled'); };
    return pipeline('feature-extraction', model.MODEL, { dtype: 'q8', device: 'cpu', local_files_only: true,
      session_options: { intraOpNumThreads: 2, interOpNumThreads: 1 } });
  })();
  return extractor;
}
let queue = Promise.resolve();
process.on('disconnect', () => process.exit(0));
process.on('message', request => {
  queue = queue.then(async () => {
    try {
      const pipe = await load();
      const vectors = [];
      for (const text of request.texts) {
        // Average complete token windows instead of silently truncating long passages.
        const ids = pipe.tokenizer.encode(text);
        const windows = [];
        for (let i = 0; i < ids.length; i += 400) {
          const piece = pipe.tokenizer.decode(ids.slice(i, i + 400), { skip_special_tokens: true });
          const result = await pipe(piece, { pooling: 'mean', normalize: true, truncation: false });
          windows.push(result.tolist()[0]);
        }
        vectors.push(windows[0].map((_, j) => windows.reduce((sum, v) => sum + v[j], 0) / windows.length));
      }
      process.send({ id: request.id, vectors });
    } catch (error) { process.send({ id: request.id, error: error.message }); }
  });
});
