const fs = require('fs');
const path = require('path');

const HISTORY_FILE = path.resolve('allure-report/history/history.json');
const RESULTS_DIR = path.resolve('allure-results');
const OUTPUT_FILE = path.resolve('allure-results', 'flaky-retry-dashboard.txt');

function loadHistory() {
  if (!fs.existsSync(HISTORY_FILE)) {
    return {};
  }
  return JSON.parse(fs.readFileSync(HISTORY_FILE, 'utf-8'));
}

function getCurrentResults() {
  const files = fs.existsSync(RESULTS_DIR) ? fs.readdirSync(RESULTS_DIR) : [];
  const resultFiles = files.filter((f) => f.endsWith('-result.json'));

  const results = resultFiles.map((file) => {
    const content = JSON.parse(
      fs.readFileSync(path.join(RESULTS_DIR, file), 'utf-8')
    );
    return {
      name: content.name,
      status: content.status,
      historyId: content.historyId
    };
  });

  return results;
}

function isFlakyFromHistory(items) {
  if (!Array.isArray(items) || items.length < 3) {
    return false;
  }

  const recent = items.slice(-10).map((item) => item.status);
  const unique = [...new Set(recent)];

  if (!(unique.includes('passed') && unique.includes('failed'))) {
    return false;
  }

  let transitions = 0;
  for (let i = 1; i < recent.length; i++) {
    if (recent[i] !== recent[i - 1]) {
      transitions++;
    }
  }

  return transitions >= 2;
}

function main() {
  const history = loadHistory();
  const currentResults = getCurrentResults();

  let total = currentResults.length;
  let passed = 0;
  let failed = 0;
  let flakyCandidates = 0;

  const flakyNames = [];

  currentResults.forEach((result) => {
    if (result.status === 'passed') passed++;
    if (result.status === 'failed') failed++;

    const historyEntry = history[result.historyId];
    const items = historyEntry?.items || [];

    if (isFlakyFromHistory(items)) {
      flakyCandidates++;
      flakyNames.push(result.name);
    }
  });

  const report = [
    '===== FLAKY + RETRY DASHBOARD =====',
    `Total tests: ${total}`,
    `Passed: ${passed}`,
    `Failed: ${failed}`,
    `Flaky candidates: ${flakyCandidates}`,
    '',
    'Flaky test list:',
    ...(flakyNames.length ? flakyNames.map((name) => `- ${name}`) : ['- None'])
  ].join('\n');

  fs.writeFileSync(OUTPUT_FILE, report, 'utf-8');
  console.log(report);
}

main();