'use strict';
require('ts-node/register');
const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { chromium } = require('playwright');
const { LoginPage } = require('../../../src/pages/Id02_LoginPage');

test('login asserts a ready dashboard without waiting for permanent background traffic', async () => {
  const previous = process.env.BASE_URL;
  let background = 0;
  const server = http.createServer((req, res) => {
    if (req.url === '/background') { background++; res.writeHead(200, { 'Content-Type': 'text/plain' }); res.write('pending'); return; }
    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.end(`<input data-testid="email"><input data-testid="password" type="password">
      <button data-testid="submit" onclick="history.pushState({},'', '/todo'); document.body.innerHTML='<button><svg data-testid=add></svg></button>';fetch('/background');">Login</button>`);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({ headless: true });
  try {
    process.env.BASE_URL = `http://127.0.0.1:${server.address().port}`;
    const page = await browser.newPage();
    page.setDefaultNavigationTimeout(30000);
    const login = new LoginPage(page);
    await login.open();
    const start = Date.now();
    await login.login('synthetic@example.test', 'synthetic-password');
    await login.assertLoggedIn();
    assert.ok(Date.now() - start < 5000, 'Ready UI must not wait 10 seconds for networkidle');
    assert.ok(background > 0, 'The fixture must keep a real network request pending');
  } finally {
    await browser.close();
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
    if (previous === undefined) delete process.env.BASE_URL; else process.env.BASE_URL = previous;
  }
});
