const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto('https://qacart-todo.herokuapp.com', { waitUntil: 'networkidle' });
  const url = page.url();
  const title = await page.title();
  const inputs = await page.$$eval('input', els => els.map(e => ({ name: e.getAttribute('name'), type: e.getAttribute('type'), placeholder: e.getAttribute('placeholder'), ariaLabel: e.getAttribute('aria-label'), id: e.id, class: e.className })));
  const buttons = await page.$$eval('button', els => els.map(e => ({ text: e.textContent?.trim(), type: e.getAttribute('type'), id: e.id, class: e.className })));
  console.log('URL=' + url);
  console.log('TITLE=' + title);
  console.log('INPUTS=' + JSON.stringify(inputs, null, 2));
  console.log('BUTTONS=' + JSON.stringify(buttons, null, 2));
  await browser.close();
})();
