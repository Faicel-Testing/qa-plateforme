'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { ROOT, DEFAULT_FILE } = require('./task-metrics');
function readEvents(file) {
  if (!fs.existsSync(file)) return { events: [], invalidLines: 0 };
  const events = []; let invalidLines = 0;
  for (const line of fs.readFileSync(file, 'utf8').split('\n').filter(Boolean)) {
    try { const event = JSON.parse(line); if (!event || event.version !== 1) throw Error(); events.push(event); }
    catch { invalidLines++; }
  }
  return { events, invalidLines };
}
function summarize(calls) {
  const known = calls.filter(c => Number.isFinite(c.cost?.usd));
  return { calls: calls.length, failedCalls: calls.filter(c => !c.success).length,
    measuredUsageCalls: calls.filter(c => c.usageStatus === 'MEASURED').length,
    inputTokens: calls.reduce((n, c) => n + (c.inputTokens || 0), 0),
    outputTokens: calls.reduce((n, c) => n + (c.outputTokens || 0), 0),
    knownApiCostUsd: known.reduce((n, c) => n + c.cost.usd, 0),
    unknownCostCalls: calls.length - known.length,
    apiCostComplete: calls.length === known.length,
    callDurationMs: calls.reduce((n, c) => n + (c.durationMs || 0), 0) };
}
function aggregate(events) {
  const tasks = new Map(), calls = new Map();
  for (const event of events) {
    if (event.type === 'task_start') tasks.set(event.taskId, { ...event, status: 'INCOMPLETE', durationMs: null });
    else if (event.type === 'task_end' && tasks.has(event.taskId)) Object.assign(tasks.get(event.taskId), {
      durationMs: event.durationMs, status: event.timedOut ? 'TIMEOUT' : event.success ? 'PROCESS_OK' : 'FAILED', exitCode: event.exitCode });
    else if (event.type === 'task_verification' && tasks.has(event.taskId)) tasks.get(event.taskId).verification = event.status;
    else if (event.type === 'call_start' && !calls.has(event.callId)) calls.set(event.callId, { ...event, usageStatus: 'UNKNOWN', success: false, cost: { usd: null, status: 'INCOMPLETE' } });
    else if (event.type === 'call_end') calls.set(event.callId, event);
  }
  const allCalls = [...calls.values()];
  function descendants(id) {
    const ids = new Set([id]); let changed = true;
    while (changed) { changed = false; for (const task of tasks.values()) if (ids.has(task.parentTaskId) && !ids.has(task.taskId)) { ids.add(task.taskId); changed = true; } }
    return ids;
  }
  const rows = [...tasks.values()].map(task => {
    const ids = descendants(task.taskId);
    const summary = summarize(allCalls.filter(call => ids.has(call.taskId)));
    if ([...tasks.values()].some(t => ids.has(t.taskId) && t.status === 'INCOMPLETE')) summary.apiCostComplete = false;
    return { ...task, ...summary,
      models: [...new Set(allCalls.filter(call => ids.has(call.taskId)).map(call => `${call.provider}/${call.model}`))] };
  });
  // Only root tasks enter per-completed-task averages; children are already included.
  const roots = rows.filter(t => !tasks.has(t.parentTaskId));
  const completed = roots.filter(t => t.status === 'PROCESS_OK' && t.verification !== 'REJECTED');
  const totals = summarize(allCalls);
  const byCategory = Object.fromEntries(['generation', 'embedding', 'evaluation', 'reranking'].map(kind => [kind, summarize(allCalls.filter(c => c.kind === kind))]));
  const byModel = {};
  for (const c of allCalls) byModel[`${c.provider}/${c.model}`] = summarize(allCalls.filter(x => x.provider === c.provider && x.model === c.model));
  return { totals, byCategory, byModel, tasks: rows, unassignedCalls: allCalls.filter(c => !tasks.has(c.taskId)).length,
    completedRootTasks: completed.length,
    meanCompletedTaskMs: completed.length ? completed.reduce((n, t) => n + t.durationMs, 0) / completed.length : null,
    meanCompletedTaskApiCostUsd: completed.length && completed.every(t => t.apiCostComplete && t.status !== 'INCOMPLETE')
      ? completed.reduce((n, t) => n + t.knownApiCostUsd, 0) / completed.length : null };
}
function historical(root) {
  let pipeline = null;
  try { const data = JSON.parse(fs.readFileSync(path.join(root, 'logs/pipeline-summary.json'), 'utf8'));
    pipeline = { runId: data.runId, timestamp: data.timestamp, durationMs: data.totalMs, validation: data.validation,
      tasks: (data.results || []).map(r => ({ label: r.name, durationMs: r.durationMs ?? null,
        status: r.skipped ? 'SKIPPED' : r.blocked ? 'BLOCKED' : r.success ? 'PROCESS_OK' : 'FAILED', verification: r.verification?.status || 'UNKNOWN', apiCostUsd: null })) };
  } catch { /* No historical pipeline. */ }
  let traceCount = 0;
  try { traceCount = fs.readFileSync(path.join(root, 'logs/traces.jsonl'), 'utf8').split('\n').filter(Boolean).length; } catch {}
  return { pipeline, legacyTraceCount: traceCount, note: 'Anciens coûts et tokens inconnus ; durées historiques séparées des nouvelles mesures.' };
}
const escape = value => String(value ?? '—').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
function html(report) {
  const seconds = ms => Number.isFinite(ms) ? (ms / 1000).toFixed(2) + ' s' : '—';
  return `<!doctype html><html lang="fr"><meta charset="utf-8"><title>Coût et temps par tâche</title>
  <style>body{font:16px system-ui;background:#101827;color:#edf3ff;margin:32px}h1,h2{color:#65d6d0}table{border-collapse:collapse;width:100%;background:#19263a}td,th{padding:12px;border-bottom:1px solid #34445b;text-align:left}small,p{color:#c3d1e5}.cards{display:flex;gap:16px;flex-wrap:wrap}.card{padding:18px;background:#19263a;border-radius:10px}input{padding:10px;margin:16px 0;width:320px}</style>
  <h1>Coût et temps par tâche</h1><p>${escape(report.generatedAt)}</p>
  <div class="cards"><div class="card">${report.completedRootTasks} tâches racines PROCESS_OK</div><div class="card">${seconds(report.meanCompletedTaskMs)} en moyenne par tâche terminée</div>
  <div class="card">$${report.totals.knownApiCostUsd.toFixed(6)} — part API connue, estimée au tarif catalogue</div>
  <div class="card">${report.totals.unknownCostCalls} appels au coût inconnu</div></div>
  <p>PROCESS_OK signifie sortie de processus réussie, pas validation métier. Coût machine, énergie, licences et services externes exclus. Les lignes parentes incluent leurs enfants : ne pas additionner les lignes.</p>
  <p>Tokens connus : ${report.totals.inputTokens} entrée / ${report.totals.outputTokens} sortie ; usage mesuré pour ${report.totals.measuredUsageCalls}/${report.totals.calls} appels. Appels sans tâche : ${report.unassignedCalls}. Lignes illisibles : ${report.invalidLines}.</p>
  <input id="filter" placeholder="Filtrer les tâches ou les modèles" aria-label="Filtrer les tâches">
  <table id="tasks"><thead><tr><th>Tâche</th><th>État</th><th>Temps réel</th><th>Appels</th><th>Tokens entrée / sortie</th><th>Coût API USD</th><th>Modèles</th></tr></thead><tbody>
  ${report.tasks.slice(-100).reverse().map(t => `<tr><td>${escape(t.label)}<br><small>${escape(t.taskId)}</small></td><td>${escape(t.status)}<br>${escape(t.verification || '')}</td><td>${seconds(t.durationMs)}</td><td>${t.calls}</td><td>${t.inputTokens} / ${t.outputTokens}</td><td>${t.apiCostComplete ? '$' + t.knownApiCostUsd.toFixed(6) : 'Inconnu (part connue $' + t.knownApiCostUsd.toFixed(6) + ')'}</td><td>${escape(t.models.join(', '))}</td></tr>`).join('')}</tbody></table>
  <h2>Dernier pipeline historique</h2><p>Coûts non reconstituables. Durée totale : ${seconds(report.historical.pipeline?.durationMs)}. Validation : ${escape(report.historical.pipeline?.validation)}</p>
  <table><tr><th>Tâche</th><th>État</th><th>Temps</th><th>Coût</th></tr>${(report.historical.pipeline?.tasks || []).map(t => `<tr><td>${escape(t.label)}</td><td>${escape(t.status)}</td><td>${seconds(t.durationMs)}</td><td>Inconnu</td></tr>`).join('')}</table>
  <script>document.getElementById('filter').addEventListener('input',function(){for(const row of document.querySelectorAll('#tasks tbody tr'))row.hidden=!row.textContent.toLowerCase().includes(this.value.toLowerCase())})</script></html>`;
}
function generate(root = ROOT, file = process.env.QA_METRICS_FILE || DEFAULT_FILE) {
  const data = readEvents(file);
  const report = { generatedAt: new Date().toISOString(), ...aggregate(data.events), invalidLines: data.invalidLines, historical: historical(root) };
  if (data.invalidLines) { report.totals.apiCostComplete = false; report.meanCompletedTaskApiCostUsd = null; }
  const dir = path.join(root, 'logs/metrics'); fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'report.json'), JSON.stringify(report, null, 2));
  fs.writeFileSync(path.join(dir, 'report.html'), html(report));
  console.table(report.tasks.map(t => ({ tâche: t.label, état: t.status, secondes: t.durationMs === null ? null : +(t.durationMs / 1000).toFixed(2), appels: t.calls,
    tokensEntrée: t.inputTokens, tokensSortie: t.outputTokens, coûtApiUSD: t.apiCostComplete ? t.knownApiCostUsd : 'INCONNU' })));
  console.log(`Rapport : ${path.join(dir, 'report.html')}`);
  return report;
}
module.exports = { aggregate, summarize, readEvents, generate, html };
