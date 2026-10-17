'use strict';
const fs = require('node:fs');
const path = require('node:path');
const ROOT = path.resolve(__dirname, '../../..');
const mappings = {
  'SCRUM-5': ['Id01'], 'SCRUM-6': ['Id02', 'Id05'], 'SCRUM-9': ['Id02', 'Id05'],
  'SCRUM-7': ['Id03', 'Id09'], 'SCRUM-8': ['Id04', 'Id09'],
};
const escape = text => String(text).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
function collect(root = ROOT) {
  const trace = fs.readFileSync(path.join(root, 'docs/JIRA_TRACEABILITY.md'), 'utf8').split('## Analyse')[0];
  const stories = [...trace.matchAll(/^- \[(SCRUM-\d+)\].*?— (.+)$/gm)].map(m => ({ externalId: m[1], summary: m[2].trim(), source: 'docs/JIRA_TRACEABILITY.md' }));
  const spec = fs.readFileSync(path.join(root, 'docs/SPEC_REPORT.md'), 'utf8');
  for (const section of spec.split('### ').slice(1)) {
    const match = section.match(/^\[(Id\d+)\] (.+)/);
    if (!match) continue;
    const key = { Id06: 'SCRUM-18', Id07: 'SCRUM-19', Id08: 'SCRUM-20' }[match[1]];
    if (!key) throw Error('Unmapped historical story');
    stories.push({ externalId: key, summary: match[2].trim(), source: 'docs/SPEC_REPORT.md', original: section.split('## Tickets')[0].trim() });
  }
  const names = fs.readdirSync(path.join(root, 'src/features')).filter(n => n.endsWith('.feature'));
  return stories.map(s => {
    const prefixes = mappings[s.externalId] || [];
    const files = names.filter(n => prefixes.some(p => n.startsWith(p))).map(n => 'src/features/' + n);
    const criteria = files.flatMap(file => [...fs.readFileSync(path.join(root, file), 'utf8').matchAll(/^\s*Scenario:\s*(.+)$/gm)].map(m => m[1]));
    const domain = ['SCRUM-5','SCRUM-6','SCRUM-9'].includes(s.externalId) ? 'Authentification' : ['SCRUM-7','SCRUM-8'].includes(s.externalId) ? 'Gestion des tâches' : s.externalId === 'SCRUM-2' ? 'À clarifier' : 'Évolutions du compte';
    const note = s.externalId === 'SCRUM-9' ? 'Recouvrement historique avec SCRUM-6 : conservé pour traçabilité, à consolider par le métier.' : s.externalId === 'SCRUM-2' ? 'Titre historique non spécifié : exigences à clarifier, aucune couverture attribuée.' : !files.length ? 'Exigences historiques à confirmer ; aucun scénario exécutable actuellement associé.' : 'Couverture présente dans le dépôt ; cela ne signifie pas que les tests passent ou que la story est acceptée.';
    const html = `<h2>User story</h2><p>${escape(s.summary)}</p>${s.original ? `<pre>${escape(s.original)}</pre>` : ''}<h3>Origine et périmètre</h3><p>${escape(s.externalId)} — ${escape(s.source)}</p><p>${escape(note)}</p><h3>Critères représentés par les tests existants — à valider métier</h3><ul>${criteria.map(c => `<li>${escape(c)}</li>`).join('')}</ul><h3>Sources de tests</h3><ul>${files.map(f => `<li>${escape(f)}</li>`).join('')}</ul><p>Priorité proposée pour le tri du backlog. Aucun responsable, échéance ou engagement de livraison n'est déduit de cet import.</p>`;
    return { ...s, files, domain, note, priority: domain === 'Authentification' ? 'high' : s.externalId === 'SCRUM-2' ? 'low' : s.externalId === 'SCRUM-20' ? 'urgent' : s.externalId === 'SCRUM-18' ? 'high' : 'medium', description_html: html };
  });
}
function filesFor(story, root = ROOT) {
  const match = collect(root).find(s => s.externalId === story.externalId || String(story.summary || '').startsWith(`[${s.externalId}]`));
  if (!match?.files.length) throw Error('No reviewed executable feature mapping for this Plane story');
  return match.files;
}
async function importStoriesCore(plane, { dryRun = false, root = ROOT } = {}) {
  const stories = collect(root);
  if (dryRun) return stories.map(s => ({ key: s.externalId, title: s.summary, module: s.domain, priority: s.priority, files: s.files }));
  const project = await plane.request(), states = await plane.list('states/');
  const state = states.find(s => s.group === 'backlog') || states.find(s => s.group === 'unstarted');
  if (!state) throw Error('No backlog/unstarted state: import stopped');
  const labels = await plane.list('labels/'), modules = await plane.list('modules/'), existing = await plane.list('work-items/');
  async function ensure(rows, route, name, body) {
    const found = rows.find(r => r.name === name);
    if (found) return found;
    const created = await plane.request(route, 'POST', { name, ...body }); rows.push(created); return created;
  }
  const result = [];
  for (const story of stories) {
    const matches = existing.filter(i => i.external_source === 'ui_playwright_bdd' && i.external_id === story.externalId);
    if (matches.length > 1) throw Error('Duplicate external identifiers in Plane; resolve manually');
    let item = matches[0];
    if (!item) {
      const label = await ensure(labels, 'labels/', 'User story', { color: '#2563eb' });
      const coverage = await ensure(labels, 'labels/', story.files.length ? 'Tests disponibles' : 'À clarifier', { color: '#0d9488' });
      item = await plane.request('work-items/', 'POST', { name: `[${story.externalId}] ${story.summary}`, description_html: story.description_html,
        priority: story.priority, state: state.id, labels: [label.id, coverage.id], assignees: [],
        external_source: 'ui_playwright_bdd', external_id: story.externalId });
      existing.push(item);
    }
    const module = await ensure(modules, 'modules/', story.domain, { description: 'Stories importées depuis ui_playwright_bdd ; validation métier à effectuer.', status: 'backlog' });
    const members = await plane.list(`modules/${module.id}/module-issues/`);
    if (!members.some(m => m.issue === item.id || m.issue?.id === item.id || m.id === item.id)) await plane.request(`modules/${module.id}/module-issues/`, 'POST', { issues: [item.id] });
    result.push({ externalId: story.externalId, id: item.id, key: `${project.identifier}-${item.sequence_id}`, module: module.name, files: story.files, created: !matches.length });
    fs.mkdirSync(path.join(root, 'logs/plane'), { recursive: true });
    fs.writeFileSync(path.join(root, 'logs/plane/import.json'), JSON.stringify({ projectId: plane.cfg.project, stories: result }, null, 2));
  }
  return result;
}
async function importStories(plane, options = {}) {
  if (options.dryRun) return importStoriesCore(plane, options);
  const dir = path.join(options.root || ROOT, 'logs/plane');
  fs.mkdirSync(dir, { recursive: true });
  const lock = path.join(dir, 'import.lock');
  let handle;
  try { handle = fs.openSync(lock, 'wx'); } catch { throw Error('Plane import already running or lock unavailable'); }
  try { return await importStoriesCore(plane, options); }
  finally { fs.closeSync(handle); fs.unlinkSync(lock); }
}
module.exports = { collect, filesFor, importStories };
