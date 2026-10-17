'use strict';
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const root = path.resolve(__dirname, '..');
function run(command, args) {
  const result = spawnSync(command, args, { cwd: root, stdio: 'inherit', windowsHide: true });
  if (result.error || result.status !== 0) throw Error('Python setup failed; check the installation output');
}
try {
  run('python', ['-m', 'venv', '.venv-agents']);
  const python = path.join(root, '.venv-agents', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  run(python, ['-m', 'pip', 'install', '-r', 'qa_agents/requirements.lock.txt']);
  run(python, ['-m', 'qa_agents', 'doctor']);
} catch (error) { console.error(error.message); process.exitCode = 1; }
