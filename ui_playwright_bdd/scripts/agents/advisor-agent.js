'use strict';
// ============================================================
// Advisor Agent — Décisions Release & Intelligence Prédictive
// ============================================================
// Absorbe : release-advisor-agent, predictive-agent, memory-agent
//
// Usage:
//   node scripts/agents/advisor-agent.js advise [N]      Go/No-Go release (N votes, défaut 3)
//   node scripts/agents/advisor-agent.js predict         Prédit les prochains échecs
//   node scripts/agents/advisor-agent.js gate            Quality Gate LLM
//   node scripts/agents/advisor-agent.js history <tc>    Historique d'un test
//   node scripts/agents/advisor-agent.js memory seed     Injecte des données démo
//   node scripts/agents/advisor-agent.js memory recurring Échecs récurrents
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
const memory = require('./shared/memory-store');

const FRAMEWORK   = path.join(__dirname, '..', '..');
const RESULTS_DIR = path.join(FRAMEWORK, 'allure-results');
const DOCS_DIR    = path.join(FRAMEWORK, 'docs');

fs.mkdirSync(DOCS_DIR, { recursive: true });

const DRY_RUN = process.argv.includes('--dry-run');
const N_VOTES = parseInt(process.argv.find(a => /^\d+$/.test(a)) || '3');

const G = '\x1b[32m', R = '\x1b[31m', Y = '\x1b[33m', C = '\x1b[36m', B = '\x1b[1m', E = '\x1b[0m';

// ── Contexte release ───────────────────────────────────────────────────────────
function collectContext() {
  if (!fs.existsSync(RESULTS_DIR)) return { total: 0, passed: 0, failed: 0, pass_rate: 0, failures: [] };
  const results = fs.readdirSync(RESULTS_DIR)
    .filter(f => f.endsWith('-result.json'))
    .map(f => { try { return JSON.parse(fs.readFileSync(path.join(RESULTS_DIR, f), 'utf8')); } catch { return null; } })
    .filter(Boolean);

  const s = { total: 0, passed: 0, failed: 0, broken: 0, skipped: 0, failures: [] };
  for (const r of results) {
    s.total++;
    if (r.status in s) s[r.status]++;
    if (['failed','broken'].includes(r.status)) s.failures.push({ name: r.name, message: (r.statusDetails?.message||'').slice(0,200) });
  }
  s.pass_rate = s.total ? Math.round(s.passed / s.total * 1000) / 10 : 0;
  return s;
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
  console.log(`\n${B}=== ADVISOR — RELEASE ADVISE (${nVotes} votes) [${llm.MODEL}] ===${E}`);
  const ctx    = collectContext();
  const agentSummary = memory.getAgentSummary('quality-agent', 3);

  console.log(`  ${C}Contexte : ${ctx.pass_rate}% (${ctx.passed}/${ctx.total}) | ${ctx.failures.length} échec(s)${E}`);
  console.log(`  ${C}Self-consistency : ${nVotes} votes indépendants...${E}\n`);

  const prompt = `Tu es un Release Manager expert. Décide si ce build Playwright est prêt pour la production.

Métriques de test:
- Pass rate : ${ctx.pass_rate}% (${ctx.passed}/${ctx.total} tests)
- Échecs : ${ctx.failures.length}
- Tests cassés : ${ctx.broken}
- Tests ignorés : ${ctx.skipped}

Détail des échecs:
${ctx.failures.slice(0,5).map(f => `- ${f.name}: ${f.message}`).join('\n') || 'Aucun'}

Historique agent qualité:
${agentSummary}

Critères Go: pass_rate ≥ 90%, pas de bloquant critique, échecs < 5%`;

  const messages = [{ role: 'user', content: prompt }];
  const span     = new tracer.Span('adviseSelfConsistent', prompt, llm.MODEL).begin();

  try {
    const { responses, winner, vote_counts, n_votes } = await llm.chatSelfConsistent(messages, VOTE_SCHEMA, nVotes);
    span.end(true);

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

// ── PREDICT — Prédiction des prochains échecs ─────────────────────────────────
const PREDICT_SCHEMA = {
  tc:              'string — identifiant du test',
  failure_risk:    'float 0.0-1.0 — probabilité d\'échec',
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

  console.log(`  ${C}${Object.keys(recurring).length} tests récurrents analysés...${E}\n`);

  for (const [tc, stats] of Object.entries(recurring).slice(0, 10)) {
    const context = memory.getContextFor(tc);
    const span    = new tracer.Span('predictStructured', tc, llm.MODEL).begin();

    try {
      const prompt = `Prédit le risque d'échec futur pour ce test Playwright.

Test : ${tc}
Historique :
${context}
Statistiques : ${stats.count} occurrences, catégorie dominante: ${stats.dominant_category}`;

      const pred = await llm.chatStructured([{ role: 'user', content: prompt }], PREDICT_SCHEMA);
      span.end(true);

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
    const prompt = `Évalue la qualité de ce build Playwright et donne un score 0-100.

Pass rate: ${ctx.pass_rate}% | Échecs: ${ctx.failures.length} | Total: ${ctx.total}

Critères: pass_rate≥90% PASS, ≥80% WARNING, <80% FAIL`;

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
  if (!tcId) { console.log(`  Usage: advisor history <test-name>`); return; }
  console.log(`\n${B}=== ADVISOR — HISTORY : ${tcId} ===${E}`);
  const hist = memory.getTcHistory(tcId, 10);
  if (!hist.length) { console.log(`  ${Y}⚠  Aucun historique pour ${tcId}${E}`); return; }
  console.log(`  ${C}${hist.length} entrées dans la mémoire épisodique${E}\n`);
  hist.forEach(h => {
    const icon = (h.category === 'real_bug' || h.verdict === 'NO-GO') ? R+'✗'+E : G+'✓'+E;
    console.log(`  ${icon} ${h.ts.slice(0,10)}  ${h.agent.padEnd(20)}  ${h.category||h.verdict||'?'}  conf:${h.confidence!=null?Math.round(h.confidence*100)+'%':'?'}`);
  });
  console.log(`\n  ${memory.getContextFor(tcId)}`);
}

// ── MEMORY ────────────────────────────────────────────────────────────────────
function cmdMemory(action) {
  if (action === 'recurring') {
    console.log(`\n${B}=== ADVISOR — MÉMOIRE RÉCURRENTE ===${E}`);
    const rec = memory.getRecurringFailures(2);
    if (!Object.keys(rec).length) { console.log(`  ${Y}⚠  Aucun échec récurrent${E}`); return; }
    Object.entries(rec).forEach(([tc, s]) => {
      console.log(`  ${R}⚠${E}  ${tc.slice(0,50).padEnd(50)}  ×${s.count}  ${s.dominant_category}  last: ${s.last_seen.slice(0,10)}`);
    });
  } else if (action === 'seed') {
    console.log(`\n${B}=== ADVISOR — SEED MÉMOIRE ===${E}`);
    const demos = [
      { tc: 'Login - credentials invalides', category: 'real_bug', confidence: 0.92 },
      { tc: 'Checkout - paiement timeout',   category: 'flaky',    confidence: 0.78 },
      { tc: 'Dashboard - chargement lent',   category: 'env_issue',confidence: 0.65 },
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
<html lang="fr"><head><meta charset="UTF-8"><title>Advisor Report</title>
<style>body{font-family:sans-serif;background:#0f172a;color:#e2e8f0;padding:24px}
h1{color:#7c3aed}h2{color:#94a3b8;font-size:1rem;margin-top:24px}
.card{background:#1e293b;border-radius:8px;padding:16px;margin:12px 0}
.go{color:#4ade80}.nogo{color:#f87171}.warn{color:#fbbf24}
table{width:100%;border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #1e293b}
th{color:#64748b;text-align:left}</style></head>
<body>
<h1>🧠 Advisor Report — ${new Date().toLocaleDateString('fr-FR')}</h1>
<div class="card"><h2>Contexte Build</h2>
<p>Pass rate: <strong>${ctx.pass_rate}%</strong> (${ctx.passed}/${ctx.total}) | Échecs: ${ctx.failures.length}</p></div>
<div class="card"><h2>Échecs Récurrents (≥2 occurrences)</h2>
<table><tr><th>Test</th><th>Occurrences</th><th>Catégorie</th><th>Dernier</th></tr>
${Object.entries(recurring).map(([tc,s])=>`<tr><td>${tc}</td><td class="nogo">${s.count}</td><td>${s.dominant_category}</td><td>${s.last_seen.slice(0,10)}</td></tr>`).join('')||'<tr><td colspan="4" style="color:#4ade80">Aucun</td></tr>'}
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
${B}Advisor Agent${E} — Décisions Release & Intelligence Prédictive

  advise [N]           Go/No-Go release par self-consistency (N votes, défaut 3)
  predict              Prédit les prochains échecs depuis la mémoire épisodique
  gate                 Quality Gate avec score LLM (0-100)
  history <test>       Historique complet d'un test dans la mémoire
  memory               Affiche les épisodes mémorisés
  memory recurring     Échecs récurrents (≥2 occurrences)
  memory seed          Injecte des données de démo
  report               Génère docs/advisor-report.html

Options:
  --dry-run    Simulation sans écriture
  N            Nombre de votes pour advise (ex: advisor advise 5)
`);
  }
}

main().catch(e => { console.error(R + e.message + E); process.exit(1); });
