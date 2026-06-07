const fs = require('fs');
const path = require('path');

const RESULTS_DIR = path.resolve('allure-results');
const HISTORY_FILE = path.resolve('allure-report/history/history-trend.json');

// Seuil de tolérance
const MAX_DROP = 5; // % de baisse autorisée

function getCurrentStats() {
  const files = fs.readdirSync(RESULTS_DIR);
  const resultFiles = files.filter(f => f.endsWith('-result.json'));

  let total = 0;
  let passed = 0;

  resultFiles.forEach(file => {
    const content = JSON.parse(
      fs.readFileSync(path.join(RESULTS_DIR, file))
    );

    total++;
    if (content.status === 'passed') passed++;
  });

  const passRate = (passed / total) * 100;
  return { total, passed, passRate };
}

function getPreviousPassRate() {
  if (!fs.existsSync(HISTORY_FILE)) {
    console.log('No history found → first run');
    return null;
  }

  const history = JSON.parse(fs.readFileSync(HISTORY_FILE));
  const last = history[history.length - 1];

  return last?.data?.passed / last?.data?.total * 100;
}

function runTrendGate() {
  const current = getCurrentStats();
  const previousRate = getPreviousPassRate();

  console.log('----- TREND QUALITY GATE -----');
  console.log(`Current Pass Rate: ${current.passRate.toFixed(2)}%`);

  if (previousRate === null) {
    console.log('⚠️ No previous data → skipping trend gate');
    return;
  }

  console.log(`Previous Pass Rate: ${previousRate.toFixed(2)}%`);

  const delta = current.passRate - previousRate;

  console.log(`Delta: ${delta.toFixed(2)}%`);

  if (delta < -MAX_DROP) {
    console.log('❌ QUALITY REGRESSION DETECTED');
    process.exit(1);
  } else {
    console.log('✅ Trend OK');
  }
}

runTrendGate();