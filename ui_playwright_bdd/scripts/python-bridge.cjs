'use strict';
// Local JSON RPC, not an HTTP service. It exposes guarded tools, never a shell.
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const AGENTS = ['codegen', 'planning', 'quality', 'bug', 'advisor', 'runner', 'reporting', 'ci', 'observability', 'governance'];

async function dispatch(request) {
  const { operation, agent = 'quality' } = request;
  if (!AGENTS.includes(agent)) throw Error('Unknown agent');
  process.argv[1] = path.join(__dirname, 'agents', agent + '-agent.js');
  if (request.dryRun && !process.argv.includes('--dry-run')) process.argv.push('--dry-run');
  const shared = name => require('./agents/shared/' + name);
  const runtime = shared('pipeline-runtime');
  switch (operation) {
    case 'chat': {
      const result = await require('./agents/llm').chat(request.messages, request.options || {});
      const text = result?.message?.content || '';
      const cb = shared('circuit-breaker');
      if ((!text && !result?.message?.tool_calls?.length) ||
          text === cb.getDefaultResponse(request.options?._fnName || 'chat') ||
          /service\s+LLM[^\n]*(indisponible|hors ligne)/i.test(text)) throw Error('LLM_UNAVAILABLE');
      return result;
    }
    case 'sources': return shared('source-verification').walkSources(root);
    case 'coverage': {
      const { generateMessages } = require('@cucumber/gherkin');
      const { IdGenerator, SourceMediaType } = require('@cucumber/messages');
      const sources = shared('source-verification').walkSources(root);
      if (sources.errors.length) throw Error('Incomplete source inventory');
      return sources.files.filter(f => /^src\/features\/.*\.feature$/.test(f.file)).map(f => {
        const envelopes = generateMessages(f.content, f.file, SourceMediaType.TEXT_X_CUCUMBER_GHERKIN_PLAIN,
          { newId: IdGenerator.incrementing(), includeGherkinDocument: true, includePickles: true });
        if (envelopes.some(e => e.parseError)) throw Error('Invalid Gherkin source');
        const pickles = envelopes.filter(e => e.pickle).map(e => e.pickle);
        return { file: f.file, scenarios: pickles.length, steps: pickles.reduce((sum, p) => sum + p.steps.length, 0),
          tags: [...new Set(pickles.flatMap(p => p.tags.map(t => t.name)))] };
      });
    }
    case 'read_source': return shared('analysis-evidence').readSource(root, request.args);
    case 'source_context': return shared('analysis-evidence').sourceContext(root, request.failure);
    case 'source_bundle': return shared('analysis-evidence').sourceBundle(root, request.failure,
      { directory: runtime.resultDirectory(root), runId: process.env.QA_RUN_ID });
    case 'skill': return shared('skill-store').instructions(request.name);
    case 'prompt': return shared('prompt-store').get(request.name);
    case 'gherkin_contract': return shared('gherkin-contract').contract(request.key);
    case 'verify': return shared('agent-verifier').createVerifier({ agent, root }).check(request.kind, request.output, request.context || {});
    case 'propose': {
      const proposal = shared('change-proposals');
      const file = proposal.target(root, request.file);
      shared('generated-code').validateGenerated(request.content, file.endsWith('.feature') ? 'gherkin' : 'typescript');
      if (request.dryRun) return { status: 'preview', file: request.file };
      return proposal.propose(root, file, request.content, agent);
    }
    case 'repair_proposal': {
      const proposals = shared('change-proposals');
      const file = proposals.target(root, request.file);
      const before = fs.readFileSync(file, 'utf8');
      if (typeof request.old !== 'string' || !request.old || before.split(request.old).length !== 2) throw Error('Repair requires one unambiguous match');
      return dispatch({ ...request, operation: 'propose', content: before.replace(request.old, request.replacement) });
    }
    case 'stories': return require('./agents/plane-fetcher').fetchStories();
    case 'story': return require('./agents/plane-fetcher').fetchIssue(request.key);
    case 'plane_check': return require('./agents/plane-fetcher').client().request();
    case 'cycles': return require('./agents/plane-fetcher').client().list('cycles/');
    case 'testcases': {
      const items = await require('./agents/plane-fetcher').client().list('work-items/');
      return items.filter(i => i.external_source === shared('plane-testcases').SOURCE).sort((a, b) => a.sequence_id - b.sequence_id);
    }
    case 'import_stories': return shared('plane-stories').importStories(require('./agents/plane-fetcher').client(), { dryRun: !!request.dryRun });
    case 'results': {
      const directory = runtime.resultDirectory(root);
      const data = runtime.readResults(directory);
      return { ...data, directory, run: runtime.checkRun(directory, process.env.QA_RUN_ID) };
    }
    case 'allure_verify': {
      const directory = runtime.resultDirectory(root);
      const files = fs.existsSync(directory) ? fs.readdirSync(directory).filter(f => f.endsWith('-result.json')) : [];
      const allure = shared('allure-verification');
      return allure.allureVerdict(allure.buildAllureSummary(files, f => fs.readFileSync(path.join(directory, f), 'utf8')));
    }
    case 'audit_prepare': {
      const source = shared('source-verification');
      const { files, errors } = source.walkSources(root);
      const local = await source.runLocalChecks(root);
      const facts = Object.fromEntries(Object.entries(local).map(([name, check]) => [name, {
        status: check.status, scope: check.scope, scenarios: check.scenarios, steps: check.steps,
        synchronousCalls: check.synchronousCalls, diagnosticCount: check.diagnostics?.length,
      }]));
      return { files, errors, local, ...source.buildSourceBatches(files, facts, request.maxChars || 24000) };
    }
    case 'audit_validate': return shared('source-verification').validateReview(request.raw, request.files, request.local);
    case 'analysis_prompt': return shared('llm-analysis').analysisPrompt(request.failure, request.context,
      new Map(request.reads), request.limit || 12000, !!request.final);
    default: throw Error('Unsupported framework service');
  }
}

async function main() {
  // Console diagnostics go to stderr. stdout is strictly the JSON protocol.
  console.log = (...args) => console.error(...args);
  require('dotenv').config({ path: path.join(root, '.env'), quiet: true });
  let input = '';
  for await (const chunk of process.stdin) {
    input += chunk;
    if (Buffer.byteLength(input) > 8 * 1024 * 1024) throw Error('RPC_INPUT_TOO_LARGE');
  }
  try {
    const value = await dispatch(JSON.parse(input));
    process.stdout.write(JSON.stringify({ ok: true, value }));
  } catch (error) {
    // Never echo arbitrary provider errors (they can contain request bodies).
    const code = error.verification ? 'VERIFICATION_REJECTED' : error.message === 'LLM_UNAVAILABLE' ? error.message : 'FRAMEWORK_SERVICE_FAILED';
    process.stdout.write(JSON.stringify({ ok: false, error: code, verification: error.verification }));
    process.exitCode = 1;
  }
}
if (require.main === module) main().catch(() => { process.stdout.write('{"ok":false,"error":"INVALID_RPC_REQUEST"}'); process.exitCode = 1; });
module.exports = { dispatch };
