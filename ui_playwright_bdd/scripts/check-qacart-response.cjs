'use strict';
// One synthetic registration; prints response field names/types, never values.
require('dotenv').config({ quiet: true });
require('ts-node/register');
const { request } = require('@playwright/test');
const { randomUser } = require('../src/support/testData');
(async () => {
  const ctx = await request.newContext({ baseURL: process.env.BASE_URL || 'https://qacart-todo.herokuapp.com', ignoreHTTPSErrors: true });
  try {
    const response = await ctx.post('/api/v1/users/register', { data: randomUser(), timeout: 30000, maxRetries: 0 });
    const body = await response.json();
    console.log(JSON.stringify({ status: response.status(), fields: Object.entries(body).map(([name, value]) => ({ name, type: typeof value })) }));
  } finally { await ctx.dispose(); }
})().catch(() => { console.error('API contract probe unavailable; no response content printed.'); process.exitCode = 1; });
