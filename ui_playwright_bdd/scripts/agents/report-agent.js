// ============================================
// Report Agent — Ollama (local LLM)
// ============================================
// Reads allure results, uses local LLM (streaming) to generate a
// professional test execution report with root cause analysis.
//
// Usage:    npm run agent:report
// Requires: Ollama running + model pulled + tests run
// Output:   docs/LATEST_TEST_REPORT.md
// ============================================

require('dotenv').config();
const llm  = require('./llm');
const fs   = require('fs');
const path = require('path');

const projectRoot   = path.resolve(__dirname, '../../');
const summaryPath   = path.join(projectRoot, 'allure-report/widgets/summary.json');
const resultsDir    = path.join(projectRoot, 'allure-results');
const bugAnalysisPath = path.join(projectRoot, 'docs/BUG_ANALYSIS.md');
const outputPath    = path.join(projectRoot, 'docs/LATEST_TEST_REPORT.md');

function loadResults() {
  if (!fs.existsSync(resultsDir)) return [];
  return fs.readdirSync(resultsDir)
    .filter(f => f.endsWith('-result.json'))
    .map(f => { try { return JSON.parse(fs.readFileSync(path.join(resultsDir, f), 'utf-8')); } catch { return null; } })
    .filter(Boolean);
}

async function run() {
  await llm.assertRunning();
  console.log(`=== REPORT AGENT  [${llm.MODEL}] ===`);

  const allResults = loadResults();
  const summary    = fs.existsSync(summaryPath) ? JSON.parse(fs.readFileSync(summaryPath, 'utf-8')) : null;
  const failures   = allResults.filter(r => r.status === 'failed' || r.status === 'broken')
    .map(r => ({ name: r.name, status: r.status, error: r.statusDetails?.message || '', duration_ms: r.time?.duration || 0 }));
  const bugAnalysis = fs.existsSync(bugAnalysisPath) ? fs.readFileSync(bugAnalysisPath, 'utf-8').slice(0, 2000) : null;
  const slowest = allResults.filter(r => r.time?.duration).sort((a, b) => b.time.duration - a.time.duration).slice(0, 5)
    .map(r => `- ${r.name}: ${(r.time.duration / 1000).toFixed(2)}s [${r.status}]`).join('\n');

  if (!summary && !allResults.length) {
    console.error('No test data. Run: npm run test:allure && npm run allure:generate');
    process.exit(1);
  }

  const stats = summary?.statistic || {
    total: allResults.length,
    passed: allResults.filter(r => r.status === 'passed').length,
    failed: failures.length
  };

  const dataContext = [
    `## Statistics\n\`\`\`json\n${JSON.stringify(stats, null, 2)}\n\`\`\``,
    failures.length ? `## Failures\n\`\`\`json\n${JSON.stringify(failures, null, 2)}\n\`\`\`` : '## Failures\nNone.',
    slowest ? `## Top 5 Slowest\n${slowest}` : '',
    bugAnalysis ? `## Bug Analysis Summary\n${bugAnalysis}` : ''
  ].filter(Boolean).join('\n\n');

  const messages = [
    {
      role: 'system',
      content: 'You are a QA reporting expert. Generate professional, clear, actionable Markdown reports.'
    },
    {
      role: 'user',
      content: `Generate a professional test execution report in Markdown.

Structure:
## Executive Summary
- Health: 🟢 all pass / 🟡 some fail / 🔴 critical failures
- Pass rate, key metrics table

## Test Results
- Results by status (table)
- Duration stats

## Failure Analysis
- Each failure: name, error, suspected root cause

## Performance
- Slowest tests

## Recommendations
- Next steps by priority

## Test Data
${dataContext}`
    }
  ];

  console.log('Streaming report...\n');
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
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, `# Test Execution Report\n\n_${ts} — ${llm.MODEL}_\n\n${fullText}\n`, 'utf-8');
  console.log(`✅ docs/LATEST_TEST_REPORT.md`);
}

run().catch(err => { console.error('Report agent error:', err.message || err); process.exit(1); });
