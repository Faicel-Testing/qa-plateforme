'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const fs = require('node:fs'), path = require('node:path'), os = require('node:os');
const { client } = require('../plane-fetcher');
const { collect, filesFor, importStories } = require('../shared/plane-stories');
const env = { PLANE_WORKSPACE: 'test', PLANE_PROJECT_ID: 'a1cd9e82-915a-4dc9-9fd9-69441c41ebdb', PLANE_API_KEY: 'synthetic-plane-token' };
test('Plane paginates and never sends credentials to another origin or follows redirects', async () => {
  let calls = 0;
  const transport = (opts, callback) => {
    assert.equal(opts.hostname, 'api.plane.so'); assert.equal(opts.rejectUnauthorized, true);
    const req = new EventEmitter(); req.setTimeout = () => {}; req.write = () => {};
    req.end = () => { const response = new EventEmitter(); response.statusCode = 200; callback(response);
      response.emit('data', JSON.stringify({ results: [{ id: ++calls }], next_page_results: calls === 1, next_cursor: 'next' })); response.emit('end'); };
    return req;
  };
  const plane = client(env, transport);
  assert.equal((await plane.list('work-items/')).length, 2);
  await assert.rejects(plane.request('https://evil.test/'), /Invalid Plane route/);
  await assert.rejects(plane.request('../secret'), /Invalid Plane route/);
});
test('historic stories retain provenance; undocumented features cannot be executed', () => {
  const stories = collect(); assert.equal(stories.length, 9);
  assert.equal(new Set(stories.map(s => s.externalId)).size, 9);
  assert.ok(filesFor({ externalId: 'SCRUM-5' }).every(f => f.startsWith('src/features/Id01')));
  assert.throws(() => filesFor({ externalId: 'SCRUM-18' }), /No reviewed/);
  assert.ok(stories.find(s => s.externalId === 'SCRUM-9').note.includes('SCRUM-6'));
});
test('Plane refuses redirect and authentication errors without exposing the response body', async () => {
  for (const status of [302, 401, 403, 429, 500]) {
    let calls = 0;
    const transport = (opts, callback) => {
      calls++;
      const req = new EventEmitter(); req.setTimeout = () => {};
      req.end = () => { const res = new EventEmitter(); res.statusCode = status; callback(res); res.emit('data', 'private-response-body'); res.emit('end'); };
      return req;
    };
    await assert.rejects(client(env, transport).request(), error => error.message.includes('HTTP ' + status) && !error.message.includes('private-response-body'));
    assert.equal(calls, 1);
  }
});
test('import is repeatable without overwriting manually edited stories', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'plane-import-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const source = path.resolve(__dirname, '../../..');
  for (const folder of ['docs', 'src/features']) fs.mkdirSync(path.join(root, folder), { recursive: true });
  for (const name of ['JIRA_TRACEABILITY.md', 'SPEC_REPORT.md']) fs.copyFileSync(path.join(source, 'docs', name), path.join(root, 'docs', name));
  for (const name of fs.readdirSync(path.join(source, 'src/features'))) if (name.endsWith('.feature')) fs.copyFileSync(path.join(source, 'src/features', name), path.join(root, 'src/features', name));
  const tables = { 'states/': [{ id: 'backlog', group: 'backlog' }], 'labels/': [], 'modules/': [], 'work-items/': [] };
  let writes = 0;
  const plane = { cfg: { project: 'test' }, list: async route => [...(tables[route] || [])], request: async (route, method, body) => {
    if (!route) return { identifier: 'QA' };
    assert.equal(method, 'POST'); writes++;
    if (route.includes('module-issues')) { tables[route] = body.issues.map(issue => ({ issue })); return {}; }
    const item = { ...body, id: 'id-' + writes, sequence_id: writes }; tables[route].push(item); return item;
  } };
  // The fake module relation supports multiple members, like the actual API.
  const request = plane.request;
  plane.request = async (route, method, body) => {
    if (route?.includes('module-issues')) { writes++; tables[route] = [...(tables[route] || []), ...body.issues.map(issue => ({ issue }))]; return {}; }
    return request(route, method, body);
  };
  await importStories(plane, { root });
  assert.equal(tables['work-items/'].length, 9);
  tables['work-items/'][0].name = 'Human edited title';
  const before = writes;
  const again = await importStories(plane, { root });
  assert.equal(writes, before); assert.ok(again.every(s => !s.created));
  assert.equal(tables['work-items/'][0].name, 'Human edited title');
});
