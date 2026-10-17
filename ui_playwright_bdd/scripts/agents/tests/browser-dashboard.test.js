'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { main } = require('../../browser-dashboard');

test('environment counts final attempts, separates browsers and measures elapsed parallel execution', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'browser-kpi-'));
  try {
    const write = (name, value) => fs.writeFileSync(path.join(dir, name), JSON.stringify(value));
    const result = (uuid, browser, historyId, status, start, stop) => write(`${uuid}-result.json`, {
      uuid, historyId, status, start, stop, labels: browser ? [{ name: 'browser', value: browser }] : [],
    });
    result('retry', 'chromium', 'same', 'failed', 1000, 2000);
    result('final', 'chromium', 'same', 'passed', 2500, 4000);
    result('parallel', null, 'other', 'skipped', 1000, 3000);
    result('firefox', 'firefox', 'same', 'broken', 2000, 5000);
    write('hook-container.json', { children: ['parallel'], befores: [{ attachments: [{ type: 'text/plain', source: 'browser.txt' }] }] });
    fs.writeFileSync(path.join(dir, 'browser.txt'), 'Browser: chromium');
    fs.writeFileSync(path.join(dir, 'environment.properties'), 'target=staging\nchromium_total=99\n');
    const dashboard = main(dir);
    assert.equal(dashboard.chromium.total, 2);
    assert.equal(dashboard.chromium.passed, 1);
    assert.equal(dashboard.chromium.failed, 0);
    assert.equal(dashboard.chromium.skipped, 1);
    assert.equal(dashboard.chromium.retried, 1);
    assert.equal(dashboard.chromium.durationMs, 3000);
    assert.equal(dashboard.firefox.broken, 1);
    const env = fs.readFileSync(path.join(dir, 'environment.properties'), 'utf8');
    assert.match(env, /tests_execution_time=4\.000 s/);
    assert.match(env, /target=staging/);
    main(dir);
    assert.equal(fs.readFileSync(path.join(dir, 'environment.properties'), 'utf8'), env);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
