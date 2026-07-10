const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  await page.goto('http://127.0.0.1:63283', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2500);
  const out = path.join(__dirname, 'screenshot-allure-report.png');
  await page.screenshot({ path: out });
  console.log('[OK] Allure report -> ' + out);
  await browser.close();
})();
