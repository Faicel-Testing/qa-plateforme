'use strict';
// ============================================================
// Reporting Agent — KPI, Dashboard, Notifications, Sync Jira
// ============================================================
// Absorbe : kpi-agent, notification-agent, status-agent, report-agent
//
// Usage:
//   node scripts/agents/reporting-agent.js kpi             Calcule les KPIs depuis allure-results
//   node scripts/agents/reporting-agent.js dashboard       Génère docs/kpi-dashboard.html
//   node scripts/agents/reporting-agent.js notify          Envoie résumé Slack (ou Teams)
//   node scripts/agents/reporting-agent.js notify teams    Envoie vers Teams
//   node scripts/agents/reporting-agent.js sync            Synchronise Allure → Jira
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

const FRAMEWORK   = path.join(__dirname, '..', '..');
const RESULTS_DIR = path.join(FRAMEWORK, 'allure-results');
const DOCS_DIR    = path.join(FRAMEWORK, 'docs');

fs.mkdirSync(DOCS_DIR, { recursive: true });

const DRY_RUN        = process.argv.includes('--dry-run');
const SLACK_WEBHOOK  = process.env.SLACK_WEBHOOK_URL || '';
const TEAMS_WEBHOOK  = process.env.TEAMS_WEBHOOK_URL || '';
const JIRA_BASE_URL  = (process.env.JIRA_BASE_URL || '').replace(/\/$/, '');
const JIRA_AUTH      = Buffer.from(`${process.env.JIRA_EMAIL}:${process.env.JIRA_TOKEN}`).toString('base64');
const JIRA_PROJECT   = process.env.JIRA_PROJECT || 'SCRUM';

const G = '\x1b[32m', R = '\x1b[31m', Y = '\x1b[33m', C = '\x1b[36m', B = '\x1b[1m', E = '\x1b[0m';

// Quality Gate seuils
const QUALITY_GATE = { pass_rate: 90, fail_rate: 5, flaky_rate: 20, coverage: 80 };

// ── Lecture allure-results ─────────────────────────────────────────────────────
function loadResults() {
  if (!fs.existsSync(RESULTS_DIR)) return [];
  return fs.readdirSync(RESULTS_DIR)
    .filter(f => f.endsWith('-result.json'))
    .map(f => { try { return JSON.parse(fs.readFileSync(path.join(RESULTS_DIR, f), 'utf8')); } catch { return null; } })
    .filter(Boolean);
}

function computeKpi(results) {
  const s = { passed: 0, failed: 0, broken: 0, skipped: 0, total: 0 };
  results.forEach(r => { const st = r.status || 'unknown'; if (st in s) s[st]++; s.total++; });
  s.pass_rate  = s.total ? Math.round(s.passed / s.total * 1000) / 10 : 0;
  s.fail_rate  = s.total ? Math.round((s.failed + s.broken) / s.total * 1000) / 10 : 0;
  s.skip_rate  = s.total ? Math.round(s.skipped / s.total * 1000) / 10 : 0;
  s.gate_ok    = s.pass_rate >= QUALITY_GATE.pass_rate && s.fail_rate <= QUALITY_GATE.fail_rate;
  return s;
}

// ── KPI ───────────────────────────────────────────────────────────────────────
function cmdKpi() {
  console.log(`\n${B}=== REPORTING — KPI ===${E}`);
  const results = loadResults();
  if (!results.length) { console.log(`  ${Y}⚠  Aucun résultat dans allure-results/${E}`); return null; }

  const kpi = computeKpi(results);
  const bar = G + '█'.repeat(Math.round(kpi.pass_rate / 5)) + E + '░'.repeat(20 - Math.round(kpi.pass_rate / 5));
  console.log(`\n  [${bar}] ${kpi.pass_rate}% passed`);
  console.log(`  Total: ${kpi.total}  |  ${G}${kpi.passed}P${E}  ${R}${kpi.failed}F${E}  ${Y}${kpi.broken}B${E}  ${C}${kpi.skipped}S${E}`);
  console.log(`\n  ${B}Quality Gate :${E} ${kpi.gate_ok ? G+'✓ PASSED'+E : R+'✗ FAILED'+E}`);
  console.log(`  Pass Rate : ${kpi.pass_rate}%  (seuil: ${QUALITY_GATE.pass_rate}%)`);
  console.log(`  Fail Rate : ${kpi.fail_rate}%  (seuil max: ${QUALITY_GATE.fail_rate}%)`);
  return kpi;
}

// ── DASHBOARD HTML ────────────────────────────────────────────────────────────
function cmdDashboard() {
  console.log(`\n${B}=== REPORTING — DASHBOARD ===${E}`);
  const results = loadResults();
  const kpi     = computeKpi(results);
  const failures = results.filter(r => ['failed','broken'].includes(r.status)).slice(0,10);

  const html = `<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><title>KPI Dashboard — Playwright BDD</title>
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
  .tag-failed{color:#f87171}.tag-broken{color:#fb923c}
</style></head>
<body>
<h1>📊 KPI Dashboard — Playwright BDD</h1>
<p style="color:#64748b">Généré le ${new Date().toLocaleString('fr-FR')}</p>
<div class="gate ${kpi.gate_ok?'ok':'fail'}">${kpi.gate_ok?'✅ QUALITY GATE PASSED':'❌ QUALITY GATE FAILED'}</div>
<div class="grid">
  <div class="card"><div class="val">${kpi.pass_rate}%</div><div class="lbl">Pass Rate</div></div>
  <div class="card"><div class="val">${kpi.passed}</div><div class="lbl">Passed</div></div>
  <div class="card"><div class="val" style="color:#f87171">${kpi.failed}</div><div class="lbl">Failed</div></div>
  <div class="card"><div class="val" style="color:#fb923c">${kpi.broken}</div><div class="lbl">Broken</div></div>
  <div class="card"><div class="val">${kpi.total}</div><div class="lbl">Total</div></div>
</div>
<canvas id="donut" width="300" height="260"></canvas>
${failures.length ? `<h2 style="color:#f87171;margin-top:24px">Échecs (${failures.length})</h2>
<table><tr><th>Test</th><th>Statut</th><th>Message</th></tr>
${failures.map(f=>`<tr><td>${f.name||''}</td><td class="tag-${f.status}">${f.status}</td><td style="color:#94a3b8;font-size:.8rem">${(f.statusDetails?.message||'').slice(0,80)}</td></tr>`).join('')}
</table>` : '<p style="color:#4ade80;margin-top:16px">✅ Aucun échec</p>'}
<script>
new Chart(document.getElementById('donut'),{type:'doughnut',
  data:{labels:['Passed','Failed','Broken','Skipped'],
    datasets:[{data:[${kpi.passed},${kpi.failed},${kpi.broken},${kpi.skipped}],
      backgroundColor:['#22c55e','#ef4444','#f97316','#64748b'],borderWidth:0}]},
  options:{plugins:{legend:{labels:{color:'#e2e8f0'}}}}});
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
  const results  = loadResults();
  const kpi      = computeKpi(results);
  const failures = results.filter(r => ['failed','broken'].includes(r.status)).slice(0,5);

  const span = new tracer.Span('notifySummary', JSON.stringify(kpi), llm.MODEL).begin();
  let summary;
  try {
    const prompt = `Tu es un expert QA. Génère un résumé Slack concis (2-3 phrases) du run Playwright.
Pass rate: ${kpi.pass_rate}% | ${kpi.passed}/${kpi.total} passés
Échecs: ${failures.map(f=>f.name).join(', ')||'aucun'}
Ton: direct. Si PASSED → rassurant. Si FAILED → factuel, action concrète.`;

    const resp = await llm.chat([{ role: 'user', content: prompt }]);
    summary = resp.message.content || '';
    span.end(true);
  } catch (e) {
    span.error = e.message; span.end(false);
    summary = `Run Playwright : ${kpi.pass_rate}% de réussite (${kpi.passed}/${kpi.total}).`;
  }

  const status = kpi.gate_ok ? 'PASSED' : 'FAILED';
  const emoji  = { PASSED: '✅', FAILED: '❌' }[status] || '📊';
  console.log(`\n  ${emoji} ${kpi.pass_rate}% — ${summary.slice(0,80)}`);

  if (DRY_RUN) { console.log(`  ${Y}[DRY-RUN] Message non envoyé${E}`); return; }

  const webhook = target === 'teams' ? TEAMS_WEBHOOK : SLACK_WEBHOOK;
  if (!webhook) { console.log(`  ${Y}⚠  ${target.toUpperCase()}_WEBHOOK_URL non configurée dans .env${E}`); return; }

  const payload = target === 'teams'
    ? { '@type':'MessageCard','@context':'http://schema.org/extensions', themeColor: kpi.gate_ok?'00b894':'d63031',
        summary: `${emoji} Playwright — ${kpi.pass_rate}%`,
        sections:[{ activityTitle:`${emoji} Playwright BDD — ${kpi.pass_rate}% passé`, activitySubtitle: summary,
          facts:[{name:'Passed',value:String(kpi.passed)},{name:'Failed',value:String(kpi.failed)},{name:'Total',value:String(kpi.total)}] }] }
    : { attachments:[{ color: kpi.gate_ok?'#22c55e':'#ef4444', blocks:[
        { type:'header', text:{type:'plain_text', text:`${emoji} Playwright BDD — ${kpi.pass_rate}% passed`}},
        { type:'section', text:{type:'mrkdwn', text: summary}},
        { type:'section', fields:[
          {type:'mrkdwn',text:`*Passed*\n${kpi.passed}/${kpi.total}`},
          {type:'mrkdwn',text:`*Failed*\n${kpi.failed}`},
        ]}
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

// ── SYNC Allure → Jira ────────────────────────────────────────────────────────
async function cmdSync() {
  console.log(`\n${B}=== REPORTING — SYNC JIRA ===${E}`);
  const results = loadResults();
  if (!results.length) { console.log(`  ${Y}⚠  Aucun résultat Allure${E}`); return; }

  const STATUS_MAP = { passed: 'Terminé', failed: 'En cours', broken: 'En cours', skipped: 'À faire' };
  let synced = 0, skipped = 0;

  for (const r of results) {
    const labels = (r.labels || []).map(l => l.value);
    const jiraKey = labels.find(l => /^[A-Z]+-\d+$/.test(l));
    if (!jiraKey) { skipped++; continue; }

    const jiraStatus = STATUS_MAP[r.status] || 'À faire';
    const icon = r.status === 'passed' ? G+'✓'+E : R+'✗'+E;
    console.log(`  ${icon} ${r.name?.slice(0,45).padEnd(45)} → ${jiraKey}  [${jiraStatus}]`);

    if (!DRY_RUN) {
      try {
        const comment = { body: { type:'doc', version:1, content:[{ type:'paragraph', content:[
          { type:'text', text:`[Allure] ${r.status.toUpperCase()} — ${r.name}`, marks:[{type:'strong'}] }
        ]}]}};
        const data = JSON.stringify(comment);
        await new Promise((resolve, reject) => {
          const url = new URL(`${JIRA_BASE_URL}/rest/api/3/issue/${jiraKey}/comment`);
          const req = https.request({ hostname:url.hostname, path:url.pathname, method:'POST',
            headers:{Authorization:`Basic ${JIRA_AUTH}`,'Content-Type':'application/json','Content-Length':Buffer.byteLength(data)}
          }, res => resolve(res.statusCode));
          req.on('error', reject); req.write(data); req.end();
        });
        synced++;
      } catch {}
    }
  }
  console.log(`\n  ${G}✓ ${synced} synchronisés${E}  ${C}${skipped} sans clé Jira${E}`);
}

// ── SUMMARY ───────────────────────────────────────────────────────────────────
function cmdSummary() {
  const results = loadResults();
  const kpi     = computeKpi(results);
  const gate    = kpi.gate_ok ? G+'✅ GATE OK'+E : R+'❌ GATE FAILED'+E;
  console.log(`\n${B}=== REPORTING — SUMMARY ===${E}`);
  console.log(`  ${gate}  |  ${kpi.pass_rate}% (${kpi.passed}/${kpi.total})  |  ${kpi.failed}F ${kpi.broken}B ${kpi.skipped}S`);
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
    case 'sync':      await cmdSync();         break;
    case 'summary':   cmdSummary();            break;
    default:
      console.log(`
${B}Reporting Agent${E} — KPI, Dashboard, Notifications, Sync

  kpi              Calcule et affiche les KPIs depuis allure-results
  dashboard        Génère docs/kpi-dashboard.html avec Chart.js
  notify [teams]   Envoie résumé Slack (ou Teams)
  sync             Synchronise les statuts Allure → commentaires Jira
  summary          Résumé rapide Quality Gate en console

Options:
  --dry-run        Simulation sans écriture ni envoi

Variables:
  SLACK_WEBHOOK_URL     Webhook Slack
  TEAMS_WEBHOOK_URL     Webhook Teams (alternatif)
  JIRA_PROJECT=SCRUM    Projet Jira cible
`);
  }
}

main().catch(e => { console.error(R + e.message + E); process.exit(1); });
