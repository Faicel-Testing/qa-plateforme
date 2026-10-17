'use strict';
// Application gateway, shared by generation, streaming, judge and embeddings.
const fs = require('node:fs');
const path = require('node:path');
const { randomUUID } = require('node:crypto');
const ROOT = path.resolve(__dirname, '../../..');
const DIRECTORY = path.join(ROOT, 'logs/gateway');
function reject(reason) {
  const error = new Error('AI gateway blocked request: ' + reason);
  error.code = 'AI_GATEWAY_BLOCKED'; error.reason = reason;
  throw error;
}
function isGatewayError(error) {
  for (let i = 0; error && i < 8; i++, error = error.cause) if (error.code === 'AI_GATEWAY_BLOCKED') return true;
  return false;
}
function policy() {
  let value;
  try { value = JSON.parse(fs.readFileSync(path.join(ROOT, 'config/ai-gateway.json'), 'utf8')); }
  catch { reject('POLICY_UNAVAILABLE'); }
  if (value.version !== 1 || !value.providers || ['maxRequestBytes', 'maxOutputTokens', 'maxRequestsPerMinute', 'maxReservedUnitsPerTask', 'timeoutMs']
    .some(key => !Number.isSafeInteger(value[key]) || value[key] <= 0)) reject('INVALID_POLICY');
  return value;
}
function audit(event, directory = DIRECTORY) {
  try {
    fs.mkdirSync(directory, { recursive: true });
    fs.appendFileSync(path.join(directory, 'audit.jsonl'), JSON.stringify({ at: new Date().toISOString(), ...event }) + '\n');
  } catch { reject('AUDIT_UNAVAILABLE'); }
}
function checkContent(value, env, rules) {
  const text = JSON.stringify(value);
  if (Buffer.byteLength(text) > rules.maxRequestBytes) reject('REQUEST_TOO_LARGE');
  // Inspect decoded JSON values as well as serialized text, so escaped secrets cannot bypass checks.
  const strings = [];
  function visit(item) {
    if (typeof item === 'string') strings.push(item);
    else if (item && typeof item === 'object') for (const [key, entry] of Object.entries(item)) { strings.push(key); visit(entry); }
  }
  visit(value);
  const secrets = Object.entries(env).filter(([key, entry]) => /(?:KEY|TOKEN|PASSWORD|SECRET|CREDENTIAL)/i.test(key)
    && typeof entry === 'string' && entry.length >= 8).map(([, entry]) => entry);
  for (const entry of strings) {
    if (secrets.some(secret => entry.includes(secret)) || /\b(?:plane_api_|gsk_|sk-)[A-Za-z0-9_-]{16,}|\bBearer\s+[A-Za-z0-9._~+-]{16,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/i.test(entry)) reject('SECRET_IN_PAYLOAD');
  }
  return Buffer.byteLength(text);
}
function preflight(messages, env = process.env) {
  try {
    const rules = policy();
    checkContent(messages, env, rules);
    const cleaned = require('./payload-privacy').sanitize(messages);
    checkContent(cleaned, env, rules);
    return cleaned;
  }
  catch (error) {
    if (isGatewayError(error)) audit({ decision: 'BLOCK', reason: error.reason, taskId: env.QA_METRICS_TASK_ID || null });
    throw error;
  }
}
// Cross-process reservations. Failed network attempts also consume quota; SDK retries cannot evade it.
function releaseQuotaLock(handle, lock, io = fs, pause = ms => Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms)) {
  try { io.closeSync(handle); } catch { reject('QUOTA_RELEASE_FAILED'); }
  for (let attempt = 0; attempt < 5; attempt++) {
    try { io.unlinkSync(lock); return; }
    catch (error) {
      if (!['EPERM', 'EBUSY', 'EACCES'].includes(error.code) || attempt === 4) reject('QUOTA_RELEASE_FAILED');
      pause(50 * (attempt + 1));
    }
  }
}
function reserve(rules, units, taskId, directory = DIRECTORY, now = Date.now()) {
  fs.mkdirSync(directory, { recursive: true });
  const lock = path.join(directory, 'quota.lock'), file = path.join(directory, 'quota.json');
  let handle;
  try { handle = fs.openSync(lock, 'wx'); } catch { reject('QUOTA_BUSY_OR_UNAVAILABLE'); }
  try {
    fs.writeFileSync(handle, JSON.stringify({ pid: process.pid, createdAt: new Date().toISOString() }));
    let entries = [];
    if (fs.existsSync(file)) entries = JSON.parse(fs.readFileSync(file, 'utf8'));
    if (!Array.isArray(entries) || entries.some(e => !Number.isFinite(e.at) || !Number.isFinite(e.units) || e.units < 0 || typeof e.taskId !== 'string')) reject('INVALID_QUOTA_LEDGER');
    entries = entries.filter(e => e.at >= now - 86400000);
    if (entries.filter(e => e.at >= now - 60000).length >= rules.maxRequestsPerMinute) reject('RATE_LIMIT');
    if (entries.filter(e => e.taskId === taskId).reduce((sum, e) => sum + e.units, 0) + units > rules.maxReservedUnitsPerTask) reject('TASK_BUDGET');
    entries.push({ at: now, taskId, units });
    // Every reader holds the same lock. Direct fsynced writes avoid Windows rename sharing violations.
    // A interrupted/corrupt write is refused on the next request rather than resetting quota.
    const ledger = fs.openSync(file, 'w');
    try { fs.writeFileSync(ledger, JSON.stringify(entries)); fs.fsyncSync(ledger); }
    finally { fs.closeSync(ledger); }
  } catch (error) { if (isGatewayError(error)) throw error; reject('QUOTA_UNAVAILABLE'); }
  finally { releaseQuotaLock(handle, lock); }
}
async function reserveWithRetry(rules, units, taskId, reserveFn = reserve) {
  const deadline = Date.now() + 2500;
  while (true) {
    try { return reserveFn(rules, units, taskId); }
    catch (error) {
      if (error.reason !== 'QUOTA_BUSY_OR_UNAVAILABLE' || Date.now() >= deadline) throw error;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
  }
}
function gatewayFetch(provider, fetcher = globalThis.fetch, dependencies = {}) {
  return async (url, init = {}) => {
    const env = dependencies.env || process.env;
    const emit = dependencies.audit || audit;
    const event = { provider, taskId: env.QA_METRICS_TASK_ID || null, requestId: randomUUID() };
    let next;
    try {
      const rules = dependencies.policy || policy();
      if (env.AI_LOCAL_ONLY === 'true' && provider !== 'ollama') reject('LOCAL_ONLY');
      const allowed = rules.providers[provider];
      if (!allowed || !Array.isArray(allowed.origins) || !Array.isArray(allowed.models) || !Array.isArray(allowed.routes)) reject('PROVIDER_NOT_ALLOWED');
      // SDKs currently pass a URL and a JSON string. Reject unsupported bodies rather than inspecting an incomplete request.
      if (!(typeof url === 'string' || url instanceof URL)) reject('UNSUPPORTED_REQUEST');
      const address = new URL(url);
      if (address.username || address.password || address.search || address.hash || !allowed.origins.includes(address.origin)
        || !allowed.routes.includes(address.pathname)) reject('DESTINATION_NOT_ALLOWED');
      if (address.protocol !== 'https:' && !(provider === 'ollama' && ['127.0.0.1', 'localhost', '[::1]'].includes(address.hostname))) reject('TLS_REQUIRED');
      if (env.NODE_TLS_REJECT_UNAUTHORIZED === '0' || process.env.NODE_TLS_REJECT_UNAUTHORIZED === '0') reject('TLS_DISABLED');
      if (init.dispatcher || init.agent) reject('CUSTOM_TLS_TRANSPORT');
      const headers = new Headers(init.headers);
      if (headers.has('host') || headers.has('proxy-authorization')) reject('UNSAFE_HEADER');
      const method = (init.method || 'GET').toUpperCase();
      const tags = provider === 'ollama' && address.pathname === '/api/tags';
      let body, bytes = 0, output = 0;
      if (tags) { if (method !== 'GET' || init.body) reject('INVALID_METHOD'); }
      else {
        if (method !== 'POST' || typeof init.body !== 'string') reject('JSON_POST_REQUIRED');
        if (Buffer.byteLength(init.body) > rules.maxRequestBytes) reject('REQUEST_TOO_LARGE');
        try { body = JSON.parse(init.body); } catch { reject('INVALID_JSON'); }
        if (!body || !allowed.models.includes(body.model)) reject('MODEL_NOT_ALLOWED');
        event.model = body.model;
        bytes = checkContent(body, env, rules);
        body = require('./payload-privacy').sanitize(body);
        bytes = checkContent(body, env, rules);
        if (address.pathname !== '/api/embed') {
          const requested = provider === 'groq' ? body.max_completion_tokens ?? body.max_tokens : body.options?.num_predict;
          output = requested === undefined ? rules.maxOutputTokens : requested;
          if (!Number.isSafeInteger(output) || output < 1 || output > rules.maxOutputTokens) reject('OUTPUT_LIMIT');
          if (body.n !== undefined && body.n !== 1) reject('MULTIPLE_COMPLETIONS');
          if (provider === 'groq') { delete body.max_tokens; body.max_completion_tokens = output; }
          else body.options = { ...body.options, num_predict: output };
        }
      }
      await (dependencies.reserve || reserveWithRetry)(rules, bytes + output, env.QA_GATEWAY_BUDGET_ID || env.QA_METRICS_TASK_ID || 'process-' + process.pid);
      emit({ ...event, decision: 'ALLOW', inputBytes: bytes, maxOutputTokens: output });
      const timeout = AbortSignal.timeout(rules.timeoutMs);
      next = { ...init, headers, redirect: 'error', ...(body ? { body: JSON.stringify(body) } : {}),
        signal: init.signal ? AbortSignal.any([init.signal, timeout]) : timeout };
    } catch (error) {
      const reason = isGatewayError(error) ? error.reason : 'INVALID_REQUEST_OR_POLICY';
      // A stable code helps diagnose local failures without logging URLs, headers or payloads.
      const localCode = ['EPERM', 'EACCES', 'EBUSY', 'ENOENT', 'ENOSPC', 'ERR_INVALID_ARG_TYPE'].includes(error.code) ? error.code : undefined;
      emit({ ...event, decision: 'BLOCK', reason, ...(localCode ? { localCode } : {}) });
      reject(reason);
    }
    const response = await fetcher(url, next);
    if (response.status >= 300 && response.status < 400) { emit({ ...event, decision: 'BLOCK', reason: 'REDIRECT' }); reject('REDIRECT'); }
    return response;
  };
}
module.exports = { gatewayFetch, preflight, isGatewayError, policy, reserve, reserveWithRetry, checkContent, releaseQuotaLock };
