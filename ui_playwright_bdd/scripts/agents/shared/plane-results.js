'use strict';
const fs = require('node:fs'), path = require('node:path');
const { plan, SOURCE } = require('./plane-testcases');
const ROOT = path.resolve(__dirname, '../../..');
const LABELS = { FAILED: ['01 · QA FAILED', '#dc2626'], ERROR: ['02 · QA ERROR', '#ea580c'], SKIPPED: ['03 · QA SKIPPED', '#ca8a04'], NOT_RUN: ['04 · QA NON EXÉCUTÉ', '#64748b'], PASS: ['05 · QA PASS', '#16a34a'] };
const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]));
function snapshot(directory) {
  const manifest = JSON.parse(fs.readFileSync(path.join(directory, 'run-manifest.json'), 'utf8'));
  if (!manifest.completed || manifest.timedOut || manifest.error || !manifest.runId || !Number.isFinite(manifest.startedAt) || !Number.isFinite(manifest.finishedAt) || manifest.finishedAt < manifest.startedAt) throw Error('Plane sync requires a completed, timestamped run manifest');
  const results = fs.readdirSync(directory).filter(n => n.endsWith('-result.json')).map(n => JSON.parse(fs.readFileSync(path.join(directory,n),'utf8')));
  if (!results.length || results.length !== manifest.resultCount) throw Error('Plane sync result count mismatch');
  const groups = new Map();
  for (const result of results) {
    if (typeof result.fullName !== 'string' || !Number.isFinite(result.start) || !Number.isFinite(result.stop) || result.start < manifest.startedAt - 5000 || result.stop > manifest.finishedAt + 5000 || result.stop < result.start) throw Error('Allure result outside selected run or missing identity');
    const key = result.fullName.replace(/\\/g, '/');
    const values = groups.get(key) || []; values.push(result.status); groups.set(key, values);
  }
  return { manifest, groups };
}
function statusFor(values) {
  if (!values?.length) return 'NOT_RUN';
  if (values.some(s => !['passed','failed','skipped'].includes(s))) return 'ERROR';
  if (values.includes('failed')) return 'FAILED';
  if (values.includes('skipped')) return 'SKIPPED';
  return 'PASS';
}
function block(row, status, manifest, values) {
  const date = new Date(manifest.finishedAt).toLocaleString('fr-FR', { timeZone:'Europe/Paris' });
  return `<p>QA_RESULT_START</p><h2>Dernier run synchronisé : ${status}</h2><p>Date : ${esc(date)} (Europe/Paris). Run : ${esc(manifest.runId)}.</p><p>Périmètre : ${esc(manifest.tags || 'suite sélectionnée')}. ${status === 'NOT_RUN' ? 'Ce scénario ne figure pas dans ce run ; aucun ancien résultat n’est présenté comme actuel.' : `${values.length} résultat(s) Allure associé(s). Toutes les tentatives/configurations sont prises en compte : un échec n’est pas masqué par une réussite.`}</p><p>Source : ${esc(row.file)}. Rapport local : allure-runs/${esc(manifest.runId)}/report/index.html (si généré). Ouvrir avec npm.cmd run allure:open pour le dernier run local.</p><p>Résultat historique de cette exécution uniquement ; ne valide pas les modifications de code ultérieures ni la livraison.</p><p>QA_RUN_TIMESTAMP:${manifest.finishedAt}</p><p>QA_RESULT_END</p>`;
}
async function syncResults(plane, directory, { apply = false, root = ROOT, pace = 0 } = {}) {
  const { manifest, groups } = snapshot(directory);
  const rows = plan(root);
  const items = await plane.list('work-items/');
  const updates = rows.map(row => {
    const found = items.filter(i => i.external_source === SOURCE && i.external_id === row.externalId);
    if (found.length !== 1) throw Error('Missing or ambiguous Plane test case: ' + row.name);
    const item = found[0], values = groups.get(row.file + '#' + row.name) || [];
    const old = String(item.description_html || '').match(/QA_RUN_TIMESTAMP:(\d+)/);
    if (old && Number(old[1]) > manifest.finishedAt) throw Error('Refusing to replace newer Plane results with an older run');
    return { row, item, values, status: statusFor(values) };
  });
  const summary = { runId:manifest.runId, finishedAt: new Date(manifest.finishedAt).toISOString(), cases:updates.length, counts:{} };
  for (const u of updates) summary.counts[u.status] = (summary.counts[u.status] || 0) + 1;
  if (!apply) return summary;
  const logdir = path.join(root,'logs/plane'); fs.mkdirSync(logdir,{recursive:true});
  const lock = path.join(logdir,'results.lock'); let fd;
  try { fd = fs.openSync(lock,'wx'); } catch { throw Error('Plane results sync lock unavailable'); }
  try {
    const labels = await plane.list('labels/');
    const request = async (...args) => { if (pace) await new Promise(r => setTimeout(r, pace)); return plane.request(...args); };
    for (const [name,color] of Object.values(LABELS)) if (!labels.some(l => l.name === name)) labels.push(await request('labels/','POST',{ name,color }));
    const managed = new Set(labels.filter(l => Object.values(LABELS).some(([name]) => l.name === name)).map(l=>l.id));
    let changed = 0;
    for (const { row,item,values,status } of updates) {
      // Re-read to preserve manual description/label edits made after the initial list.
      const current = await request(`work-items/${item.id}/`);
      const previous = String(current.description_html || '');
      const timestamp = previous.match(/QA_RUN_TIMESTAMP:(\d+)/);
      if (timestamp && Number(timestamp[1]) > manifest.finishedAt) throw Error('Newer Plane results detected during synchronization');
      const managedBlock = /<p>QA_RESULT_START<\/p>[\s\S]*?<p>QA_RESULT_END<\/p>/g;
      const previousBlocks = previous.match(managedBlock) || [];
      const nextBlock = block(row,status,manifest,values);
      const description_html = previousBlocks.length === 1
        ? previous.replace(managedBlock, () => nextBlock)
        : nextBlock + previous.replace(managedBlock, '');
      const oldLabels = (current.labels || []).map(l=>l.id || l);
      const labelsNext = [...oldLabels.filter(id=>!managed.has(id)), labels.find(l=>l.name===LABELS[status][0]).id];
      if (previous === description_html && oldLabels.length === labelsNext.length && oldLabels.every(id=>labelsNext.includes(id))) continue;
      await request(`work-items/${item.id}/`,'PATCH',{ labels:labelsNext, description_html }); changed++;
    }
    const verified = await plane.list('work-items/');
    for (const u of updates) {
      const remote = verified.find(i=>i.id===u.item.id);
      const id = labels.find(l=>l.name===LABELS[u.status][0]).id;
      if (!remote || !(remote.labels || []).some(l=>(l.id || l)===id) || !String(remote.description_html || '').includes(`QA_RUN_TIMESTAMP:${manifest.finishedAt}`)) throw Error('Plane result verification failed');
    }
    Object.assign(summary,{changed,verified:true});
    fs.writeFileSync(path.join(logdir,'results-sync.json'),JSON.stringify(summary,null,2));
    return summary;
  } finally { fs.closeSync(fd); fs.unlinkSync(lock); }
}
module.exports = { snapshot, statusFor, syncResults, LABELS };
