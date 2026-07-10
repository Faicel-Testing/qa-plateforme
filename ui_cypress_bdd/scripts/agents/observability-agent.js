'use strict';
// ============================================================
// Observability Agent — Monitoring LLM + Résilience + Prompt Versions
// ============================================================
// Usage:
//   node scripts/agents/observability-agent.js metrics       Métriques appels LLM
//   node scripts/agents/observability-agent.js anomalies     Détecte appels lents/erreurs
//   node scripts/agents/observability-agent.js cost          Estimation coût tokens
//   node scripts/agents/observability-agent.js cb status     État du Circuit Breaker
//   node scripts/agents/observability-agent.js cb reset      Réinitialise le CB
//   node scripts/agents/observability-agent.js cb cache      Affiche stats cache LLM
//   node scripts/agents/observability-agent.js prompts list  Liste les prompts versionnés
//   node scripts/agents/observability-agent.js prompts history <name>  Historique d'un prompt
//   node scripts/agents/observability-agent.js prompts rollback <name> Rollback version
//   node scripts/agents/observability-agent.js report        Génère docs/observability-report.html
//   node scripts/agents/observability-agent.js clear         Vide les traces
//
// Coût LLM : zéro (100% déterministe — lecture de fichiers et calculs)
// ============================================================
require('dotenv').config();

const fs     = require('fs');
const path   = require('path');
const tracer = require('./shared/tracer');
const cb     = require('./shared/circuit-breaker');
const ps     = require('./shared/prompt-store');

const FRAMEWORK = path.join(__dirname, '..', '..');
const DOCS_DIR  = path.join(FRAMEWORK, 'docs');
fs.mkdirSync(DOCS_DIR, { recursive: true });

const PRICING = { input: 0.59, output: 0.79 };

const SLOW_MS      = 8000;
const VERY_SLOW_MS = 15000;
const LOW_CONF     = 0.65;
const ERR_BURST    = 3;

const G = '\x1b[32m', R = '\x1b[31m', Y = '\x1b[33m', C = '\x1b[36m', B = '\x1b[1m', E = '\x1b[0m';

// ── METRICS ───────────────────────────────────────────────────────────────────
function cmdMetrics() {
  console.log(`\n${B}=== OBSERVABILITY — METRICS ===${E}`);
  const traces = tracer.loadTraces();
  if (!traces.length) { console.log(`  ${Y}⚠  Aucune trace dans logs/traces.jsonl${E}`); return; }

  const byAgent = {};
  for (const t of traces) {
    const key = `${t.agent}/${t.fn}`;
    if (!byAgent[key]) byAgent[key] = { calls: 0, totalMs: 0, errors: 0, durations: [] };
    const s = byAgent[key];
    s.calls++; s.totalMs += t.duration_ms || 0;
    if (!t.success) s.errors++;
    s.durations.push(t.duration_ms || 0);
  }

  console.log(`\n  ${C}${traces.length} traces — ${Object.keys(byAgent).length} fonctions uniques${E}\n`);
  console.log(`  ${'Agent/Fonction'.padEnd(40)} ${'Calls'.padEnd(7)} ${'Moy ms'.padEnd(9)} ${'P95 ms'.padEnd(9)} Erreurs`);
  console.log(`  ${'─'.repeat(78)}`);

  for (const [key, s] of Object.entries(byAgent).sort((a,b) => b[1].calls - a[1].calls)) {
    const avgMs = Math.round(s.totalMs / s.calls);
    const sorted = [...s.durations].sort((a,b) => a-b);
    const p95    = sorted[Math.floor(sorted.length * 0.95)] || 0;
    const errPct = Math.round(s.errors / s.calls * 100);
    const errStr = s.errors ? R + `${s.errors} (${errPct}%)` + E : G + '0' + E;
    const msColor = avgMs > SLOW_MS ? R : avgMs > 3000 ? Y : G;
    console.log(`  ${key.padEnd(40)} ${String(s.calls).padEnd(7)} ${msColor}${String(avgMs).padEnd(9)}${E} ${String(Math.round(p95)).padEnd(9)} ${errStr}`);
  }
}

// ── ANOMALIES ─────────────────────────────────────────────────────────────────
function cmdAnomalies() {
  console.log(`\n${B}=== OBSERVABILITY — ANOMALIES ===${E}`);
  const traces  = tracer.loadTraces();
  if (!traces.length) { console.log(`  ${Y}⚠  Aucune trace${E}`); return; }

  const anomalies = [];
  const recentErrors = traces.slice(-20).filter(t => !t.success);

  for (const t of traces) {
    if (t.duration_ms >= VERY_SLOW_MS) anomalies.push({ type: 'very_slow', trace: t, msg: `${Math.round(t.duration_ms/1000)}s — ${t.agent}/${t.fn}` });
    else if (t.duration_ms >= SLOW_MS) anomalies.push({ type: 'slow',      trace: t, msg: `${Math.round(t.duration_ms/1000)}s — ${t.agent}/${t.fn}` });
    if (t.confidence != null && t.confidence < LOW_CONF) anomalies.push({ type: 'low_conf', trace: t, msg: `conf=${t.confidence} — ${t.agent}/${t.fn}` });
  }
  if (recentErrors.length >= ERR_BURST) anomalies.push({ type: 'error_burst', msg: `${recentErrors.length} erreurs sur les 20 derniers appels` });

  if (!anomalies.length) { console.log(`  ${G}✓ Aucune anomalie détectée${E}`); return; }
  console.log(`  ${R}${anomalies.length} anomalie(s) détectée(s)${E}\n`);

  for (const a of anomalies) {
    const icon = a.type === 'very_slow' ? R+'🔴'+E : a.type === 'slow' ? Y+'🟡'+E : a.type === 'low_conf' ? Y+'⚡'+E : R+'💥'+E;
    console.log(`  ${icon}  [${a.type.toUpperCase()}]  ${a.msg}`);
  }
}

// ── COST ──────────────────────────────────────────────────────────────────────
function cmdCost() {
  console.log(`\n${B}=== OBSERVABILITY — COÛT TOKENS ===${E}`);
  const traces = tracer.loadTraces();
  if (!traces.length) { console.log(`  ${Y}⚠  Aucune trace${E}`); return; }

  let totalInput = 0, totalOutput = 0;
  const byAgent  = {};

  for (const t of traces) {
    const inp = t.prompt_len  / 4;
    const out = t.response_len / 4;
    totalInput  += inp; totalOutput += out;
    if (!byAgent[t.agent]) byAgent[t.agent] = { input: 0, output: 0, calls: 0 };
    byAgent[t.agent].input  += inp;
    byAgent[t.agent].output += out;
    byAgent[t.agent].calls++;
  }

  const costInput  = totalInput  / 1_000_000 * PRICING.input;
  const costOutput = totalOutput / 1_000_000 * PRICING.output;
  const total      = costInput + costOutput;

  console.log(`\n  ${B}Total estimé (Groq llama-3.3-70b) :${E} $${total.toFixed(4)}`);
  console.log(`  Input : ~${Math.round(totalInput).toLocaleString()} tokens  ($${costInput.toFixed(4)})`);
  console.log(`  Output: ~${Math.round(totalOutput).toLocaleString()} tokens ($${costOutput.toFixed(4)})\n`);

  console.log(`  ${'Agent'.padEnd(30)} ${'Calls'.padEnd(7)} ${'Tokens'.padEnd(12)} Coût estimé`);
  console.log(`  ${'─'.repeat(65)}`);
  for (const [agent, s] of Object.entries(byAgent).sort((a,b) => (b[1].input+b[1].output)-(a[1].input+a[1].output))) {
    const tokens = Math.round(s.input + s.output);
    const cost   = (s.input / 1_000_000 * PRICING.input + s.output / 1_000_000 * PRICING.output);
    console.log(`  ${agent.padEnd(30)} ${String(s.calls).padEnd(7)} ${String(tokens).padEnd(12)} $${cost.toFixed(4)}`);
  }
  console.log(`\n  ${C}💡 Ollama local → $0.00 (toutes les traces)${E}`);
}

// ── CIRCUIT BREAKER ───────────────────────────────────────────────────────────
function cmdCb(action) {
  if (action === 'reset') {
    cb.reset(); console.log(`  ${G}✓ Circuit Breaker réinitialisé → CLOSED${E}`);
  } else if (action === 'cache') {
    const status = cb.getStatus();
    console.log(`\n${B}=== CB — CACHE ===${E}`);
    console.log(`  Entrées en cache : ${status.cacheSize} / ${status.config.cacheMaxEntries}`);
    console.log(`  TTL              : ${status.config.cacheTtlSeconds}s`);
    console.log(`  Fichier          : ${cb.CACHE_FILE}`);
  } else {
    const status = cb.getStatus();
    const stateIcon = status.state === 'CLOSED' ? G+'CLOSED'+E : status.state === 'OPEN' ? R+'OPEN'+E : Y+'HALF_OPEN'+E;
    console.log(`\n${B}=== OBSERVABILITY — CIRCUIT BREAKER ===${E}`);
    console.log(`  État     : ${stateIcon}`);
    console.log(`  Échecs   : ${status.failures} / ${status.config.failureThreshold}`);
    console.log(`  Succès   : ${status.successes} / ${status.config.successThreshold}`);
    console.log(`  Cooldown : ${status.config.cooldownSeconds}s`);
    console.log(`  Cache    : ${status.cacheSize} entrées`);
    if (status.openedAt) console.log(`  Ouvert le: ${new Date(status.openedAt * 1000).toLocaleString('fr-FR')}`);
  }
}

// ── PROMPTS ───────────────────────────────────────────────────────────────────
function cmdPrompts(action, name) {
  if (action === 'list') {
    const prompts = ps.listAll();
    console.log(`\n${B}=== PROMPTS — LISTE (${prompts.length}) ===${E}\n`);
    if (!prompts.length) { console.log(`  ${Y}⚠  Aucun prompt stocké${E}`); return; }
    prompts.forEach(p => console.log(`  ${p.name.padEnd(30)} v${p.current_version.padEnd(8)} ×${p.metrics?.calls||0} appels  ${p.description?.slice(0,35)||''}`));
  } else if (action === 'history') {
    if (!name) { console.log(`  Usage: observability prompts history <name>`); return; }
    const versions = ps.listVersions(name);
    console.log(`\n${B}=== PROMPTS — HISTORY : ${name} ===${E}`);
    if (!versions.length) { console.log(`  ${Y}⚠  Prompt introuvable${E}`); return; }
    versions.forEach(v => {
      const cur = v.is_current ? G+' ← current'+E : '';
      console.log(`  v${v.version}  ${v.created_at?.slice(0,10)}  ${v.note?.slice(0,40)}${cur}`);
    });
  } else if (action === 'rollback') {
    if (!name) { console.log(`  Usage: observability prompts rollback <name>`); return; }
    try {
      const prev = ps.rollback(name);
      console.log(`  ${G}✓ ${name} rollback → v${prev}${E}`);
    } catch (e) { console.error(`  ${R}✗ ${e.message}${E}`); }
  } else {
    console.log(`\n  Sous-commandes prompts: list, history <name>, rollback <name>`);
  }
}

// ── REPORT ────────────────────────────────────────────────────────────────────
function cmdReport() {
  const traces  = tracer.loadTraces();
  const cbStatus = cb.getStatus();
  const prompts = ps.listAll();

  let totalCalls = traces.length, totalErrors = traces.filter(t => !t.success).length;
  let totalMs = traces.reduce((s, t) => s + (t.duration_ms||0), 0);
  const avgMs = totalCalls ? Math.round(totalMs / totalCalls) : 0;

  const html = `<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><title>Observability Report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>body{font-family:sans-serif;background:#0f172a;color:#e2e8f0;padding:24px}
h1{color:#7c3aed}h2{color:#94a3b8;font-size:1rem;margin-top:24px}
.card{background:#1e293b;border-radius:8px;padding:16px;margin:12px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:16px 0}
.metric{background:#1e293b;border-radius:8px;padding:16px;text-align:center}
.metric .val{font-size:1.8rem;font-weight:700;color:#7c3aed}
.metric .lbl{font-size:.75rem;color:#64748b;margin-top:4px}
.ok{color:#4ade80}.warn{color:#fbbf24}.err{color:#f87171}
table{width:100%;border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #1e293b;font-size:.85rem}
th{color:#64748b;text-align:left}</style></head>
<body>
<h1>🔭 Observability Report</h1>
<p style="color:#64748b">Généré le ${new Date().toLocaleString('fr-FR')}</p>
<div class="grid">
  <div class="metric"><div class="val">${totalCalls}</div><div class="lbl">Appels LLM</div></div>
  <div class="metric"><div class="val ${totalErrors>0?'err':'ok'}">${totalErrors}</div><div class="lbl">Erreurs</div></div>
  <div class="metric"><div class="val">${avgMs}ms</div><div class="lbl">Durée moy.</div></div>
  <div class="metric"><div class="val">${cbStatus.state==='CLOSED'?'<span class="ok">CLOSED</span>':cbStatus.state==='OPEN'?'<span class="err">OPEN</span>':'<span class="warn">HALF</span>'}</div><div class="lbl">Circuit Breaker</div></div>
  <div class="metric"><div class="val">${cbStatus.cacheSize}</div><div class="lbl">Cache LLM</div></div>
</div>
<div class="card"><h2>Appels LLM récents (20 derniers)</h2>
<table><tr><th>Date</th><th>Agent</th><th>Fonction</th><th>Durée</th><th>Statut</th></tr>
${traces.slice(-20).reverse().map(t=>`<tr>
  <td>${t.ts?.slice(11,19)||''}</td><td>${t.agent}</td><td>${t.fn}</td>
  <td class="${t.duration_ms>SLOW_MS?'err':t.duration_ms>3000?'warn':'ok'}">${Math.round(t.duration_ms||0)}ms</td>
  <td class="${t.success?'ok':'err'}">${t.success?'OK':'ERR'}</td>
</tr>`).join('')}
</table></div>
${prompts.length?`<div class="card"><h2>Prompts versionnés (${prompts.length})</h2>
<table><tr><th>Nom</th><th>Version</th><th>Appels</th><th>Description</th></tr>
${prompts.map(p=>`<tr><td>${p.name}</td><td>v${p.current_version}</td><td>${p.metrics?.calls||0}</td><td style="color:#94a3b8">${p.description?.slice(0,50)||''}</td></tr>`).join('')}
</table></div>`:''}
</body></html>`;

  const outPath = path.join(DOCS_DIR, 'observability-report.html');
  fs.writeFileSync(outPath, html, 'utf8');
  console.log(`  ${G}✓ ${outPath}${E}`);
}

// ── Main ──────────────────────────────────────────────────────────────────────
function main() {
  const args = process.argv.slice(2).filter(a => !a.startsWith('--'));
  const [cmd, sub, arg3] = args;

  switch (cmd) {
    case 'metrics':   cmdMetrics();         break;
    case 'anomalies': cmdAnomalies();       break;
    case 'cost':      cmdCost();            break;
    case 'cb':        cmdCb(sub);           break;
    case 'prompts':   cmdPrompts(sub, arg3);break;
    case 'report':    cmdReport();          break;
    case 'clear':     tracer.clearTraces(); console.log(`  ${G}✓ Traces effacées${E}`); break;
    default:
      console.log(`
${B}Observability Agent${E} — Monitoring LLM + Résilience + Prompts

  metrics             Métriques des appels LLM (appels, ms, P95, erreurs)
  anomalies           Détecte appels lents (>${SLOW_MS}ms) et bursts d'erreurs
  cost                Estimation coût tokens (Groq pricing)
  cb status           État du Circuit Breaker (CLOSED/OPEN/HALF_OPEN)
  cb reset            Réinitialise le Circuit Breaker
  cb cache            Statistiques du cache LLM
  prompts list        Liste les prompts versionnés
  prompts history <n> Historique des versions d'un prompt
  prompts rollback <n>Rollback à la version précédente
  report              Génère docs/observability-report.html
  clear               Vide logs/traces.jsonl

Coût LLM : $0 — 100% déterministe
`);
  }
}

main();
