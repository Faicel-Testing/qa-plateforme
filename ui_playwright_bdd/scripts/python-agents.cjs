'use strict';
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');

async function main() {
  console.log('[Python] Demarrage du lanceur et chargement de la configuration...');
  const runtime = require('./agents/shared/pipeline-runtime');
  require('dotenv').config({ path: path.join(root, '.env'), quiet: true });
  const python = path.join(root, '.venv-agents', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  if (!fs.existsSync(python)) throw Error('Python environment missing. Run npm run agents:setup');
  const env = { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUNBUFFERED: '1', QA_AGENT_RUNTIME: 'python' };
  if (env.NODE_EXTRA_CA_CERTS) env.NODE_EXTRA_CA_CERTS = fs.realpathSync(path.resolve(root, env.NODE_EXTRA_CA_CERTS));
  console.log('[Python] Lancement de qa_agents (le premier chargement peut prendre quelques secondes)...');
  const observation = require('./agents/shared/langfuse-observability');
  const result = await observation.span('task.python', {}, () => runtime.execute(python, ['-m', 'qa_agents', ...process.argv.slice(2)], {
    cwd: root, env, verbose: true, taskLabel: 'python ' + process.argv.slice(2, 4).join(' '),
    timeout: runtime.timeoutMs(env.QA_TASK_TIMEOUT_MS, 7200000),
  }));
  await observation.flush();
  process.exitCode = result.success ? 0 : result.exitCode || 1;
}
if (require.main === module) main().catch(error => { console.error(error.message); process.exitCode = 1; });
module.exports = { main };
