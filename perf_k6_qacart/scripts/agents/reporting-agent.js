'use strict';
// ============================================================
// Reporting Agent — KPI, Dashboard, Notifications (Performance k6)
// ============================================================
// Usage:
//   node scripts/agents/reporting-agent.js kpi             Calcule les KPIs depuis reports/summary-*.json
//   node scripts/agents/reporting-agent.js dashboard       Génère docs/kpi-dashboard.html
//   node scripts/agents/reporting-agent.js notify          Envoie résumé Slack (ou Teams)
//   node scripts/agents/reporting-agent.js notify teams    Envoie vers Teams
//   node scripts/agents/reporting-agent.js summary         Résumé console rapide
//
// Coût LLM : très bas — LLM uniquement pour le résumé narratif (notify)
// ============================================================
require('dotenv').config();
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';

const fs    = require('fs');
const path  = require('path');
const https = require('https');
const http  = require('http');
const llm   = require('./llm');
const tracer = require('./shared/tracer');

const FRAMEWORK    = path.join(__dirname, '..', '..');
const REPORTS_DIR  = path.join(FRAMEWORK, 'reports');
const DOCS_DIR      = path.join(FRAMEWORK, 'docs');
const SCENARIOS     = ['smoke', 'load', 'stress'];

fs.mkdirSync(DOCS_DIR, { recursive: true });

const DRY_RUN        = process.argv.includes('--dry-run');
const SLACK_WEBHOOK  = process.env.SLACK_WEBHOOK_URL || '';
const TEAMS_WEBHOOK  = process.env.TEAMS_WEBHOOK_URL || '';

const G = '\x1b[32m', R = '\x1b[31m', Y = '\x1b[33m', C = '\x1b[36m', B = '\x1b[1m', E = '\x1b[0m';

// Seuil Quality Gate — dépassement toléré uniquement en @stress (dyno gratuit partagé)
const QUALITY_GATE = { blockingScenarios: ['smoke', 'load'] };

// ── Lecture reports/summary-*.json ─────────────────────────────────────────────
function loadResults() {
  const results = {};
  for (const scenario of SCENARIOS) {
    const fp = path.join(REPORTS_DIR, `summary-${scenario}.json`);
    if (!fs.existsSync(fp)) continue;
    try { results[scenario] = JSON.parse(fs.readFileSync(fp, 'utf8')); } catch {}
  }
  return results;
}

function computeKpi(results) {
  const scenarios = {};
  let blockingBreaches = 0, totalBreaches = 0;

  for (const [scenario, summary] of Object.entries(results)) {
    const dur = summary.metrics?.http_req_duration || {};
    const checks = summary.metrics?.checks || { passes: 0, fails: 0 };
    const httpFailed = summary.metrics?.http_req_failed || { value: 0 };

    const breaches = [];
    for (const [metricName, metric] of Object.entries(summary.metrics || {})) {
      for (const [expr, wasBreached] of Object.entries(metric.thresholds || {})) {
        if (wasBreached) breaches.push({ metric: metricName, expr });
      }
    }

    scenarios[scenario] = {
      p95_ms: Math.round(dur['p(95)'] || 0),
      avg_ms: Math.round(dur.avg || 0),
      min_ms: Math.round(dur.min || 0),
      max_ms: Math.round(dur.max || 0),
      error_rate: Math.round((httpFailed.value || 0) * 1000) / 10,
      checks_pass_rate: (checks.passes + checks.fails) ? Math.round(checks.passes / (checks.passes + checks.fails) * 1000) / 10 : 0,
      breaches,
    };
    totalBreaches += breaches.length;
    if (QUALITY_GATE.blockingScenarios.includes(scenario)) blockingBreaches += breaches.length;
  }

  return { scenarios, totalBreaches, blockingBreaches, gate_ok: blockingBreaches === 0 };
}

// ── KPI ───────────────────────────────────────────────────────────────────────
function cmdKpi() {
  console.log(`\n${B}=== REPORTING — KPI ===${E}`);
  const results = loadResults();
  if (!Object.keys(results).length) { console.log(`  ${Y}⚠  Aucun résultat dans reports/${E}`); return null; }

  const kpi = computeKpi(results);
  for (const [scenario, m] of Object.entries(kpi.scenarios)) {
    const bar = (m.breaches.length ? R : G) + '█'.repeat(Math.round(m.checks_pass_rate / 5)) + E + '░'.repeat(20 - Math.round(m.checks_pass_rate / 5));
    console.log(`\n  [${bar}] ${scenario}  p95=${m.p95_ms}ms  err=${m.error_rate}%  checks=${m.checks_pass_rate}%`);
  }
  console.log(`\n  ${B}Quality Gate (smoke+load bloquants) :${E} ${kpi.gate_ok ? G+'✓ PASSED'+E : R+'✗ FAILED'+E}`);
  console.log(`  Seuils dépassés : ${kpi.totalBreaches} total, ${kpi.blockingBreaches} bloquant(s)`);
  return kpi;
}

// ── DASHBOARD HTML ────────────────────────────────────────────────────────────
function cmdDashboard() {
  console.log(`\n${B}=== REPORTING — DASHBOARD ===${E}`);
  const results = loadResults();
  const kpi     = computeKpi(results);
  const scenarioNames = Object.keys(kpi.scenarios);

  const html = `<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><title>KPI Dashboard — k6 Performance</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  body{font-family:sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:24px}
  h1{color:#7c3aed;font-size:1.5rem}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin:24px 0}
  .card{background:#1e293b;border-radius:12px;padding:20px;text-align:center}
  .card .val{font-size:2rem;font-weight:700;color:#7c3aed}
  .card .lbl{font-size:.8rem;color:#94a3b8;margin-top:4px}
  .gate{padding:12px 20px;border-radius:8px;margin:16px 0;font-weight:600}
  .gate.ok{background:#052e16;color:#4ade80}.gate.fail{background:#450a0a;color:#f87171}
  canvas{max-height:260px}
  table{width:100%;border-collapse:collapse;margin-top:16px}
  th{background:#1e293b;padding:8px;text-align:left;color:#94a3b8}
  td{padding:8px;border-bottom:1px solid #1e293b}
  .tag-breach{color:#f87171}
</style></head>
<body>
<h1>📊 KPI Dashboard — k6 Performance</h1>
<p style="color:#64748b">Généré le ${new Date().toLocaleString('fr-FR')}</p>
<div class="gate ${kpi.gate_ok?'ok':'fail'}">${kpi.gate_ok?'✅ QUALITY GATE PASSED (smoke+load)':'❌ QUALITY GATE FAILED (smoke+load)'}</div>
<div class="grid">
${scenarioNames.map(s => `  <div class="card"><div class="val">${kpi.scenarios[s].p95_ms}ms</div><div class="lbl">p95 — ${s}</div></div>`).join('\n')}
</div>
<canvas id="p95Chart" width="400" height="260"></canvas>
${kpi.totalBreaches ? `<h2 style="color:#f87171;margin-top:24px">Seuils dépassés (${kpi.totalBreaches})</h2>
<table><tr><th>Scénario</th><th>Métrique</th><th>Seuil</th></tr>
${Object.entries(kpi.scenarios).flatMap(([s,m])=>m.breaches.map(b=>`<tr><td>${s}</td><td class="tag-breach">${b.metric}</td><td>${b.expr}</td></tr>`)).join('')}
</table>` : '<p style="color:#4ade80;margin-top:16px">✅ Aucun seuil dépassé</p>'}
<script>
new Chart(document.getElementById('p95Chart'),{type:'bar',
  data:{labels:${JSON.stringify(scenarioNames)},
    datasets:[{label:'p95 (ms)',data:${JSON.stringify(scenarioNames.map(s=>kpi.scenarios[s].p95_ms))},
      backgroundColor:['#22c55e','#f59e0b','#ef4444'],borderWidth:0}]},
  options:{plugins:{legend:{labels:{color:'#e2e8f0'}}},scales:{x:{ticks:{color:'#94a3b8'}},y:{ticks:{color:'#94a3b8'}}}}});
</script>
</body></html>`;

  const outPath = path.join(DOCS_DIR, 'kpi-dashboard.html');
  if (!DRY_RUN) { fs.writeFileSync(outPath, html, 'utf8'); console.log(`  ${G}✓ ${outPath}${E}`); }
  else console.log(`  ${Y}[DRY-RUN] Dashboard non écrit${E}`);
  return kpi;
}

// ── NOTIFY ────────────────────────────────────────────────────────────────────
async function cmdNotify(target = 'slack') {
  console.log(`\n${B}=== REPORTING — NOTIFY [${target.toUpperCase()}] [${llm.MODEL}] ===${E}`);
  const results = loadResults();
  const kpi     = computeKpi(results);

  const span = new tracer.Span('notifySummary', JSON.stringify(kpi), llm.MODEL).begin();
  let summary;
  try {
    const scenarioStr = Object.entries(kpi.scenarios).map(([s,m])=>`${s}: p95=${m.p95_ms}ms err=${m.error_rate}%`).join(', ');
    const prompt = `Tu es un expert en tests de performance k6. Génère un résumé Slack concis (2-3 phrases).
${scenarioStr}
Seuils dépassés: ${kpi.totalBreaches} (${kpi.blockingBreaches} bloquant(s))
Ton: direct. Si gate OK → rassurant. Si FAILED → factuel, action concrète.`;

    const resp = await llm.chat([{ role: 'user', content: prompt }]);
    summary = resp.message.content || '';
    span.end(true);
  } catch (e) {
    span.error = e.message; span.end(false);
    summary = `Run k6 : gate ${kpi.gate_ok ? 'PASSED' : 'FAILED'} (${kpi.totalBreaches} seuil(s) dépassé(s)).`;
  }

  const status = kpi.gate_ok ? 'PASSED' : 'FAILED';
  const emoji  = { PASSED: '✅', FAILED: '❌' }[status] || '📊';
  console.log(`\n  ${emoji} ${summary.slice(0,80)}`);

  if (DRY_RUN) { console.log(`  ${Y}[DRY-RUN] Message non envoyé${E}`); return; }

  const webhook = target === 'teams' ? TEAMS_WEBHOOK : SLACK_WEBHOOK;
  if (!webhook) { console.log(`  ${Y}⚠  ${target.toUpperCase()}_WEBHOOK_URL non configurée dans .env${E}`); return; }

  const payload = target === 'teams'
    ? { '@type':'MessageCard','@context':'http://schema.org/extensions', themeColor: kpi.gate_ok?'00b894':'d63031',
        summary: `${emoji} k6 Performance`,
        sections:[{ activityTitle:`${emoji} k6 Performance — gate ${status}`, activitySubtitle: summary }] }
    : { attachments:[{ color: kpi.gate_ok?'#22c55e':'#ef4444', blocks:[
        { type:'header', text:{type:'plain_text', text:`${emoji} k6 Performance — gate ${status}`}},
        { type:'section', text:{type:'mrkdwn', text: summary}},
      ]}]};

  try {
    const url   = new URL(webhook);
    const data  = JSON.stringify(payload);
    const proto = url.protocol === 'https:' ? https : http;
    await new Promise((resolve, reject) => {
      const req = proto.request({ hostname:url.hostname, path:url.pathname+url.search, method:'POST',
        headers:{'Content-Type':'application/json','Content-Length':Buffer.byteLength(data)}
      }, res => resolve(res.statusCode));
      req.on('error', reject); req.write(data); req.end();
    });
    console.log(`  ${G}✓ Message ${target} envoyé${E}`);
  } catch (e) {
    console.error(`  ${R}✗ Envoi échoué: ${e.message}${E}`);
  }
}

// ── SUMMARY ───────────────────────────────────────────────────────────────────
function cmdSummary() {
  const results = loadResults();
  const kpi     = computeKpi(results);
  const gate    = kpi.gate_ok ? G+'✅ GATE OK'+E : R+'❌ GATE FAILED'+E;
  console.log(`\n${B}=== REPORTING — SUMMARY ===${E}`);
  console.log(`  ${gate}  |  ${kpi.totalBreaches} seuil(s) dépassé(s) (${kpi.blockingBreaches} bloquant)`);
  Object.entries(kpi.scenarios).forEach(([s,m]) => console.log(`  ${s.padEnd(8)} p95=${m.p95_ms}ms  err=${m.error_rate}%`));
}

// ── Main ──────────────────────────────────────────────────────────────────────
async function main() {
  const args = process.argv.slice(2).filter(a => !a.startsWith('--'));
  const [cmd, sub] = args;
  await llm.assertRunning();

  switch (cmd) {
    case 'kpi':       cmdKpi();                break;
    case 'dashboard': cmdDashboard();          break;
    case 'notify':    await cmdNotify(sub);    break;
    case 'summary':   cmdSummary();            break;
    default:
      console.log(`
${B}Reporting Agent${E} — KPI, Dashboard, Notifications (Performance)

  kpi              Calcule et affiche les KPIs depuis reports/summary-*.json
  dashboard        Génère docs/kpi-dashboard.html avec Chart.js
  notify [teams]   Envoie résumé Slack (ou Teams)
  summary          Résumé rapide Quality Gate en console

Options:
  --dry-run        Simulation sans écriture ni envoi

Variables:
  SLACK_WEBHOOK_URL     Webhook Slack
  TEAMS_WEBHOOK_URL     Webhook Teams (alternatif)
`);
  }
}

main().catch(e => { console.error(R + e.message + E); process.exit(1); });
