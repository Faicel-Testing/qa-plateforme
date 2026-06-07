// ============================================
// QA Agent — Ollama (local LLM)
// ============================================
// Scans the full BDD framework and uses local LLM (streaming) to produce
// a QA analysis: coverage, quality, risks, recommendations.
//
// Usage:    npm run agent:qa
// Requires: Ollama running + model pulled
// Output:   docs/QA_ANALYSIS.md  +  RAG/qa-knowledge.md
// ============================================

require('dotenv').config();
const llm  = require('./llm');
const fs   = require('fs');
const path = require('path');

const projectRoot  = path.resolve(__dirname, '../../');
const srcDir       = path.join(projectRoot, 'src');
const docsDir      = path.join(projectRoot, 'docs');
const ragDir       = path.join(projectRoot, 'RAG');
const outputAnalysis = path.join(docsDir, 'QA_ANALYSIS.md');
const outputRAG      = path.join(ragDir,  'qa-knowledge.md');

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

function buildContext() {
  const sections = [];
  const add = (label, dir, ext) => {
    const files = readDir(dir, ext);
    if (Object.keys(files).length)
      sections.push(`## ${label}\n\n` +
        Object.entries(files).map(([f, c]) => `### ${f}\n\`\`\`\n${c}\n\`\`\``).join('\n\n'));
  };
  add('Feature Files (Gherkin)',  path.join(srcDir, 'features'), '.feature');
  add('Step Definitions',         path.join(srcDir, 'steps'),    '.ts');
  add('Page Objects',             path.join(srcDir, 'pages'),    '.ts');
  add('Hooks & Setup',            path.join(srcDir, 'hooks'),    '.ts');
  add('Core (World / Driver)',    path.join(srcDir, 'core'),     '.ts');
  return sections.join('\n\n');
}

async function run() {
  await llm.assertRunning();
  console.log(`=== QA AGENT  [${llm.MODEL}] ===`);
  console.log('Scanning framework...');

  const context = buildContext();

  const messages = [
    {
      role: 'system',
      content: 'You are a senior QA architect. Produce a comprehensive, actionable analysis of BDD test frameworks.'
    },
    {
      role: 'user',
      content: `Analyze this Playwright + CucumberJS BDD framework for a Todo app.

Provide:
1. **Coverage Analysis** — what is tested, what is missing
2. **Test Quality** — strengths, weaknesses, anti-patterns
3. **Risk Areas** — insufficient coverage, flakiness risks
4. **Recommendations** — specific improvements (High/Medium/Low priority)
5. **Architecture Observations** — notable design choices

Reference actual file names and scenarios.

## Framework Source Code

${context}`
    }
  ];

  console.log('Streaming analysis...\n');
  let fullText = '';
  const stream = await llm.chatStream(messages);
  for await (const chunk of stream) {
    const text = chunk.message?.content || '';
    process.stdout.write(text);
    fullText += text;
    if (chunk.done) break;
  }
  console.log('\n');

  const ts = new Date().toISOString();
  fs.mkdirSync(docsDir, { recursive: true });
  fs.mkdirSync(ragDir,  { recursive: true });
  fs.writeFileSync(outputAnalysis, `# QA Framework Analysis\n\n_${ts} — ${llm.MODEL}_\n\n${fullText}\n`, 'utf-8');
  fs.writeFileSync(outputRAG,      `# QA Knowledge Base\n\n_${ts} — ${llm.MODEL}_\n\n${fullText}\n`, 'utf-8');

  console.log(`✅ docs/QA_ANALYSIS.md`);
  console.log(`✅ RAG/qa-knowledge.md`);
}

run().catch(err => { console.error('QA agent error:', err.message || err); process.exit(1); });
