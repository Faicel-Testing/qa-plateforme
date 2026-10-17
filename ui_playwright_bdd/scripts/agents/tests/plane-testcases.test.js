'use strict';
const test = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), os = require('node:os');
const { plan, sync } = require('../shared/plane-testcases');
test('mapping covers all 29 scenarios, includes background and separates API add/delete', () => {
  const cases = plan(); assert.equal(cases.length, 38);
  assert.equal(new Set(cases.map(c => c.file + c.name)).size, 29);
  assert.equal(new Set(cases.map(c => c.externalId)).size, 38);
  const api = cases.filter(c => c.file.includes('Id09'));
  assert.ok(api.every(c => c.steps[0] === 'Given I have a user created via API'));
  assert.ok(api.filter(c => /add todo/.test(c.name)).every(c => c.story === 'SCRUM-7'));
  assert.ok(api.filter(c => /delete todo/.test(c.name)).every(c => c.story === 'SCRUM-8'));
});
test('children preserve parent and repeated import creates no duplicates or edits', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'plane-cases-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const source = path.resolve(__dirname, '../../..');
  for (const dir of ['docs', 'src/features']) fs.mkdirSync(path.join(root, dir), { recursive: true });
  for (const name of ['JIRA_TRACEABILITY.md','SPEC_REPORT.md']) fs.copyFileSync(path.join(source,'docs',name), path.join(root,'docs',name));
  for (const name of fs.readdirSync(path.join(source,'src/features'))) if (name.endsWith('.feature')) fs.copyFileSync(path.join(source,'src/features',name),path.join(root,'src/features',name));
  const items = ['SCRUM-5','SCRUM-6','SCRUM-7','SCRUM-8','SCRUM-9'].map((external_id,i) => ({ external_id, external_source: 'ui_playwright_bdd', id: 'parent-'+i, sequence_id: i+1 }));
  const labels = []; let writes = 0;
  const plane = { request: async (route, method, body) => {
    if (!route) return { identifier: 'QA' };
    assert.equal(method, 'POST'); writes++;
    const item = { ...body, id: 'item-'+writes, sequence_id: 10+writes };
    (route === 'labels/' ? labels : items).push(item); return item;
  }, list: async route => route === 'work-items/' ? [...items] : route === 'labels/' ? [...labels] : [{ id:'backlog', group:'backlog' }] };
  assert.equal((await sync(plane,{root})).missing,38); assert.equal(writes,0);
  const first = await sync(plane,{root,apply:true}); assert.equal(first.created,38); assert.equal(first.verified,true);
  items[5].name = 'Human edited'; const before = writes;
  const second = await sync(plane,{root,apply:true}); assert.equal(second.created,0); assert.equal(writes,before); assert.equal(items[5].name,'Human edited');
});
