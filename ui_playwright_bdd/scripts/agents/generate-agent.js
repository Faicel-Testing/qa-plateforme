// ============================================
// Generate Agent — Ollama (local LLM)
// ============================================
// Analyzes existing coverage gaps and generates new Gherkin feature files
// + TypeScript step definitions via local LLM tool use.
//
// Usage:    npm run agent:generate
// Requires: Ollama running + model pulled
// Output:   new .feature and .ts files in src/features/ and src/steps/
// ============================================

require('dotenv').config();
const llm  = require('./llm');
const fs   = require('fs');
const path = require('path');

const projectRoot = path.resolve(__dirname, '../../');
const srcDir      = path.join(projectRoot, 'src');

function readDir(dir, ext) {
  const out = {};
  if (!fs.existsSync(dir)) return out;
  function walk(d) {
    for (const e of fs.readdirSync(d)) {
      const full = path.join(d, e);
      if (fs.statSync(full).isDirectory()) walk(full);
      else if (!ext || e.endsWith(ext)) {
        const rel = path.relative(projectRoot, full).replace(/\\/g, '/');
        out[rel] = fs.readFileSync(full, 'utf-8');
      }
    }
  }
  walk(dir);
  return out;
}

const TOOLS = [
  {
    name: 'create_feature_file',
    description: 'Create a new Gherkin feature file for an uncovered test scenario',
    input_schema: {
      type: 'object',
      properties: {
        file_path:   { type: 'string', description: 'e.g. src/features/Id06_EdgeCases.feature' },
        content:     { type: 'string', description: 'Full Gherkin content' },
        description: { type: 'string', description: 'What coverage gap this fills' }
      },
      required: ['file_path', 'content', 'description']
    }
  },
  {
    name: 'create_steps_file',
    description: 'Create a TypeScript step definitions file for a feature file',
    input_schema: {
      type: 'object',
      properties: {
        file_path:   { type: 'string', description: 'e.g. src/steps/Id06_EdgeCasesTest.ts' },
        content:     { type: 'string', description: 'Full TypeScript step definitions' },
        description: { type: 'string', description: 'Which feature this implements' }
      },
      required: ['file_path', 'content', 'description']
    }
  }
];

async function run() {
  await llm.assertRunning();
  console.log(`=== GENERATE AGENT  [${llm.MODEL}] ===`);

  const features = readDir(path.join(srcDir, 'features'), '.feature');
  const steps    = readDir(path.join(srcDir, 'steps'),    '.ts');
  const pages    = readDir(path.join(srcDir, 'pages'),    '.ts');

  const existingIds = Object.keys(features)
    .map(f => parseInt((path.basename(f).match(/^Id(\d+)/) || [])[1] || '0'))
    .filter(n => n > 0);
  const nextId = existingIds.length ? Math.max(...existingIds) + 1 : 6;

  const context = [
    '## Features\n\n' + Object.entries(features).map(([f, c]) => `### ${f}\n\`\`\`gherkin\n${c}\n\`\`\``).join('\n\n'),
    '## Steps\n\n'   + Object.entries(steps).map(([f, c]) => `### ${f}\n\`\`\`typescript\n${c}\n\`\`\``).join('\n\n'),
    '## Pages\n\n'   + Object.entries(pages).map(([f, c]) => `### ${f}\n\`\`\`typescript\n${c}\n\`\`\``).join('\n\n'),
  ].join('\n\n');

  const messages = [
    {
      role: 'system',
      content: 'You are a senior QA automation engineer. Generate complete, runnable BDD test files for uncovered scenarios. Always create both the feature file AND its step definitions file.'
    },
    {
      role: 'user',
      content: `Analyze the existing test coverage below and generate new test files for the most important uncovered cases.

Priority gaps to cover:
1. Edge cases: empty inputs, special characters, very long text in todo items
2. Error states: wrong password, duplicate email registration
3. UI validation: form field error messages visibility
4. Boundary: very long todo text, minimum password length

Naming convention: IdXX_ prefix, starting from Id${String(nextId).padStart(2, '0')}_
Step imports: \`from '@cucumber/cucumber'\` and \`from '../core/world'\`
Step pattern: \`async function (this: CustomWorld)\`

Generate 2 new feature files with their step files using the tools.

## Existing Framework
${context}`
    }
  ];

  const created = [];
  let iterations = 0;

  while (iterations < 15) {
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
      const args = llm.parseArgs(tc.function.arguments);
      const { file_path, content, description } = args;
      const fullPath = path.join(projectRoot, file_path);
      let result;

      if (fs.existsSync(fullPath)) {
        result = `Skipped — ${file_path} already exists. Use a different name.`;
        console.log(`  ⚠️  Skipped (exists): ${file_path}`);
      } else {
        try {
          fs.mkdirSync(path.dirname(fullPath), { recursive: true });
          fs.writeFileSync(fullPath, content, 'utf-8');
          created.push({ file: file_path, description });
          console.log(`  ✅ Created: ${file_path}`);
          result = `Created ${file_path}`;
        } catch (err) {
          result = `Error: ${err.message}`;
          console.error(`  ❌ ${err.message}`);
        }
      }

      messages.push({ role: 'tool', content: result });
    }
  }

  console.log(`\n🎯 Done — ${created.length} file(s) created.`);
  created.forEach(f => console.log(`   ${f.file} → ${f.description}`));
}

run().catch(err => { console.error('Generate agent error:', err.message || err); process.exit(1); });
