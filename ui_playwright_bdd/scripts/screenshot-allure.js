const { chromium } = require('@playwright/test');
const http = require('http');
const fs = require('fs');
const path = require('path');

const REPORT_DIR = path.resolve(__dirname, '../allure-report');
const OUT_PATH   = path.resolve(__dirname, '../docs/screenshots/allure-report.png');
const PORT = 9323;

// Serveur HTTP minimal pour servir le rapport Allure
function startServer() {
  return http.createServer((req, res) => {
    let filePath = path.join(REPORT_DIR, req.url === '/' ? '/index.html' : req.url);
    if (!fs.existsSync(filePath)) { res.writeHead(404); res.end(); return; }
    const ext = path.extname(filePath);
    const mime = { '.html':'text/html', '.js':'application/javascript', '.css':'text/css',
                   '.json':'application/json', '.png':'image/png', '.svg':'image/svg+xml' };
    res.writeHead(200, { 'Content-Type': mime[ext] || 'text/plain' });
    fs.createReadStream(filePath).pipe(res);
  }).listen(PORT);
}

(async () => {
  const server = startServer();
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1366, height: 650 });

  await page.goto(`http://localhost:${PORT}`, { waitUntil: 'networkidle', timeout: 15000 });
  await page.waitForTimeout(4000);

  fs.mkdirSync(path.dirname(OUT_PATH), { recursive: true });
  await page.screenshot({ path: OUT_PATH, fullPage: false });

  await browser.close();
  server.close();
  console.log('Screenshot saved:', OUT_PATH);
})();
