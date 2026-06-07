// ============================================
// Execute Agent — AI-Powered Pipeline
// ============================================
// Orchestrates: run tests → if failures, invoke AI bug-analyzer → re-run.
//
// Usage:
//   npm run agent:execute                          → all features
//   npm run agent:execute -- --features=Id01,Id02  → signup + login only
//   npm run agent:execute -- --features=Id01        → signup only
//
// --features accepts comma-separated Id prefixes (e.g. Id01,Id02,Id05)
// ============================================

require('dotenv').config();
const { spawn } = require('child_process');
const path = require('path');
const fs   = require('fs');

const projectRoot = path.resolve(__dirname, '../../');
const resultsDir  = path.join(projectRoot, 'allure-results');

// ── Parse --features=Id01,Id02 argument ──────────────────────────────────────
function parseFeaturePattern() {
  const arg = process.argv.find(a => a.startsWith('--features='));
  if (!arg) return null;
  const ids = arg.replace('--features=', '').split(',').map(s => s.trim()).filter(Boolean);
  if (!ids.length) return null;
  // Build glob patterns: src/features/Id01_*.feature src/features/Id02_*.feature ...
  return ids.map(id => `src/features/${id}_*.feature`).join(' ');
}

// ── Run a subprocess ──────────────────────────────────────────────────────────
function runCmd(cmd, label) {
  return new Promise((resolve) => {
    console.log(`\n▶ ${label}`);
    const child = spawn(cmd, { cwd: projectRoot, stdio: 'inherit', shell: true });
    child.on('close', code => {
      console.log(`◀ ${label} → exit code ${code}`);
      resolve(code ?? 1);
    });
    child.on('error', err => { console.error(`Process error: ${err.message}`); resolve(1); });
  });
}

function runNpm(args, label) {
  return runCmd(`npm ${args.join(' ')}`, label);
}

// ── Build the cucumber command for a given feature pattern ────────────────────
function buildCucumberCmd(featurePattern) {
  return [
    'npx cucumber-js',
    featurePattern,
    '--require-module ts-node/register',
    '--require src/core/world.ts',
    '--require src/hooks/**/*.ts',
    '--require src/steps/**/*.ts',
    '--format progress',
    '--format allure-cucumberjs/reporter'
  ].join(' ');
}

function hasFailures() {
  if (!fs.existsSync(resultsDir)) return false;
  return fs.readdirSync(resultsDir)
    .filter(f => f.endsWith('-result.json'))
    .some(f => {
      try { const r = JSON.parse(fs.readFileSync(path.join(resultsDir, f), 'utf-8')); return r.status === 'failed' || r.status === 'broken'; }
      catch { return false; }
    });
}

// ── Main ──────────────────────────────────────────────────────────────────────
async function run() {
  const featurePattern = parseFeaturePattern();
  const label = featurePattern ? `features: ${featurePattern}` : 'all features';

  console.log('=== EXECUTE AGENT ===');
  console.log(`Scope: ${label}`);
  console.log('Step 1: Running tests...');

  let exitCode1;
  if (featurePattern) {
    // Run targeted features directly
    const cmd = buildCucumberCmd(featurePattern);
    exitCode1 = await runCmd(cmd, `cucumber-js [${label}]`);
  } else {
    exitCode1 = await runNpm(['run', 'test:allure'], 'npm run test:allure');
  }

  if (exitCode1 === 0) {
    console.log('\n✅ All tests passed!');
    await runNpm(['run', 'allure:generate'], 'npm run allure:generate');
    process.exit(0);
  }

  if (!hasFailures()) {
    console.log('\n❌ Tests crashed (no allure-results produced).');
    process.exit(exitCode1);
  }

  console.log('\n⚠️  Failures detected — invoking AI Bug Analyzer (Ollama)...');
  await runNpm(['run', 'allure:generate'], 'npm run allure:generate');

  const bugCode = await runNpm(['run', 'agent:bug'], 'npm run agent:bug');
  if (bugCode !== 0) {
    console.log('\n❌ Bug analyzer failed. Skipping re-run.');
    process.exit(bugCode);
  }

  console.log('\nStep 3: Re-running tests after AI fixes...');
  let exitCode2;
  if (featurePattern) {
    exitCode2 = await runCmd(buildCucumberCmd(featurePattern), `cucumber-js retry [${label}]`);
  } else {
    exitCode2 = await runNpm(['run', 'test:allure'], 'npm run test:allure (retry)');
  }

  await runNpm(['run', 'allure:generate'], 'npm run allure:generate');

  console.log(exitCode2 === 0
    ? '\n✅ All tests pass after AI fixes!'
    : '\n⚠️  Tests still failing. Review docs/BUG_ANALYSIS.md.');

  process.exit(exitCode2);
}

run().catch(err => { console.error('Execute agent error:', err.message || err); process.exit(1); });
