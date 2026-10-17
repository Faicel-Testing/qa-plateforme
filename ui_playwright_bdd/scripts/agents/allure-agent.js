'use strict';
const path = require('path');
const fs = require('fs');
const { execute, resultDirectory, readResults } = require('./shared/pipeline-runtime');
const root = path.join(__dirname, '..', '..');
async function main() {
  const input = resultDirectory(root);
  const output = path.join(path.dirname(input), path.basename(input) === 'results' ? 'report' : 'allure-report');
  const command = process.argv[2] || 'generate';
  if (!['generate', 'open'].includes(command)) throw new Error('Use generate or open');
  if (command === 'generate' || !fs.existsSync(path.join(output, 'index.html'))) {
    if (!readResults(input).results.length) {
      const count = await require('./shared/recover-allure').recoverAllure(input);
      console.log(`Recovered ${count} Allure results from the recorded Cucumber journal (no tests rerun).`);
    }
    const history = require('./shared/allure-history');
    const prepared = history.prepareHistory(root, input);
    const dashboard = require('../browser-dashboard').main(input);
    require('./shared/allure-environment').writeEnvironment(input, dashboard || {});
    const generated = await execute(process.execPath, [path.join(root, 'node_modules/allure-commandline/bin/allure'), 'generate', input, '-o', output, '--clean'], {
      cwd: root, verbose: true, timeout: 300000,
    });
    if (!generated.success) throw new Error(generated.error || 'Allure generation failed');
    history.saveHistory(prepared, output);
    console.log(`Allure: ${output}`);
  }
  if (command === 'generate') return;
  const args = ['open', output];
  const result = await execute(process.execPath, [path.join(root, 'node_modules/allure-commandline/bin/allure'), ...args], {
    cwd: root, verbose: true, timeout: command === 'generate' ? 300000 : 2147483647,
  });
  if (!result.success) { console.error(result.error || `Allure failed (timeout=${result.timedOut}, exit=${result.exitCode})`); process.exitCode = 1; }
  else console.log(`Allure: ${output}`);
}
if (require.main === module) main().catch(e => { console.error(e.message); process.exitCode = 1; });
module.exports = { main };
