const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto('https://qacart-todo.herokuapp.com/signup', { waitUntil: 'domcontentloaded', timeout: 60000 });
  const buttons = await page.$$eval('button', els => els.map(e => ({ text: e.textContent?.trim(), type: e.getAttribute('type'), id: e.id, class: e.className }))); 
  console.log(JSON.stringify(buttons, null, 2));
  const anchors = await page.$$eval('a', els => els.map(e => ({ text: e.textContent?.trim(), href: e.href }))); 
  console.log('anchors', JSON.stringify(anchors, null, 2));
  await browser.close();
})();
