const { chromium } = require('playwright');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 980 }, deviceScaleFactor: 1 });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(pathToFileURL(path.join(__dirname, 'architecture-playwright-bdd-ia.html')).href);
    await page.locator('#next').click();
    if (!(await page.locator('#slide-2').evaluate(el => el.classList.contains('current')))) throw new Error('Navigation inactive');
    await page.locator('#play').click();
    if (await page.locator('.active-card').count() !== 1) throw new Error('Animation inactive');
    await page.locator('#play').click();
    await page.locator('#pages').selectOption({ label: '14. Les questions probables du client' });
    await page.locator('#answers').click();
    if (await page.locator('details[open]').count() !== 8) throw new Error('Reponses absentes');
    await page.locator('#pages').selectOption('5');
    await page.screenshot({ path: path.join(__dirname, 'apercu-harness.png'), animations: 'disabled' });
    await page.emulateMedia({ media: 'print' });
    await page.evaluate(() => document.querySelectorAll('details').forEach(el => el.open = true));
    const overflow = await page.evaluate(() => [...document.querySelectorAll('.slide')].map((el, i) => {
      const footer = el.querySelector('footer').getBoundingClientRect();
      const content = [...el.children].filter(c => c.tagName !== 'FOOTER');
      const bottom = Math.max(...content.map(c => c.getBoundingClientRect().bottom));
      return { page: i + 1, overflow: Math.round(bottom - footer.top), scroll: el.scrollHeight - el.clientHeight };
    }).filter(x => x.overflow > -5 || x.scroll > 2));
    if (errors.length || overflow.length) throw new Error(JSON.stringify({ errors, overflow }));
    await page.locator('#slide-5').screenshot({ path: path.join(__dirname, 'apercu-agents.png'), animations: 'disabled' });
    await page.locator('#slide-14').screenshot({ path: path.join(__dirname, 'apercu-entretien.png'), animations: 'disabled' });
    await page.locator('#slide-8').screenshot({ path: path.join(__dirname, 'apercu-chunks.png'), animations: 'disabled' });
    await page.locator('#slide-9').screenshot({ path: path.join(__dirname, 'apercu-top-k.png'), animations: 'disabled' });
    await page.pdf({ path: path.join(__dirname, 'architecture-playwright-bdd-ia.pdf'), printBackground: true, preferCSSPageSize: true, tagged: true, outline: true });
    console.log(JSON.stringify({ pages: await page.locator('.slide').count(), javascriptErrors: errors.length, overflow, navigation: 'OK', animation: 'OK', quiz: 'OK', pdf: 'architecture-playwright-bdd-ia.pdf' }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
