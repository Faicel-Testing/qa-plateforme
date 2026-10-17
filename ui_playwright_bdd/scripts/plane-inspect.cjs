require('dotenv').config({ quiet: true });
(async () => {
  const p = require('./agents/plane-fetcher').client();
  const project = await p.request();
  console.log(JSON.stringify({ project: { id: project.id, name: project.name, identifier: project.identifier, issue_types: project.is_issue_type_enabled } }));
  for (const route of ['states/', 'labels/', 'modules/', 'work-items/', 'issue-types/']) {
    try { const rows = await p.list(route); console.log(JSON.stringify({ route, count: rows.length, items: rows.map(r => ({ id: r.id, name: r.name, group: r.group, sequence_id: r.sequence_id, external_id: r.external_id })) })); }
    catch (e) { console.log(JSON.stringify({ route, error: e.message })); }
  }
})().catch(e => { console.error(e.message); process.exitCode = 1; });
