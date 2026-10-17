'use strict';
// CI entry point: test execution and read-only analysis are separate jobs.
const fs = require('fs');
const path = require('path');
const runtime = require('./agents/shared/pipeline-runtime');
const { sourceHash } = require('./agents/shared/review-context');
const { readVerification } = require('./agents/shared/agent-verifier');
const ROOT = path.join(__dirname, '..');
async function analyze(root = ROOT, env = process.env, execute = runtime.execute) {
  const dir = runtime.resultDirectory(root, env);
  const out = path.join(root, 'logs', 'ci-ai');
  fs.mkdirSync(out, { recursive: true });
  const summary = { runId: env.QA_RUN_ID, commit: env.GITHUB_SHA, status: 'BLOCKED', releaseAuthorized: false, steps: [] };
  try {
    const manifest = JSON.parse(fs.readFileSync(path.join(dir, 'run-manifest.json'), 'utf8'));
    const data = runtime.readResults(dir);
    if (!env.QA_RUN_ID || manifest.runId !== env.QA_RUN_ID || manifest.completed !== true ||
        manifest.sourceHash !== sourceHash(root) || (env.GITHUB_SHA && manifest.commit !== env.GITHUB_SHA) ||
        !Number.isFinite(manifest.startedAt) || !Number.isFinite(manifest.finishedAt) ||
        manifest.finishedAt < manifest.startedAt || !Number.isInteger(manifest.exitCode) ||
        !data.results.length || data.errors.length || manifest.resultCount !== data.results.length ||
        data.results.some(r => !Number.isFinite(r.start) || !Number.isFinite(r.stop) ||
          r.start < manifest.startedAt || r.stop > manifest.finishedAt || r.stop < r.start)) {
      throw new Error('Missing, incomplete or mismatched execution evidence');
    }
    summary.testsPassed = runtime.checkRun(dir, env.QA_RUN_ID).allowed;
    if (!env.GROQ_API_KEY?.trim()) {
      summary.status = 'UNAVAILABLE'; summary.reason = 'GROQ_API_KEY absent; analysis not executed';
    } else {
      for (const [agent, command] of [['quality', 'triage'], ['bug', 'analyze']]) {
        const verificationFile = path.join(out, agent + '-' + require('crypto').randomUUID() + '.jsonl');
        const result = await execute(process.execPath, [path.join(root, 'scripts', 'agents', agent + '-agent.js'), command], {
          cwd: root, env: { ...env, ALLURE_RESULTS_DIR: dir, QA_VERIFICATION_FILE: verificationFile },
          logFile: path.join(out, agent + '.log'), timeout: 600000,
        });
        summary.steps.push({ agent, success: result.success, exitCode: result.exitCode,
          verification: readVerification(verificationFile).status });
      }
      summary.status = summary.steps.some(s => !s.success || s.verification === 'REJECTED') ? 'FAILED' : 'ADVISORY';
    }
  } catch (error) { summary.reason = error.message; }
  fs.writeFileSync(path.join(out, 'summary.json'), JSON.stringify(summary, null, 2));
  if (env.GITHUB_STEP_SUMMARY) fs.appendFileSync(env.GITHUB_STEP_SUMMARY,
    `\n### Analyse IA : ${summary.status}\n\nAvis consultatif uniquement. Aucune autorisation de release.\n`);
  console.log(JSON.stringify(summary, null, 2));
  return summary;
}
async function main() {
  if (process.argv[2] === 'test') {
    const code = await require('./agents/runner-agent').runCucumber('@regression and not @wip');
    process.exitCode = code;
  } else if (process.argv[2] === 'analyze') {
    const result = await analyze();
    process.exitCode = result.status === 'ADVISORY' ? 0 : 1;
  } else throw new Error('Usage: node scripts/ci-ai.js test|analyze');
}
if (require.main === module) main().catch(e => { console.error(e.message); process.exitCode = 1; });
module.exports = { analyze };
