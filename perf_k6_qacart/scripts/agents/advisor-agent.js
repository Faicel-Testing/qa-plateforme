'use strict';
// ============================================================
// Advisor Agent — Décisions Release & Intelligence Prédictive (Performance)
// ============================================================
// Usage:
//   node scripts/agents/advisor-agent.js advise [N]      Go/No-Go release perf (N votes, défaut 3)
//   node scripts/agents/advisor-agent.js predict         Prédit les prochaines dégradations
//   node scripts/agents/advisor-agent.js gate            Quality Gate LLM
//   node scripts/agents/advisor-agent.js history <name>  Historique d'un scénario/métrique
//   node scripts/agents/advisor-agent.js memory seed     Injecte des données démo
//   node scripts/agents/advisor-agent.js memory recurring Dégradations récurrentes
//   node scripts/agents/advisor-agent.js report          Génère docs/advisor-report.html
//
// Guards: Self-consistency N votes (défaut 3, configurable)
// ============================================================
require('dotenv').config();
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';

const fs     = require('fs');
const path   = require('path');
const llm    = require('./llm');
const tracer = require('./shared/tracer');
const memory      = require('./shared/memory-store');
const promptStore = require('./shared/prompt-store');

function fmt(template, vars) {
  let result = template;
  for (const [k, v] of Object.entries(vars)) {
    result = result.split('{' + k + '}').join(String(v ?? '?'));
  }
  return result;
}

const FRAMEWORK   = path.join(__dirname, '..', '..');
const REPORTS_DIR = path.join(FRAMEWORK, 'reports');
const DOCS_DIR    = path.join(FRAMEWORK, 'docs');
const SCENARIOS   = ['smoke', 'load', 'stress'];

fs.mkdirSync(DOCS_DIR, { recursive: true });

const DRY_RUN = process.argv.includes('--dry-run');
const N_VOTES = parseInt(process.argv.find(a => /^\d+$/.test(a)) || '3');

const G = '\x1b[32m', R = '\x1b[31m', Y = '\x1b[33m', C = '\x1b[36m', B = '\x1b[1m', E = '\x1b[0m';

// ── Contexte release ───────────────────────────────────────────────────────────
function collectContext() {
  const ctx = { scenarios: {}, total_breaches: 0, breaches: [] };
  for (const scenario of SCENARIOS) {
    const fp = path.join(REPORTS_DIR, `summary-${scenario}.json`);
    if (!fs.existsSync(fp)) continue;
    let summary;
    try { summary = JSON.parse(fs.readFileSync(fp, 'utf8')); } catch { continue; }

    const dur = summary.metrics?.http_req_duration || {};
    const checks = summary.metrics?.checks || { passes: 0, fails: 0 };
    const httpFailed = summary.metrics?.http_req_failed || { value: 0 };

    const breaches = [];
    for (const [metricName, metric] of Object.entries(summary.metrics || {})) {
      for (const [expr, wasBreached] of Object.entries(metric.thresholds || {})) {
        if (wasBreached) breaches.push({ metric: metricName, expr });
      }
    }

    ctx.scenarios[scenario] = {
      p95_ms: Math.round(dur['p(95)'] || 0),
      avg_ms: Math.round(dur.avg || 0),
      error_rate: Math.round((httpFailed.value || 0) * 1000) / 10,
      checks_pass_rate: (checks.passes + checks.fails) ? Math.round(checks.passes / (checks.passes + checks.fails) * 1000) / 10 : 0,
      breaches,
    };
    ctx.total_breaches += breaches.length;
    ctx.breaches.push(...breaches.map(b => ({ scenario, ...b })));
  }
  return ctx;
}

// ── ADVISE — Self-Consistency voting ──────────────────────────────────────────
const VOTE_SCHEMA = {
  verdict:   'GO | NO-GO',
  risk:      'low | medium | high | critical',
  blockers:  'array of string — points bloquants (vide si GO)',
  warnings:  'array of string — points à surveiller',
  reasoning: 'string — justification en 2-3 phrases',
};

async function cmdAdvise(nVotes = N_VOTES) {
  console.log(`\n${B}=== ADVISOR — RELEASE ADVISE PERF (${nVotes} votes) [${llm.MODEL}] ===${E}`);
  const ctx = collectContext();
  const agentSummary = memory.getAgentSummary('quality-agent', 3);

  const scenarioSummary = Object.entries(ctx.scenarios).map(([s, m]) => `${s}: p95=${m.p95_ms}ms err=${m.error_rate}% checks=${m.checks_pass_rate}%`).join(' | ');
  console.log(`  ${C}Contexte : ${scenarioSummary} | ${ctx.total_breaches} seuil(s) dépassé(s)${E}`);
  console.log(`  ${C}Self-consistency : ${nVotes} votes indépendants...${E}\n`);

  const breachDetail = ctx.breaches.slice(0,8).map(b => `- ${b.scenario}/${b.metric}: ${b.expr}`).join('\n') || 'Aucun';
  const _tpl = promptStore.get('release_vote') ||
    'Tu es un Release Manager expert en performance. Décide si ce build est prêt pour la production, du point de vue charge/latence.\n\n' +
    'Métriques par scénario:\n{scenario_summary}\n\n' +
    'Seuils dépassés ({failures_count}):\n{fail_detail}\n\n' +
    'Historique agent qualité:\n{agent_summary}\n\n' +
    'Contexte : QACart Todo tourne sur un dyno Heroku gratuit partagé (pas d\'infra dédiée) — ' +
    'une dégradation en stress (@stress) est attendue et non-bloquante ; un dépassement en smoke/load ' +
    'est plus préoccupant. Critères Go: smoke et load sans dépassement critique.';
  const prompt = fmt(_tpl, {
    scenario_summary: scenarioSummary, failures_count: ctx.total_breaches, fail_detail: breachDetail,
    agent_summary: agentSummary,
    pass_rate: ctx.scenarios.load?.checks_pass_rate ?? 'N/A', passed: 'N/A', total: 'N/A',
    broken: 0, skipped: 0, context_str: scenarioSummary,
    fail_rate: ctx.scenarios.load?.error_rate ?? 'N/A',
    flaky_count: 'N/A', critical_bugs: 'N/A', high_bugs: 'N/A', medium_bugs: 'N/A',
  });

  const messages = [{ role: 'user', content: prompt }];
  const span     = new tracer.Span('adviseSelfConsistent', prompt, llm.MODEL).begin();

  try {
    const { responses, winner, vote_counts, n_votes } = await llm.chatSelfConsistent(messages, VOTE_SCHEMA, nVotes);
    span.end(true);
    promptStore.recordUsage('release_vote');

    console.log(`  ${B}Votes (${n_votes}/${nVotes}) :${E}`);
    responses.forEach((r, i) => {
      const icon = r.verdict === 'GO' ? G+'GO'+E : R+'NO-GO'+E;
      console.log(`  Vote ${i+1}: ${icon}  risque=${r.risk}  ${r.reasoning?.slice(0,60)||''}`);
    });

    if (winner) {
      const verdictIcon = winner.verdict === 'GO' ? G + '✅ GO — RELEASE AUTORISÉE' + E : R + '❌ NO-GO — BLOCAGE RELEASE' + E;
      console.log(`\n  ${B}Décision finale :${E} ${verdictIcon}`);
      console.log(`  Risque : ${winner.risk?.toUpperCase()}`);
      if (winner.blockers?.length) { console.log(`  ${R}Bloquants :${E}`); winner.blockers.forEach(b => console.log(`    • ${b}`)); }
      if (winner.warnings?.length) { console.log(`  ${Y}Warnings :${E}`);  winner.warnings.forEach(w => console.log(`    • ${w}`)); }
      console.log(`\n  ${C}${winner.reasoning||''}${E}`);

      memory.recordEpisode('advisor-agent', [{ verdict: winner.verdict, risk: winner.risk, votes: vote_counts }], `Release: ${winner.verdict} (risque ${winner.risk})`, 'advise');
    }
  } catch (e) {
    span.error = e.message; span.end(false);
    console.error(`  ${R}✗ ${e.message}${E}`);
  }
}

// ── PREDICT — Prédiction des prochaines dégradations ──────────────────────────
const PREDICT_SCHEMA = {
  tc:              'string — identifiant scénario/métrique',
  failure_risk:    'float 0.0-1.0 — probabilité de dépassement futur',
  trend:           'stable | degrading | improving',
  predicted_cause: 'string — cause probable',
  recommendation:  'string — action préventive',
};

async function cmdPredict() {
  console.log(`\n${B}=== ADVISOR — PREDICT [${llm.MODEL}] ===${E}`);
  const recurring = memory.getRecurringFailures(2);
  const episodes  = memory.loadAllEpisodes(null, 20);

  if (!Object.keys(recurring).length && !episodes.length) {
    console.log(`  ${Y}⚠  Pas assez d'historique — lance d'abord quelques runs${E}`); return;
  }

  console.log(`  ${C}${Object.keys(recurring).length} métriques récurrentes analysées...${E}\n`);

  for (const [tc, stats] of Object.entries(recurring).slice(0, 10)) {
    const context = memory.getContextFor(tc);
    const span    = new tracer.Span('predictStructured', tc, llm.MODEL).begin();

    try {
      const _tpl = promptStore.get('predict_gate') ||
        'Prédit le risque de dépassement futur pour cette métrique k6.\n\n' +
        'Métrique : {test_name}\nHistorique :\n{context}\n' +
        'Statistiques : {count} occurrences, catégorie dominante: {dominant_category}';
      const prompt = fmt(_tpl, {
        test_name: tc, context, count: stats.count,
        dominant_category: stats.dominant_category,
        pass_rate: 'N/A', passed: 'N/A', total: 'N/A',
        failures_count: stats.count, broken: 0, history_summary: context,
      });

      const pred = await llm.chatStructured([{ role: 'user', content: prompt }], PREDICT_SCHEMA);
      span.end(true);
      promptStore.recordUsage('predict_gate', pred.failure_risk);

      const riskPct = Math.round((pred.failure_risk || 0) * 100);
      const riskIcon = riskPct >= 70 ? R+'⚠ HIGH'+E : riskPct >= 40 ? Y+'~ MED'+E : G+'✓ LOW'+E;
      console.log(`  ${riskIcon}  ${tc.slice(0,45).padEnd(45)}  ${riskPct}%  ${pred.trend||'?'}  ${pred.recommendation?.slice(0,40)||''}`);
    } catch (e) {
      span.error = e.message; span.end(false);
      console.error(`  ${R}✗ ${tc}: ${e.message}${E}`);
    }
  }
}

// ── GATE — Quality Gate LLM ───────────────────────────────────────────────────
async function cmdGate() {
  console.log(`\n${B}=== ADVISOR — GATE [${llm.MODEL}] ===${E}`);
  const ctx  = collectContext();
  const span = new tracer.Span('gateStructured', JSON.stringify(ctx), llm.MODEL).begin();

  const GATE_SCHEMA = {
    verdict:     'PASS | FAIL',
    score:       'integer 0-100',
    blockers:    'array of string',
    improvement: 'string — suggestion principale',
  };

  try {
    const scenarioSummary = Object.entries(ctx.scenarios).map(([s, m]) => `${s}: p95=${m.p95_ms}ms err=${m.error_rate}%`).join(' | ');
    const prompt = `Évalue la qualité performance de ce build k6 et donne un score 0-100.

${scenarioSummary}
Seuils dépassés: ${ctx.total_breaches}

Critères: 0 dépassement en smoke/load → PASS, dépassement uniquement en stress (dyno gratuit partagé) → WARNING, dépassement en smoke/load → FAIL`;

    const gate = await llm.chatStructured([{ role: 'user', content: prompt }], GATE_SCHEMA);
    span.end(true);

    const icon = gate.verdict === 'PASS' ? G+'✅ PASS'+E : R+'❌ FAIL'+E;
    console.log(`\n  ${icon}  Score : ${gate.score}/100`);
    if (gate.blockers?.length) gate.blockers.forEach(b => console.log(`  ${R}• ${b}${E}`));
    if (gate.improvement) console.log(`  ${C}→ ${gate.improvement}${E}`);
  } catch (e) {
    span.error = e.message; span.end(false);
    console.error(`  ${R}✗ ${e.message}${E}`);
  }
}

// ── HISTORY ───────────────────────────────────────────────────────────────────
function cmdHistory(tcId) {
  if (!tcId) { console.log(`  Usage: advisor history <scenario/metric>`); return; }
  console.log(`\n${B}=== ADVISOR — HISTORY : ${tcId} ===${E}`);
  const hist = memory.getTcHistory(tcId, 10);
  if (!hist.length) { console.log(`  ${Y}⚠  Aucun historique pour ${tcId}${E}`); return; }
  console.log(`  ${C}${hist.length} entrées dans la mémoire épisodique${E}\n`);
  hist.forEach(h => {
    const icon = (h.category === 'backend_degradation' || h.verdict === 'NO-GO') ? R+'✗'+E : G+'✓'+E;
    console.log(`  ${icon} ${h.ts.slice(0,10)}  ${h.agent.padEnd(20)}  ${h.category||h.verdict||'?'}  conf:${h.confidence!=null?Math.round(h.confidence*100)+'%':'?'}`);
  });
  console.log(`\n  ${memory.getContextFor(tcId)}`);
}

// ── MEMORY ────────────────────────────────────────────────────────────────────
function cmdMemory(action) {
  if (action === 'recurring') {
    console.log(`\n${B}=== ADVISOR — MÉMOIRE RÉCURRENTE ===${E}`);
    const rec = memory.getRecurringFailures(2);
    if (!Object.keys(rec).length) { console.log(`  ${Y}⚠  Aucune dégradation récurrente${E}`); return; }
    Object.entries(rec).forEach(([tc, s]) => {
      console.log(`  ${R}⚠${E}  ${tc.slice(0,50).padEnd(50)}  ×${s.count}  ${s.dominant_category}  last: ${s.last_seen.slice(0,10)}`);
    });
  } else if (action === 'seed') {
    console.log(`\n${B}=== ADVISOR — SEED MÉMOIRE ===${E}`);
    const demos = [
      { tc: 'stress/http_req_duration', category: 'env_shared_demo', confidence: 0.82 },
      { tc: 'load/http_req_failed',     category: 'test_config_too_aggressive', confidence: 0.71 },
    ];
    for (const d of demos) {
      memory.recordEpisode('quality-agent', [d], `Demo: ${d.category}`, 'seed');
      console.log(`  ${G}✓${E} ${d.tc}`);
    }
  } else {
    const eps = memory.loadAllEpisodes(null, 10);
    console.log(`\n${B}=== ADVISOR — MÉMOIRE (${eps.length} épisodes) ===${E}`);
    eps.slice(-10).reverse().forEach(ep => {
      console.log(`  ${ep.ts.slice(0,10)}  ${ep.agent.padEnd(20)}  ${ep.summary?.slice(0,50)||''}`);
    });
  }
}

// ── REPORT ────────────────────────────────────────────────────────────────────
function cmdReport() {
  const ctx      = collectContext();
  const episodes = memory.loadAllEpisodes(null, 20);
  const recurring = memory.getRecurringFailures(2);

  const html = `<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><title>Advisor Report — k6 Performance</title>
<style>body{font-family:sans-serif;background:#0f172a;color:#e2e8f0;padding:24px}
h1{color:#7c3aed}h2{color:#94a3b8;font-size:1rem;margin-top:24px}
.card{background:#1e293b;border-radius:8px;padding:16px;margin:12px 0}
.go{color:#4ade80}.nogo{color:#f87171}.warn{color:#fbbf24}
table{width:100%;border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #1e293b}
th{color:#64748b;text-align:left}</style></head>
<body>
<h1>🧠 Advisor Report Performance — ${new Date().toLocaleDateString('fr-FR')}</h1>
<div class="card"><h2>Contexte Build</h2>
<table><tr><th>Scénario</th><th>p95</th><th>Err rate</th><th>Checks</th></tr>
${Object.entries(ctx.scenarios).map(([s,m])=>`<tr><td>${s}</td><td>${m.p95_ms}ms</td><td>${m.error_rate}%</td><td>${m.checks_pass_rate}%</td></tr>`).join('')}
</table></div>
<div class="card"><h2>Dégradations Récurrentes (≥2 occurrences)</h2>
<table><tr><th>Métrique</th><th>Occurrences</th><th>Catégorie</th><th>Dernier</th></tr>
${Object.entries(recurring).map(([tc,s])=>`<tr><td>${tc}</td><td class="nogo">${s.count}</td><td>${s.dominant_category}</td><td>${s.last_seen.slice(0,10)}</td></tr>`).join('')||'<tr><td colspan="4" style="color:#4ade80">Aucune</td></tr>'}
</table></div>
<div class="card"><h2>Historique Épisodique (20 derniers)</h2>
<table><tr><th>Date</th><th>Agent</th><th>Résumé</th></tr>
${episodes.slice(-20).reverse().map(ep=>`<tr><td>${ep.ts.slice(0,10)}</td><td>${ep.agent}</td><td>${ep.summary?.slice(0,60)||''}</td></tr>`).join('')}
</table></div>
</body></html>`;

  const outPath = path.join(DOCS_DIR, 'advisor-report.html');
  if (!DRY_RUN) { fs.writeFileSync(outPath, html, 'utf8'); console.log(`  ${G}✓ ${outPath}${E}`); }
}

// ── Main ──────────────────────────────────────────────────────────────────────
async function main() {
  const args = process.argv.slice(2).filter(a => !a.startsWith('--') && !/^\d+$/.test(a));
  const [cmd, sub] = args;
  await llm.assertRunning();

  switch (cmd) {
    case 'advise':  await cmdAdvise(N_VOTES); break;
    case 'predict': await cmdPredict();       break;
    case 'gate':    await cmdGate();          break;
    case 'history': cmdHistory(sub);          break;
    case 'memory':  cmdMemory(sub);           break;
    case 'report':  cmdReport();              break;
    default:
      console.log(`
${B}Advisor Agent${E} — Décisions Release & Intelligence Prédictive (Performance)

  advise [N]           Go/No-Go release perf par self-consistency (N votes, défaut 3)
  predict               Prédit les prochaines dégradations depuis la mémoire épisodique
  gate                  Quality Gate avec score LLM (0-100)
  history <scénario>    Historique complet d'un scénario/métrique dans la mémoire
  memory                Affiche les épisodes mémorisés
  memory recurring      Dégradations récurrentes (≥2 occurrences)
  memory seed            Injecte des données de démo
  report                 Génère docs/advisor-report.html

Options:
  --dry-run    Simulation sans écriture
  N            Nombre de votes pour advise (ex: advisor advise 5)
`);
  }
}

main().catch(e => { console.error(R + e.message + E); process.exit(1); });
