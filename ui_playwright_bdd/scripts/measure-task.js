'use strict';
const fs = require('node:fs');
const path = require('node:path');
const runtime = require('./agents/shared/pipeline-runtime');
const { ROOT } = require('./agents/shared/task-metrics');
require('dotenv').config({ path: path.join(ROOT, '.env'), quiet: true });
async function main() {
  const [entry, ...args] = process.argv.slice(2);
  if (!entry) throw new Error('Usage: npm run metrics:run -- scripts/agents/quality-agent.js verify --local-only');
  const file = fs.realpathSync(path.resolve(ROOT, entry));
  const relative = path.relative(ROOT, file);
  if (relative.startsWith('..') || path.isAbsolute(relative) || !/\.[cm]?js$/.test(file)) throw new Error('Expected a JavaScript entry point inside the framework');
  const env = { ...process.env };
  if (env.NODE_EXTRA_CA_CERTS) env.NODE_EXTRA_CA_CERTS = fs.realpathSync(path.resolve(ROOT, env.NODE_EXTRA_CA_CERTS));
  const observation = require('./agents/shared/langfuse-observability');
  const result = await observation.span('task.node', {}, () => runtime.execute(process.execPath, [file, ...args], {
    env,
    cwd: ROOT, verbose: true, timeout: runtime.timeoutMs(process.env.QA_TASK_TIMEOUT_MS, 7200000),
  }));
  await observation.flush();
  console.log(`[Metrics] ${result.metricsTaskId} — ${(result.durationMs / 1000).toFixed(2)} s — ${result.success ? 'PROCESS_OK' : 'FAILED'}`);
  process.exitCode = result.exitCode === 0 && result.success ? 0 : result.exitCode || 1;
}
if (require.main === module) main().catch(error => { console.error(error.message); process.exitCode = 1; });
