const fs = require('fs');
const path = require('path');

/**
 * Écrit allure-results/environment.properties (KPIs) et categories.json
 * (classification des échecs), et sauvegarde l'historique Trend persistant.
 * Équivalent Cypress de AllureSuiteListener.java (api-Java-Rest-Assured / ui_selenium_bdd).
 * Branché sur l'événement Node 'after:run' de Cypress (setupNodeEvents).
 */
function writeCategoriesJson(resultsDir) {
  const json = [
    {
      name: 'Infrastructure Issues',
      messageRegex: '.*ECONNREFUSED.*|.*timed out.*|.*Cypress failed to start.*|.*net::ERR.*',
      matchedStatuses: ['failed', 'broken'],
    },
    {
      name: 'App Assertion Mismatches',
      messageRegex: '.*AssertionError.*|.*CypressError.*|.*expected.*to.*',
      matchedStatuses: ['failed'],
    },
    {
      name: 'Test Framework Errors',
      matchedStatuses: ['broken'],
    },
  ];
  fs.mkdirSync(resultsDir, { recursive: true });
  fs.writeFileSync(path.join(resultsDir, 'categories.json'), JSON.stringify(json, null, 2), 'utf8');
}

function writeEnvironmentProperties(resultsDir, results, config) {
  const stats = results?.totalTests != null
    ? { total: results.totalTests, passed: results.totalPassed, failed: results.totalFailed, skipped: results.totalSkipped }
    : { total: 0, passed: 0, failed: 0, skipped: 0 };

  const passRate = stats.total ? (stats.passed / stats.total) * 100 : 0;
  const failRate = stats.total ? (stats.failed / stats.total) * 100 : 0;
  const gateOk = passRate >= 90 && failRate <= 5;
  const durationSec = results?.totalDuration ? Math.round(results.totalDuration / 1000) : 0;

  const lines = [
    'Application=QACart Todo (React SPA)',
    `Application.URL=${config.baseUrl || ''}`,
    'Framework=Cypress + @badeball/cypress-cucumber-preprocessor (JavaScript)',
    `Browser=${(results?.browserName || 'electron')} ${results?.browserVersion || ''}`.trim(),
    `Environment=${process.env.NODE_ENV || 'local'}`,
    `Scenarios.Total=${stats.total}`,
    `Scenarios.Passed=${stats.passed}`,
    `Scenarios.Failed=${stats.failed}`,
    `Scenarios.Skipped=${stats.skipped}`,
    `Pass.Rate=${passRate.toFixed(1)}%`,
    `Fail.Rate=${failRate.toFixed(1)}%`,
    `Execution.Duration=${Math.floor(durationSec / 60)}m ${String(durationSec % 60).padStart(2, '0')}s`,
    `Quality.Gate=${gateOk ? 'PASSED — pass>=90% / fail<=5%' : 'FAILED'}`,
  ];

  fs.mkdirSync(resultsDir, { recursive: true });
  fs.writeFileSync(path.join(resultsDir, 'environment.properties'), lines.join('\n') + '\n', 'utf8');
}

// Sauvegarde allure-report/history/ -> allure-history/ (persistant, hors du dossier
// de rapport régénéré à chaque run), pour que le Trend Allure survive dans le temps.
function persistHistory(frameworkRoot) {
  const src = path.join(frameworkRoot, 'allure-report', 'history');
  const dest = path.join(frameworkRoot, 'allure-history');
  if (!fs.existsSync(src)) return;
  fs.mkdirSync(dest, { recursive: true });
  for (const name of fs.readdirSync(src)) {
    const s = path.join(src, name);
    if (fs.statSync(s).isFile()) fs.copyFileSync(s, path.join(dest, name));
  }
}

// Réinjecte l'historique persistant dans allure-results/history/ avant génération du rapport,
// pour que le Trend Allure survive malgré un dossier allure-results nettoyé entre les runs.
function restoreHistory(frameworkRoot, resultsDir) {
  const src = path.join(frameworkRoot, 'allure-history');
  const dest = path.join(resultsDir, 'history');
  if (!fs.existsSync(src)) return;
  fs.mkdirSync(dest, { recursive: true });
  for (const name of fs.readdirSync(src)) {
    const s = path.join(src, name);
    if (fs.statSync(s).isFile()) fs.copyFileSync(s, path.join(dest, name));
  }
}

module.exports = { writeCategoriesJson, writeEnvironmentProperties, persistHistory, restoreHistory };
