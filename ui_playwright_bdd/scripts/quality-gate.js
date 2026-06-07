const fs = require('fs');
const path = require('path');

const RESULTS_DIR = path.resolve('allure-results');

// Seuils (tu peux adapter)
const MIN_PASS_RATE = 95; // %
const MAX_FAILED = 0;

function getResults() {
  const files = fs.readdirSync(RESULTS_DIR);
  const resultFiles = files.filter(f => f.endsWith('-result.json'));

  let total = 0;
  let passed = 0;
  let failed = 0;

  resultFiles.forEach(file => {
    const content = JSON.parse(
      fs.readFileSync(path.join(RESULTS_DIR, file))
    );

    total++;

    if (content.status === 'passed') passed++;
    if (content.status === 'failed') failed++;
  });

  return { total, passed, failed };
}

function runQualityGate() {
  const { total, passed, failed } = getResults();

  const passRate = (passed / total) * 100;

  console.log('----- QUALITY GATE -----');
  console.log(`Total: ${total}`);
  console.log(`Passed: ${passed}`);
  console.log(`Failed: ${failed}`);
  console.log(`Pass Rate: ${passRate.toFixed(2)}%`);

  if (passRate < MIN_PASS_RATE || failed > MAX_FAILED) {
    console.log('❌ QUALITY GATE FAILED');
    process.exit(1);
  } else {
    console.log('✅ QUALITY GATE PASSED');
  }
}

runQualityGate();