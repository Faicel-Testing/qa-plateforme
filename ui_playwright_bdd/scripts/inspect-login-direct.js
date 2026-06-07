const { chromium } = require('playwright');
(async () => {
  console.log('script start');
  const browser = await chromium.launch();
  console.log('browser launched');
  const context = await browser.newContext();
  const page = await context.newPage();
  console.log('navigator created');
  await page.goto('https://qacart-todo.herokuapp.com', { waitUntil: 'domcontentloaded', timeout: 60000 });
  console.log('page loaded');
  const title = await page.title();
  console.log('TITLE=' + title);
  const html = await page.content();
  console.log('HTML_LEN=' + html.length);
  await browser.close();
  console.log('browser closed');
})();
