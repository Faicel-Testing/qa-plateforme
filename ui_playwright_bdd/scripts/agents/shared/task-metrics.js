'use strict';
// Transport-level measurements: each SDK retry is a separate HTTP attempt.
const fs = require('node:fs');
const path = require('node:path');
const { randomUUID } = require('node:crypto');
const { performance } = require('node:perf_hooks');
const ROOT = path.resolve(__dirname, '../../..');
const DEFAULT_FILE = path.join(ROOT, 'logs/metrics/events.jsonl');
const count = n => Number.isSafeInteger(n) && n >= 0 ? n : null;
let warned = false;
function write(event, env = process.env) {
  if (env.QA_METRICS_DISABLED === 'true') return;
  if (process.env.NODE_TEST_CONTEXT && !env.QA_METRICS_FILE) return;
  try {
    const file = env.QA_METRICS_FILE || DEFAULT_FILE;
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.appendFileSync(file, JSON.stringify({ version: 1, ts: new Date().toISOString(), ...event }) + '\n');
  } catch { if (!warned) { console.error('[Metrics] Journal indisponible : mesures incomplètes.'); warned = true; } }
}
function usage(data, provider, kind) {
  if (provider === 'groq') {
    const u = data?.usage || data?.x_groq?.usage;
    return { inputTokens: count(u?.prompt_tokens), outputTokens: count(u?.completion_tokens),
      cachedInputTokens: u?.prompt_tokens_details?.cached_tokens === undefined ? null : count(u.prompt_tokens_details.cached_tokens) };
  }
  return { inputTokens: count(data?.prompt_eval_count), outputTokens: kind === 'embedding' ? 0 : count(data?.eval_count),
    cachedInputTokens: count(data?.prompt_eval_cached_count) };
}
function prices(env = process.env) {
  try { return JSON.parse(fs.readFileSync(env.QA_METRICS_PRICING_FILE || path.join(ROOT, 'config/ai-pricing.json'), 'utf8')); }
  catch { return { models: {} }; }
}
function cost(meta, tokens, catalog = prices()) {
  if (meta.provider === 'ollama' && meta.local && !meta.model?.includes('cloud'))
    return { usd: 0, status: 'LOCAL_API_ONLY', note: 'Infrastructure, énergie et matériel non chiffrés' };
  const rate = catalog.models?.[`${meta.provider}/${meta.model}`];
  if (!rate || tokens.inputTokens === null || tokens.outputTokens === null)
    return { usd: null, status: 'UNKNOWN' };
  if (![rate.input, rate.output].every(n => typeof n === 'number' && Number.isFinite(n) && n >= 0))
    return { usd: null, status: 'UNKNOWN' };
  if (meta.serviceTier && !['auto', 'on_demand'].includes(meta.serviceTier)) return { usd: null, status: 'UNKNOWN_TIER' };
  const cached = tokens.cachedInputTokens;
  if (cached !== null && cached > tokens.inputTokens) return { usd: null, status: 'UNKNOWN' };
  const discountKnown = cached !== null && Number.isFinite(rate.cachedInput) && rate.cachedInput >= 0;
  const usd = ((tokens.inputTokens - (discountKnown ? cached : 0)) * rate.input
    + (discountKnown ? cached * rate.cachedInput : 0) + tokens.outputTokens * rate.output) / 1e6;
  return { usd, status: 'ESTIMATED_LIST_PRICE', cachedDiscountApplied: discountKnown,
    rate: { ...rate }, currency: 'USD', checkedAt: catalog.checkedAt, source: catalog.source };
}
function startTask(label, env = process.env) {
  const task = { taskId: randomUUID(), parentTaskId: env.QA_METRICS_TASK_ID || null, label, started: performance.now() };
  write({ type: 'task_start', taskId: task.taskId, parentTaskId: task.parentTaskId, label }, env);
  return task;
}
function endTask(task, result, env = process.env) {
  write({ type: 'task_end', taskId: task.taskId, durationMs: performance.now() - task.started,
    success: result.success, exitCode: result.exitCode, timedOut: !!result.timedOut }, env);
}
function meteredFetch(provider, fetcher = globalThis.fetch, options = {}) {
  return async (url, init = {}) => {
    let request;
    try { request = JSON.parse(init.body); } catch { return fetcher(url, init); }
    if (!request?.model) return fetcher(url, init);
    const address = new URL(typeof url === 'string' ? url : url.url || String(url));
    const kind = /\/(embed|embeddings)$/.test(address.pathname) ? 'embedding' : ['evaluation', 'reranking'].includes(options.kind) ? options.kind : 'generation';
    const env = options.env || process.env;
    // Unit-test provider doubles never enter the production ledger.
    const emit = options.emit || (event => { if (env.QA_METRICS_TASK_ID || !process.env.NODE_TEST_CONTEXT) write(event, env); });
    const meta = { provider, kind, model: request.model, serviceTier: request.service_tier || 'on_demand',
      local: ['localhost', '127.0.0.1', '[::1]'].includes(address.hostname),
      agent: path.basename(process.argv[1] || 'unknown', '.js'), taskId: env.QA_METRICS_TASK_ID || null,
      callId: randomUUID() };
    const started = performance.now();
    const observation = require('./langfuse-observability').start('groq.request', { 'gen_ai.request.model': options.simulated ? 'synthetic-installation-model' : request.model,
      'langfuse.observation.type': kind === 'embedding' ? 'embedding' : 'generation', 'qa.simulated': options.simulated === true });
    emit({ type: 'call_start', ...meta });
    let finished = false;
    function finish(data, success, status) {
      if (finished) return;
      finished = true;
      const tokens = usage(data, provider, kind);
      const estimate = cost({ ...meta, model: data?.model || meta.model, serviceTier: data?.service_tier || meta.serviceTier }, tokens, options.catalog || prices(env));
      observation.setAttributes({ 'gen_ai.usage.input_tokens': tokens.inputTokens, 'gen_ai.usage.output_tokens': tokens.outputTokens,
        'http.response.status_code': status, 'qa.success': success, 'qa.estimated_cost_usd': options.simulated ? undefined : estimate.usd });
      observation.end(success);
      emit({ type: 'call_end', ...meta, model: data?.model || meta.model,
        durationMs: performance.now() - started, success, httpStatus: status,
        ...tokens, usageStatus: tokens.inputTokens !== null && tokens.outputTokens !== null ? 'MEASURED' : 'UNKNOWN',
        cost: estimate });
    }
    let response;
    try { response = await fetcher(url, init); }
    catch (error) { finish(null, false, null); throw error; }
    if (!request.stream || !response.ok) {
      let data;
      try { data = await response.clone().json(); } catch { /* Unknown usage, never characters / 4. */ }
      finish(data, response.ok, response.status);
      return response;
    }
    // Pass bytes through unchanged; only retain usage, never prompt/answer content.
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '', last = null;
    function parse(text, final = false) {
      buffer += text;
      const lines = buffer.split('\n'); buffer = final ? '' : lines.pop();
      for (const line of lines) {
        try {
          const data = JSON.parse(line.replace(/^data:\s*/, ''));
          if (data.usage || data.x_groq?.usage || data.done === true) last = data;
        } catch { /* SSE markers and partial lines are not data. */ }
      }
      if (buffer.length > 1024 * 1024) buffer = ''; // bounded parser, incomplete usage stays unknown
    }
    const stream = new ReadableStream({
      async pull(controller) {
        try {
          const next = await reader.read();
          if (next.done) { parse(decoder.decode(), true); finish(last, true, response.status); controller.close(); }
          else { parse(decoder.decode(next.value, { stream: true })); controller.enqueue(next.value); }
        } catch (error) { finish(last, false, response.status); controller.error(error); }
      },
      async cancel(reason) { finish(null, false, response.status); await reader.cancel(reason); },
    });
    return new Response(stream, { status: response.status, statusText: response.statusText, headers: response.headers });
  };
}
module.exports = { ROOT, DEFAULT_FILE, write, usage, cost, startTask, endTask, meteredFetch };
