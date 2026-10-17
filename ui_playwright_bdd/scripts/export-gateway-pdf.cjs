const { chromium } = require('playwright');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
(async () => {
  const directory = path.resolve(__dirname, '../docs/preparation');
  const deepEval = process.argv.includes('--deepeval');
  const stem = deepEval ? 'deepeval' : 'gateway';
  const pdfName = deepEval ? 'architecture-deepeval-client.pdf' : 'architecture-gateway-ia-client.pdf';
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 900, height: 1200 }, deviceScaleFactor: 1 });
    await page.goto(pathToFileURL(path.join(directory, `${stem}-client.html`)).href);
    await page.emulateMedia({ media: 'print' });
    const checks = await page.locator('.page').evaluateAll(pages => pages.map((p, i) => {
      const footer = p.querySelector('.footer').getBoundingClientRect();
      const content = [...p.children].filter(c => !c.classList.contains('footer'));
      return { page: i + 1, fits: content.every(c => c.getBoundingClientRect().bottom < footer.top), overflow: p.scrollHeight > p.clientHeight };
    }));
    if (checks.some(c => !c.fits || c.overflow)) throw Error(JSON.stringify(checks));
    await page.pdf({ path: path.join(directory, pdfName), preferCSSPageSize: true, printBackground: true });
    for (let i = 0; i < 4; i++) await page.locator('.page').nth(i).screenshot({ path: path.join(directory, `${stem}-preview-${i + 1}.png`) });
    console.log(JSON.stringify({ pdf: `docs/preparation/${pdfName}`, checks }));
  } finally { await browser.close(); }
})().catch(e => { console.error(e.message); process.exitCode = 1; });
