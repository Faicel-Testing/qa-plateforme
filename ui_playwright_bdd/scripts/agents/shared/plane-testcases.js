'use strict';
const fs = require('node:fs'), path = require('node:path'), { createHash } = require('node:crypto');
const { generateMessages } = require('@cucumber/gherkin');
const { IdGenerator, SourceMediaType } = require('@cucumber/messages');
const { collect } = require('./plane-stories');
const ROOT = path.resolve(__dirname, '../../..');
const SOURCE = 'ui_playwright_bdd_testcase';
const esc = text => String(text).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
function scenarios(file, root = ROOT) {
  const content = fs.readFileSync(path.join(root, file), 'utf8');
  const messages = generateMessages(content, file, SourceMediaType.TEXT_X_CUCUMBER_GHERKIN_PLAIN, { newId: IdGenerator.incrementing(), includeGherkinDocument: true, includePickles: true, includeSource: false });
  if (messages.some(m => m.parseError)) throw Error('Invalid feature: ' + file);
  const nodes = new Map();
  function visit(v) { if (!v || typeof v !== 'object') return; if (v.id) nodes.set(v.id, v); for (const child of Object.values(v)) if (typeof child === 'object') { if (Array.isArray(child)) child.forEach(visit); else visit(child); } }
  messages.filter(m => m.gherkinDocument).forEach(m => visit(m.gherkinDocument));
  return messages.filter(m => m.pickle).map(({ pickle }) => {
    const steps = pickle.steps.map(s => {
      const node = nodes.get(s.astNodeIds[0]);
      let line = `${node?.keyword || ''}${s.text}`;
      if (s.argument?.docString) line += '\n"""\n' + s.argument.docString.content + '\n"""';
      if (s.argument?.dataTable) line += '\n' + s.argument.dataTable.rows.map(r => '| ' + r.cells.map(c => c.value).join(' | ') + ' |').join('\n');
      return line;
    });
    return { name: pickle.name, file, line: nodes.get(pickle.astNodeIds[0])?.location?.line, steps, tags: pickle.tags.map(t => t.name) };
  });
}
function plan(root = ROOT) {
  const items = [];
  for (const story of collect(root)) for (const file of story.files) for (const scenario of scenarios(file, root)) {
    // Shared API setup file: attach each action to its actual functional story.
    if (file.includes('Id09_') && ((story.externalId === 'SCRUM-7' && /delete todo/.test(scenario.name)) || (story.externalId === 'SCRUM-8' && /add todo/.test(scenario.name)))) continue;
    const hash = createHash('sha256').update(JSON.stringify([file, scenario.name, scenario.steps])).digest('hex');
    // Steps affect the snapshot hash, but not the identity of an existing test case.
    const identity = createHash('sha256').update(JSON.stringify([file, scenario.name])).digest('hex');
    const externalId = `${story.externalId}:${identity}`;
    if (items.some(i => i.externalId === externalId)) throw Error('Ambiguous scenario identity: ' + scenario.name);
    items.push({ ...scenario, story: story.externalId, externalId, hash });
  }
  return items;
}
async function sync(plane, { apply = false, root = ROOT } = {}) {
  const planned = plan(root);
  const project = await plane.request(), existing = await plane.list('work-items/');
  const parents = new Map();
  for (const row of planned) {
    const matches = existing.filter(i => i.external_source === 'ui_playwright_bdd' && i.external_id === row.story);
    if (matches.length !== 1) throw Error('Missing or ambiguous parent story: ' + row.story);
    parents.set(row.story, matches[0]);
    const duplicates = existing.filter(i => i.external_source === SOURCE && i.external_id === row.externalId);
    if (duplicates.length > 1 || (duplicates.length && duplicates[0].parent !== matches[0].id)) throw Error('Duplicate or conflicting test case parent');
  }
  if (!apply) return { total: planned.length, stories: [...parents].map(([story, p]) => ({ story, key: `${project.identifier}-${p.sequence_id}`, count: planned.filter(t => t.story === story).length })), missing: planned.filter(t => !existing.some(i => i.external_source === SOURCE && i.external_id === t.externalId)).length };
  const dir = path.join(root, 'logs/plane'); fs.mkdirSync(dir, { recursive: true });
  const lock = path.join(dir, 'testcases.lock'); let fd;
  try { fd = fs.openSync(lock, 'wx'); } catch { throw Error('Test case import already running or lock unavailable'); }
  try {
    const states = await plane.list('states/');
    const state = states.find(s => s.group === 'backlog') || states.find(s => s.group === 'unstarted');
    if (!state) throw Error('No initial state available');
    const labels = await plane.list('labels/');
    let label = labels.find(l => l.name === 'Test case');
    if (!label) label = await plane.request('labels/', 'POST', { name: 'Test case', color: '#9333ea' });
    const report = [];
    for (const row of planned) {
      const parent = parents.get(row.story);
      let item = existing.find(i => i.external_source === SOURCE && i.external_id === row.externalId);
      const created = !item;
      if (!item) {
        const html = `<h2>Cas de test automatisé</h2><p>Source : ${esc(row.file)}:${row.line || ''}</p><p>User story : ${esc(row.story)} / ${esc(project.identifier)}-${parent.sequence_id}</p><p>Tags : ${esc(row.tags.join(' '))}</p><h3>Préconditions et étapes Gherkin</h3><p>Les étapes du Background, si présent, sont incluses ci-dessous.</p><pre>${esc(row.steps.join('\n'))}</pre><p>Les étapes Then/And définissent les résultats attendus. Statut d'exécution : non évalué par cet import. Aucune réussite n'est déduite de la présence du scénario.</p><p>Empreinte de la source : ${row.hash}</p>`;
        item = await plane.request('work-items/', 'POST', { name: `[TC] ${row.name}`.slice(0,255), parent: parent.id, description_html: html, state: state.id, priority: parent.priority || 'none', labels: [label.id], assignees: [], external_source: SOURCE, external_id: row.externalId });
        existing.push(item);
      }
      if (item.parent !== parent.id) throw Error('Plane did not persist the required parent');
      report.push({ story: row.story, parentKey: `${project.identifier}-${parent.sequence_id}`, key: `${project.identifier}-${item.sequence_id}`, id: item.id, externalId: row.externalId, file: row.file, scenario: row.name, created });
      fs.writeFileSync(path.join(dir, 'testcases-import.json'), JSON.stringify(report, null, 2));
    }
    const verified = await plane.list('work-items/');
    if (!report.every(r => verified.some(i => i.id === r.id && i.parent === parents.get(r.story).id))) throw Error('Remote verification failed');
    return { total: report.length, created: report.filter(r => r.created).length, preserved: report.filter(r => !r.created).length, verified: true, stories: [...parents].map(([story, p]) => ({ story, key: `${project.identifier}-${p.sequence_id}`, count: report.filter(r => r.story === story).length })) };
  } finally { fs.closeSync(fd); fs.unlinkSync(lock); }
}
module.exports = { scenarios, plan, sync, SOURCE };
