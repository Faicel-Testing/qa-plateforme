'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const root = path.resolve(__dirname, '..');
require('dotenv').config({ path: path.join(root, '.env'), quiet: true });
const { endpoint } = require('./agents/shared/langfuse-observability');
function uiEndpoint() {
  const url = new URL(endpoint());
  if (url.hostname === '127.0.0.1') url.hostname = 'localhost';
  return url.origin;
}
async function api(route, authenticated = true) {
  const headers = authenticated ? { Authorization: 'Basic ' + Buffer.from(process.env.LANGFUSE_PUBLIC_KEY + ':' + process.env.LANGFUSE_SECRET_KEY).toString('base64') } : {};
  const response = await fetch(endpoint() + route, { headers, redirect: 'error', signal: AbortSignal.timeout(30000) });
  if (!response.ok) throw new Error('LANGFUSE_HTTP_' + response.status);
  return response.json();
}
async function main(command = process.argv[2]) {
  if (command === 'open') {
    if (process.platform !== 'win32') throw new Error('Open ' + uiEndpoint() + ' in your browser');
    spawn('rundll32.exe', ['url.dll,FileProtocolHandler', uiEndpoint()], { detached: true, stdio: 'ignore', windowsHide: true }).unref();
    return;
  }
  await api('/api/public/health', false);
  const projects = await api('/api/public/projects');
  if (command === 'status') {
    console.log(JSON.stringify({ status: 'READY', url: uiEndpoint(), enabled: process.env.LANGFUSE_ENABLED === 'true', projects: projects.data?.length ?? null }, null, 2));
    return;
  }
  if (command === 'verify') return verifyProof(JSON.parse(fs.readFileSync(path.join(root, '.langfuse/last-proof.json'), 'utf8')));
  if (command !== 'check') throw new Error('Usage: status | check | verify | open');
  const python = path.join(root, '.venv-agents', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  const proof = await new Promise((resolve, reject) => {
    const child = spawn(python, ['-m', 'qa_agents.check_observability'], { cwd: root,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8', LANGFUSE_ENABLED: 'true' }, windowsHide: true });
    let stdout = '';
    child.stdout.on('data', data => { stdout += data; });
    child.stderr.on('data', () => {}); // Provider/SDK errors may carry arbitrary text; never echo them.
    child.on('error', reject);
    child.on('close', code => {
      if (code !== 0) return reject(new Error('LANGFUSE_SMOKE_FAILED'));
      try { resolve(JSON.parse(stdout)); } catch { reject(new Error('LANGFUSE_INVALID_PROOF')); }
    });
  });
  proof.recordedAt = new Date().toISOString();
  fs.writeFileSync(path.join(root, '.langfuse/last-proof.json'), JSON.stringify(proof, null, 2));
  return verifyProof(proof);
}
async function verifyProof(proof) {
  if (!/^[a-f0-9]{32}$/.test(proof.traceId || '') || proof.storage !== 'pgvector' || proof.semanticStatus !== 'READY') throw new Error('LANGFUSE_INCOMPLETE_PROOF');
  if (proof.pythonTraceId && proof.pythonTraceId !== proof.traceId) throw new Error('LANGFUSE_TRACE_MISMATCH');
  const expectedNames = ['installation.python', 'installation.node', 'rag.search', 'rag.pgvector', 'llm.gateway', 'groq.request'];
  let observations = [];
  const deadline = Date.now() + 120000;
  while (Date.now() < deadline) {
    try {
      const response = await api('/api/public/v2/observations?traceId=' + encodeURIComponent(proof.traceId) + '&limit=100&fields=basic,io,usage');
      observations = response.data || [];
      const receivedNames = new Set(observations.map(o => o.name));
      if (expectedNames.every(name => receivedNames.has(name))) break;
    } catch { /* ingestion is asynchronous */ }
    await new Promise(resolve => setTimeout(resolve, 1500));
  }
  const names = observations.map(o => o.name);
  for (const expected of expectedNames) {
    if (!names.includes(expected)) throw new Error('LANGFUSE_MISSING_OBSERVATION_' + expected);
  }
  const hasPayload = value => value != null && value !== '' && value !== 'null';
  if (observations.some(o => hasPayload(o.input) || hasPayload(o.output))) throw new Error('LANGFUSE_UNEXPECTED_CAPTURE');
  if (observations.some(o => o.traceId !== proof.traceId)) throw new Error('LANGFUSE_TRACE_MISMATCH');
  const pythonRoot = observations.find(o => o.name === 'installation.python');
  const byId = new Map(observations.map(o => [o.id, o]));
  let parent = observations.find(o => o.name === 'installation.node');
  const visited = new Set();
  while (parent && parent.id !== pythonRoot.id && !visited.has(parent.id)) {
    visited.add(parent.id);
    parent = byId.get(parent.parentObservationId);
  }
  if (parent?.id !== pythonRoot.id) throw new Error('LANGFUSE_BROKEN_PARENT_CONTEXT');
  const report = { status: 'PASS', ...proof, verifiedAt: new Date().toISOString(), observations: names, payloadCapture: false,
    traceUrl: uiEndpoint() + '/project/playwright-bdd/traces/' + proof.traceId };
  fs.writeFileSync(path.join(root, '.langfuse/integration-check.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
}
if (require.main === module) main().catch(error => { console.error(error.message); process.exitCode = 1; });
module.exports = { api, main, verifyProof };
