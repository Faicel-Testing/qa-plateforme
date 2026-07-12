// Capture d'écran du dashboard k6 natif (fichier HTML autonome, pas de serveur requis).
// Réutilise le Playwright déjà installé dans ui_playwright_bdd (aucune dépendance ajoutée ici).
const { chromium } = require(require('path').resolve(__dirname, '..', '..', 'ui_playwright_bdd', 'node_modules', 'playwright'));
const path = require('path');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  const target = path.join(__dirname, '..', 'reports', 'dashboard-load.html');
  await page.goto('file://' + target.replace(/\\/g, '/'), { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  const out = path.join(__dirname, 'screenshot-dashboard.png');
  await page.screenshot({ path: out });
  console.log('[OK] k6 dashboard -> ' + out);
  await browser.close();
})();
