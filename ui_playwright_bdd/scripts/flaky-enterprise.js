const fs = require('fs');
const path = require('path');

const HISTORY_FILE = path.resolve('allure-report/history/history.json');

// PARAMÈTRES
const MIN_RUNS = 3;
const MAX_RUNS = 10;
const MAX_FLAKY_RATE = 2; // % max autorisé
const FAIL_ON_FLAKY = true;

function loadHistory() {
  if (!fs.existsSync(HISTORY_FILE)) {
    console.log('No history found → skipping flaky detection');
    process.exit(0);
  }
  return JSON.parse(fs.readFileSync(HISTORY_FILE, 'utf-8'));
}

function isFlaky(statuses) {
  const unique = [...new Set(statuses)];

  // doit contenir passed + failed
  if (!(unique.includes('passed') && unique.includes('failed'))) {
    return false;
  }

  // compter les transitions
  let transitions = 0;
  for (let i = 1; i < statuses.length; i++) {
    if (statuses[i] !== statuses[i - 1]) transitions++;
  }

  return transitions >= 2;
}

function main() {
  const history = loadHistory();

  let totalTests = 0;
  let flakyTests = [];

  console.log('----- FLAKY ENTERPRISE ANALYSIS -----');

  for (const [id, test] of Object.entries(history)) {
    const items = test.items || [];

    if (items.length < MIN_RUNS) continue;

    const recent = items.slice(-MAX_RUNS);
    const statuses = recent.map(i => i.status);

    totalTests++;

    if (isFlaky(statuses)) {
      flakyTests.push({
        name: test.statistic?.name || id,
        statuses
      });
    }
  }

  const flakyRate =
    totalTests === 0 ? 0 : (flakyTests.length / totalTests) * 100;

  console.log(`Total analyzed tests: ${totalTests}`);
  console.log(`Flaky tests: ${flakyTests.length}`);
  console.log(`Flaky rate: ${flakyRate.toFixed(2)}%`);

  if (flakyTests.length > 0) {
    console.log('\n⚠️ Flaky tests details:\n');

    flakyTests.forEach((t, i) => {
      console.log(`[${i + 1}] ${t.name}`);
      console.log(`    ${t.statuses.join(' -> ')}`);
    });
  }

  // QUALITY GATE
  if (flakyRate > MAX_FLAKY_RATE) {
    console.log('\n❌ Flaky rate exceeds threshold → FAIL');
    if (FAIL_ON_FLAKY) process.exit(1);
  } else {
    console.log('\n✅ Flaky rate acceptable');
  }
}

main();