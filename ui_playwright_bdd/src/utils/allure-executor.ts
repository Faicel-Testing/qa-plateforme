import fs from 'fs';
import path from 'path';

export function writeExecutorFile(): void {
  const resultsDir = path.resolve('allure-results');

  if (!fs.existsSync(resultsDir)) {
    fs.mkdirSync(resultsDir, { recursive: true });
  }

  const executorPath = path.join(resultsDir, 'executor.json');

  // Évite de réécrire le fichier inutilement à chaque scénario
  if (fs.existsSync(executorPath)) {
    return;
  }

  const executor = {
    name: 'Playwright Cucumber',
    type: 'local',
    buildName: `Run ${new Date().toISOString()}`,
    buildOrder: Date.now(),
    reportName: 'Playwright Cucumber Allure Report'
  };

  fs.writeFileSync(executorPath, JSON.stringify(executor, null, 2), 'utf-8');
}