'use strict';
// Compatibility for deterministic JS adapters. AI chains execute in Python.
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');
const root = path.resolve(__dirname, '..');

function request(method, args, agent) {
  const python = path.join(root, '.venv-agents', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  return new Promise((resolve, reject) => {
    if (!fs.existsSync(python)) return reject(Error('Python runtime missing: npm run agents:setup'));
    const child = spawn(python, ['-m', 'qa_agents.worker'], { cwd: root, windowsHide: true,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8', LANGCHAIN_TRACING_V2: 'false', LANGSMITH_TRACING: 'false' },
      stdio: ['pipe', 'pipe', 'pipe'] });
    let output = '', oversized = false;
    const timer = setTimeout(() => {
      child.kill(); reject(Error('Python LLM deadline exceeded'));
    }, 600000);
    child.stdout.on('data', chunk => {
      output += chunk;
      if (Buffer.byteLength(output) > 8 * 1024 * 1024) { oversized = true; child.kill(); }
    });
    child.stderr.resume(); // Do not leak raw third-party exception messages.
    child.on('error', error => { clearTimeout(timer); reject(error); });
    child.on('close', code => {
      clearTimeout(timer);
      try {
        if (oversized) throw Error('Python response too large');
        const data = JSON.parse(output);
        if (code !== 0 || !data.ok) throw Error(data.error || 'Python LLM failed');
        resolve(data.value);
      } catch (error) { reject(error); }
    });
    child.stdin.on('error', () => {});
    child.stdin.end(JSON.stringify({ method, args, agent }));
  });
}

function install() {
  if (process.env.QA_PYTHON_BRIDGE === '1') return;
  const file = require.resolve('./agents/llm');
  const original = require(file);
  const agent = path.basename(process.argv[1] || '').replace(/-agent\.js$/, '');
  const facade = { ...original };
  for (const method of ['chat', 'chatCot', 'chatStructured', 'chatConfident', 'chatAdversarial', 'chatSelfConsistent']) {
    facade[method] = (...args) => request(method, args, agent);
  }
  // Compatibility iterator is buffered; no claim of token streaming.
  facade.chatStream = async (...args) => (async function* () { yield await request('chat', args, agent); })();
  require.cache[file].exports = facade;
}
install();
module.exports = { request };
