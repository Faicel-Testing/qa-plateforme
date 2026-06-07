// ============================================
// Bug Analyzer Agent — Ollama (local LLM)
// ============================================
// Reads allure-results failures, loads source files, uses local LLM to
// identify root causes and apply code fixes via tool use.
//
// Usage:    npm run agent:bug
// Requires: Ollama running + model pulled (see scripts/agents/llm.js)
// ============================================

require('dotenv').config();
const llm = require('./llm');
const fs  = require('fs');
const path = require('path');

const projectRoot = path.resolve(__dirname, '../../');
const resultsDir  = path.join(projectRoot, 'allure-results');
const srcDir      = path.join(projectRoot, 'src');
const docsDir     = path.join(projectRoot, 'docs');
const outputPath  = path.join(docsDir, 'BUG_ANALYSIS.md');

// ── File helpers ──────────────────────────────────────────────────────────────
function listSourceFiles(dir) {
  const files = [];
  if (!fs.existsSync(dir)) return files;
  function walk(d) {
    for (const e of fs.readdirSync(d)) {
      const full = path.join(d, e);
      if (fs.statSync(full).isDirectory()) walk(full);
      else if (e.endsWith('.ts') || e.endsWith('.feature'))
        files.push(path.relative(projectRoot, full).replace(/\\/g, '/'));
    }
  }
  walk(dir);
  return files;
}

function readProjectFile(rel) {
  const full = path.join(projectRoot, rel);
  return fs.existsSync(full) ? fs.readFileSync(full, 'utf-8') : null;
}

function applyFix(rel, oldCode, newCode) {
  const full = path.join(projectRoot, rel);
  if (!fs.existsSync(full)) return { ok: false, error: `File not found: ${rel}` };
  const content = fs.readFileSync(full, 'utf-8');
  if (!content.includes(oldCode))
    return { ok: false, error: `old_code not found in ${rel} — may already be fixed` };
  fs.writeFileSync(full, content.replace(oldCode, newCode), 'utf-8');
  return { ok: true };
}

// ── Tools definition ──────────────────────────────────────────────────────────
const TOOLS = [
  {
    name: 'read_file',
    description: 'Read the content of a source file in the project',
    input_schema: {
      type: 'object',
      properties: {
        file_path: { type: 'string', description: 'Relative path from project root' }
      },
      required: ['file_path']
    }
  },
  {
    name: 'apply_fix',
    description: 'Apply a targeted code fix by replacing an exact code block in a file',
    input_schema: {
      type: 'object',
      properties: {
        file_path: { type: 'string' },
        old_code:  { type: 'string', description: 'Exact code to replace' },
        new_code:  { type: 'string', description: 'Replacement code' },
        reason:    { type: 'string', description: 'Why this fix resolves the failure' }
      },
      required: ['file_path', 'old_code', 'new_code', 'reason']
    }
  },
  {
    name: 'report_analysis',
    description: 'Submit the final analysis after applying all fixes',
    input_schema: {
      type: 'object',
      properties: {
        summary:     { type: 'string' },
        root_causes: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              test_name:   { type: 'string' },
              root_cause:  { type: 'string' },
              fix_applied: { type: 'boolean' }
            }
          }
        }
      },
      required: ['summary', 'root_causes']
    }
  }
];

// ── Agentic loop ──────────────────────────────────────────────────────────────
async function analyzeWithLLM(failures, sourceFileList) {
  const failureContext = failures.map(f => {
    const error = f.statusDetails?.message || 'No error';
    const trace = (f.statusDetails?.trace || '').slice(0, 600);
    const steps = (f.steps || []).map(s => `  [${s.status}] ${s.name}`).join('\n');
    return `### ${f.name} [${f.status}]\nError: ${error}\nTrace:\n${trace}\nSteps:\n${steps}`;
  }).join('\n\n---\n\n');

  const messages = [
    {
      role: 'system',
      content: 'You are an expert QA engineer and TypeScript developer. Analyze test failures, read the relevant source files using tools, then apply targeted code fixes. After all fixes, call report_analysis.'
    },
    {
      role: 'user',
      content: `Analyze these test failures and fix them.\n\nAvailable source files:\n${sourceFileList.join('\n')}\n\n## Failures\n${failureContext}`
    }
  ];

  const fixes = [];
  let finalAnalysis = null;
  let iterations = 0;

  while (iterations < 20) {
    iterations++;
    const resp = await llm.chat(messages, { tools: TOOLS });
    const msg  = resp.message;
    const toolCalls = msg.tool_calls || [];

    if (!toolCalls.length) {
      if (msg.content?.trim()) console.log(msg.content);
      break;
    }

    messages.push(msg);

    for (const tc of toolCalls) {
      const name = tc.function.name;
      const args = llm.parseArgs(tc.function.arguments);
      let result;

      if (name === 'read_file') {
        const content = readProjectFile(args.file_path);
        result = content !== null ? content : `File not found: ${args.file_path}`;

      } else if (name === 'apply_fix') {
        const res = applyFix(args.file_path, args.old_code, args.new_code);
        if (res.ok) {
          fixes.push({ file: args.file_path, reason: args.reason });
          console.log(`  ✅ Fixed: ${args.file_path}`);
          console.log(`     ${args.reason}`);
          result = `Fix applied to ${args.file_path}`;
        } else {
          console.log(`  ⚠️  ${res.error}`);
          result = `Fix not applied: ${res.error}`;
        }

      } else if (name === 'report_analysis') {
        finalAnalysis = args;
        result = 'Analysis recorded.';

      } else {
        result = `Unknown tool: ${name}`;
      }

      messages.push({ role: 'tool', content: typeof result === 'string' ? result : JSON.stringify(result) });
    }

    if (finalAnalysis) break;
  }

  return { fixes, analysis: finalAnalysis };
}

// ── Main ──────────────────────────────────────────────────────────────────────
async function run() {
  await llm.assertRunning();

  if (!fs.existsSync(resultsDir)) {
    console.error('No allure-results found. Run: npm run test:allure');
    process.exit(1);
  }

  const resultFiles = fs.readdirSync(resultsDir).filter(f => f.endsWith('-result.json'));
  const results  = resultFiles.map(f => JSON.parse(fs.readFileSync(path.join(resultsDir, f), 'utf-8')));
  const failures = results.filter(r => r.status === 'failed' || r.status === 'broken');

  console.log('=== BUG ANALYZER ===');
  console.log(`Model:   ${llm.MODEL}`);
  console.log(`Total:   ${results.length}  Passed: ${results.filter(r => r.status === 'passed').length}  Failed: ${failures.length}`);

  if (!failures.length) {
    console.log('\n✅ All tests passed — nothing to fix.');
    return;
  }

  console.log(`\n🔍 Analyzing ${failures.length} failure(s)...\n`);
  const sourceFiles = listSourceFiles(srcDir);
  const { fixes, analysis } = await analyzeWithLLM(failures, sourceFiles);

  const lines = [
    '# Bug Analysis Report',
    `_${new Date().toISOString()} — model: ${llm.MODEL}_`,
    '',
    '## Summary',
    analysis?.summary || 'Analysis complete.',
    '',
    '## Fixes Applied',
    fixes.length ? fixes.map(f => `- **${f.file}**: ${f.reason}`).join('\n') : '_None._',
    '',
    '## Root Causes',
    ...(analysis?.root_causes || []).map(rc =>
      `### ${rc.test_name}\n- Root cause: ${rc.root_cause}\n- Fixed: ${rc.fix_applied ? '✅' : '⚠️'}\n`
    )
  ];

  fs.mkdirSync(docsDir, { recursive: true });
  fs.writeFileSync(outputPath, lines.join('\n'), 'utf-8');
  console.log(`\n📄 Report: ${outputPath}`);
  if (fixes.length) console.log(`🔧 ${fixes.length} fix(es) applied — re-run tests to verify.`);
}

run().catch(err => { console.error('Bug analyzer error:', err.message || err); process.exit(1); });
