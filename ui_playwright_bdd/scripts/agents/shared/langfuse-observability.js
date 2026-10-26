'use strict';
// Metadata-only instrumentation. No automatic HTTP/SQL/prompt capture.
const { randomUUID } = require('node:crypto');
let state;
const ALLOWED = new Set(['qa.run_id', 'qa.operation', 'qa.agent', 'qa.storage', 'qa.sources', 'qa.chunks',
  'qa.cache_hits', 'qa.generated', 'qa.matched', 'qa.dimension', 'qa.success', 'qa.exit_code', 'qa.simulated',
  'gen_ai.request.model', 'gen_ai.usage.input_tokens', 'gen_ai.usage.output_tokens',
  'qa.estimated_cost_usd', 'http.response.status_code', 'langfuse.observation.type', 'langfuse.trace.name']);
function attributes(values = {}) {
  return Object.fromEntries(Object.entries(values).filter(([key, value]) => ALLOWED.has(key)
    && (typeof value === 'boolean' || typeof value === 'number' && Number.isFinite(value)
      || typeof value === 'string' && /^[a-zA-Z0-9_.:/-]{1,150}$/.test(value))));
}
function endpoint(env = process.env) {
  const url = new URL(env.LANGFUSE_BASE_URL || 'http://127.0.0.1:3000');
  if (url.username || url.password || url.search || url.hash || url.pathname !== '/'
    || !(url.protocol === 'https:' || url.protocol === 'http:' && ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname))) throw new Error('Invalid Langfuse endpoint');
  return url.origin;
}
function init() {
  if (process.env.LANGFUSE_ENABLED !== 'true') return null;
  if (state !== undefined) return state;
  try {
    if (!process.env.LANGFUSE_PUBLIC_KEY || !process.env.LANGFUSE_SECRET_KEY) return state = null;
    const api = require('@opentelemetry/api');
    const { NodeSDK } = require('@opentelemetry/sdk-node');
    const { LangfuseSpanProcessor } = require('@langfuse/otel');
    const processor = new LangfuseSpanProcessor({ baseUrl: endpoint(), publicKey: process.env.LANGFUSE_PUBLIC_KEY,
      secretKey: process.env.LANGFUSE_SECRET_KEY, flushInterval: 1, flushAt: 10, timeout: 5, mediaUploadEnabled: false,
      shouldExportSpan: ({ otelSpan }) => otelSpan.instrumentationScope.name === 'qa-framework' });
    const sdk = new NodeSDK({ autoDetectResources: false, spanProcessors: [processor], instrumentations: [] });
    sdk.start();
    state = { api, sdk, processor, tracer: api.trace.getTracer('qa-framework') };
    process.once('beforeExit', () => { void flush(); });
    return state;
  } catch { state = null; return null; }
}
function activeContext(s) {
  const active = s.api.context.active();
  if (s.api.trace.getSpanContext(active)) return active;
  const parent = process.env.QA_TRACEPARENT;
  return parent ? s.api.propagation.extract(active, { traceparent: parent }) : active;
}
async function span(name, values, fn) {
  const s = init();
  if (!s) return fn();
  const safeName = /^[a-zA-Z0-9_.:-]{1,100}$/.test(name) ? name : 'qa.operation';
  return s.tracer.startActiveSpan(safeName, { attributes: attributes({ 'qa.run_id': process.env.QA_TRACE_RUN_ID || process.env.QA_RUN_ID,
    'langfuse.observation.type': 'span', ...values }) }, activeContext(s), async observation => {
    try {
      const value = await fn(observation);
      const success = value?.success !== false;
      if (typeof value?.exitCode === 'number') observation.setAttributes(attributes({ 'qa.exit_code': value.exitCode, 'qa.success': success }));
      observation.setStatus({ code: success ? s.api.SpanStatusCode.OK : s.api.SpanStatusCode.ERROR, ...(success ? {} : { message: 'TASK_UNSUCCESSFUL' }) });
      return value;
    }
    catch (error) { observation.setStatus({ code: s.api.SpanStatusCode.ERROR, message: 'OPERATION_FAILED' }); throw error; }
    finally { observation.end(); }
  });
}
function childEnvironment() {
  const s = init();
  if (!s) return {};
  const carrier = {};
  s.api.propagation.inject(activeContext(s), carrier);
  return carrier.traceparent ? { QA_TRACEPARENT: carrier.traceparent, QA_TRACE_RUN_ID: process.env.QA_TRACE_RUN_ID || process.env.QA_RUN_ID || '' } : {};
}
function setAttributes(values) {
  const s = init();
  s?.api.trace.getActiveSpan()?.setAttributes(attributes(values));
}
async function flush() {
  if (!state) return;
  let timer;
  try { await Promise.race([state.processor.forceFlush(), new Promise(resolve => { timer = setTimeout(resolve, 2000); })]); }
  catch { /* Observability cannot change test/provider outcomes. */ }
  finally { clearTimeout(timer); }
}
function traceId() {
  const s = init();
  return s?.api.trace.getSpanContext(activeContext(s))?.traceId || null;
}
function start(name, values) {
  const s = init();
  if (!s) return { setAttributes() {}, end() {} };
  const observation = s.tracer.startSpan(name, { attributes: attributes(values) }, activeContext(s));
  return { setAttributes: values => observation.setAttributes(attributes(values)), end: success => {
    observation.setStatus({ code: success ? s.api.SpanStatusCode.OK : s.api.SpanStatusCode.ERROR, ...(success ? {} : { message: 'OPERATION_FAILED' }) });
    observation.end();
  } };
}
module.exports = { span, start, attributes, endpoint, childEnvironment, setAttributes, flush, traceId, newRunId: () => randomUUID() };
