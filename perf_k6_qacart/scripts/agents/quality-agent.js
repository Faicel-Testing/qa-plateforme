'use strict';
// ============================================================
// Quality Agent — Intelligence Qualité Performance
// ============================================================
// Usage:
//   node scripts/agents/quality-agent.js triage          Classifie les seuils dépassés
//   node scripts/agents/quality-agent.js rca             Root Cause Analysis (CoT)
//   node scripts/agents/quality-agent.js verify          Vérification adversariale des scénarios
//   node scripts/agents/quality-agent.js full            triage + rca + verify
//
// Guards:
//   CONFIDENCE_THRESHOLD=0.70   Seuil en dessous duquel l'adversarial se déclenche
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

const FRAMEWORK     = path.join(__dirname, '..', '..');
const REPORTS_DIR   = path.join(FRAMEWORK, 'reports');
const DOCS_DIR       = path.join(FRAMEWORK, 'docs');
const SCENARIOS_DIR  = path.join(FRAMEWORK, 'k6', 'scenarios');
const SCENARIOS      = ['smoke', 'load', 'stress'];

fs.mkdirSync(DOCS_DIR, { recursive: true });

const CONFIDENCE_THRESHOLD = parseFloat(process.env.CONFIDENCE_THRESHOLD || '0.70');

const G = '\x1b[32m', R = '\x1b[31m', Y = '\x1b[33m', C = '\x1b[36m', B = '\x1b[1m', E = '\x1b[0m';

// ── Lecture reports/summary-*.json ─────────────────────────────────────────────
function loadBreaches() {
  const breaches = [];
  for (const scenario of SCENARIOS) {
    const fp = path.join(REPORTS_DIR, `summary-${scenario}.json`);
    if (!fs.existsSync(fp)) continue;
    let summary;
    try { summary = JSON.parse(fs.readFileSync(fp, 'utf8')); } catch { continue; }

    for (const [metricName, metric] of Object.entries(summary.metrics || {})) {
      for (const [expr, wasBreached] of Object.entries(metric.thresholds || {})) {
        if (!wasBreached) continue;
        breaches.push({
          name: `${scenario}/${metricName}`,
          scenario, metric: metricName, expr,
          value: metric['p(95)'] ?? metric.value ?? metric.avg ?? null,
        });
      }
    }
  }
  return breaches;
}

// ── TRIAGE ────────────────────────────────────────────────────────────────────
const TRIAGE_SCHEMA = {
  category:   'backend_degradation | test_config_too_aggressive | network_flakiness | env_shared_demo',
  confidence: 'float 0.0-1.0',
  reasoning:  'string — justification courte (1-2 phrases)',
};

async function cmdTriage() {
  console.log(`\n${B}=== QUALITY — TRIAGE [${llm.MODEL}] ===${E}`);
  const breaches = loadBreaches();
  if (!breaches.length) { console.log(`  ${G}✓ Aucun seuil dépassé dans reports/${E}`); return []; }
  console.log(`  ${C}${breaches.length} seuil(s) dépassé(s) à analyser${E}\n`);

  const results = [];
  for (const b of breaches) {
    const context = memory.getContextFor(b.name);
    const span    = new tracer.Span('triageChatConfident', b.name, llm.MODEL).begin();

    const _tpl = promptStore.get('triage_classify') ||
      'Tu es un expert en tests de performance k6. Classifie ce dépassement de seuil.\n\n' +
      'Scénario : {test_name}\nMétrique : {status}\nExpression seuil : {error_message}\n' +
      'Valeur observée : {stack_trace}\nHistorique : {context}\n\n' +
      'Catégories possibles:\n' +
      '- backend_degradation         : Le backend réel est plus lent sous charge\n' +
      '- test_config_too_aggressive  : Le seuil ou la charge du scénario est mal calibré\n' +
      '- network_flakiness           : Variance réseau/latence ponctuelle\n' +
      '- env_shared_demo             : Dégradation due à l\'infra partagée (démo publique, dyno gratuit)';
    const prompt = fmt(_tpl, {
      test_name: b.name, status: b.metric, error_message: b.expr,
      stack_trace: `valeur observée: ${b.value}`, context,
      feature_file: 'N/A', scenario_name: b.scenario, failed_step: 'N/A',
      screenshot_path: 'N/A', browser: 'N/A', current_url: 'N/A',
    });

    try {
      const result = await llm.chatConfident([{ role: 'user', content: prompt }], CONFIDENCE_THRESHOLD);
      span.confidence = result.confidence; span.end(true);
      promptStore.recordUsage('triage_classify', result.confidence);

      const icon = { backend_degradation: R+'🐢'+E, test_config_too_aggressive: Y+'⚙️'+E, network_flakiness: C+'📶'+E, env_shared_demo: '\x1b[2m'+'☁️'+E }[result.result] || '?';
      const confIcon = result.confidence >= CONFIDENCE_THRESHOLD ? G : Y;
      console.log(`  ${icon} ${b.name.slice(0,50).padEnd(50)} ${confIcon}${Math.round(result.confidence*100)}%${E}  ${result.result}`);

      results.push({ ...b, category: result.result, confidence: result.confidence });
      memory.recordEpisode('quality-agent', [{ tc: b.name, category: result.result, confidence: result.confidence }], `Triage: ${result.result}`, 'triage');
    } catch (e) {
      span.error = e.message; span.end(false);
      console.error(`  ${R}✗ ${b.name}: ${e.message}${E}`);
      results.push({ ...b, category: 'unknown', confidence: 0 });
    }
  }

  const byCategory = results.reduce((acc, r) => { acc[r.category] = (acc[r.category]||0)+1; return acc; }, {});
  console.log(`\n  ${B}Résumé :${E} ${Object.entries(byCategory).map(([k,v])=>`${k}×${v}`).join('  ')}`);
  return results;
}

// ── RCA — Root Cause Analysis (Chain of Thought) ──────────────────────────────
const RCA_SCHEMA = {
  root_cause:     'string — cause racine en 1 phrase',
  cause_category: 'latency | error_rate | throughput | config | infra_partagee | unknown',
  affected_layer: 'backend | database | network | k6_config | infra',
  fix_action:     'string — action corrective concrète',
  fix_priority:   'immediate | high | medium | low',
  related_scenarios: 'array of string — scénarios potentiellement affectés',
};

async function cmdRca() {
  console.log(`\n${B}=== QUALITY — RCA [${llm.MODEL}] ===${E}`);
  const breaches = loadBreaches();
  if (!breaches.length) { console.log(`  ${G}✓ Aucun seuil dépassé${E}`); return []; }

  const groups = {};
  for (const b of breaches) {
    const key = b.metric;
    if (!groups[key]) groups[key] = [];
    groups[key].push(b);
  }

  console.log(`  ${C}${breaches.length} dépassement(s) regroupés en ${Object.keys(groups).length} groupes${E}\n`);
  const analyses = [];

  for (const [key, group] of Object.entries(groups)) {
    console.log(`  ${B}Groupe (${group.length} scénarios) :${E} ${key}`);
    const span = new tracer.Span('rcaChatCot', key, llm.MODEL).begin();

    const failList = group.map(b => `- ${b.scenario}: ${b.expr} (observé: ${b.value})`).join('\n');
    const _rcaTpl = promptStore.get('rca_analyze') ||
      'Tu es un expert en tests de performance k6. Analyse la cause racine de ces dépassements de seuil.\n\n' +
      'Groupe ({count} scénarios):\n{fail_list}\n\n' +
      'Raisonne étape par étape (ÉTAPE 1, ÉTAPE 2, CONCLUSION) avant de conclure.';
    const prompt = fmt(_rcaTpl, {
      count: group.length, fail_list: failList,
      test_name: key, tc: key, tc_id: key, us: 'N/A', us_id: 'N/A',
      error_message: key, stack_trace: failList, suite: 'k6',
      method: 'N/A', endpoint: 'N/A',
    });

    try {
      const { reasoning, structured } = await llm.chatCot(
        [{ role: 'user', content: prompt }],
        `Maintenant extrais la cause racine en JSON selon ce schéma:\n${JSON.stringify(RCA_SCHEMA, null, 2)}\n\nRéponds UNIQUEMENT avec le JSON.`
      );

      let rca = {};
      const m = (structured || '').match(/\{[\s\S]*\}/);
      if (m) { try { rca = JSON.parse(m[0]); } catch {} }

      span.end(true);
      promptStore.recordUsage('rca_analyze');
      console.log(`  ${G}→ ${rca.cause_category || '?'}${E} | ${rca.fix_priority || '?'} | ${rca.fix_action?.slice(0,50)||''}`);
      console.log(`\x1b[2m  Raisonnement: ${reasoning.slice(0,100)}...\x1b[0m\n`);

      analyses.push({ group: key, scenarios: group.map(b=>b.scenario), rca, reasoning });
    } catch (e) {
      span.error = e.message; span.end(false);
      console.error(`  ${R}✗ ${e.message}${E}`);
    }
  }

  if (!process.argv.includes('--dry-run')) {
    fs.writeFileSync(path.join(DOCS_DIR, 'rca-report.json'), JSON.stringify({ ts: new Date().toISOString(), analyses }, null, 2), 'utf8');
    console.log(`  ${G}✓ docs/rca-report.json${E}`);
  }
  return analyses;
}

// ── VERIFY — Vérification adversariale ────────────────────────────────────────
async function cmdVerify() {
  console.log(`\n${B}=== QUALITY — VERIFY (adversarial) [${llm.MODEL}] ===${E}`);

  const checks = [
    { name: 'Scénarios k6',    path: SCENARIOS_DIR, ext: '.js' },
    { name: 'Résultats k6',    path: REPORTS_DIR,   ext: '.json' },
  ];

  const verdicts = [];
  for (const check of checks) {
    if (!fs.existsSync(check.path)) { console.log(`  ${Y}⚠  ${check.name}: dossier absent${E}`); continue; }
    const files = fs.readdirSync(check.path).filter(f => f.endsWith(check.ext));
    console.log(`\n  ${B}[${check.name}]${E} ${files.length} fichier(s)`);

    const span = new tracer.Span('verifyAdversarial', check.name, llm.MODEL).begin();
    try {
      const sample = files.slice(0, 3).map(f => {
        try { return fs.readFileSync(path.join(check.path, f), 'utf8').slice(0, 300); } catch { return ''; }
      }).join('\n---\n');

      const prompt = `Tu es un auditeur expert en tests de performance k6. Vérifie la qualité de ces fichiers ${check.name}.

Échantillon:
${sample}

Évalue: seuils réalistes, couverture des chemins critiques, cohérence avec une démo publique partagée (pas d'infra dédiée).`;

      const { proposal, critique, final } = await llm.chatAdversarial([{ role: 'user', content: prompt }]);
      span.end(true);

      const verdict = final.toLowerCase().includes('valide') || final.toLowerCase().includes('correct') ? 'VALID' : 'WARNING';
      const icon    = verdict === 'VALID' ? G+'✓ VALID'+E : Y+'⚠ WARNING'+E;
      console.log(`  ${icon} : ${final.slice(0,100)}`);
      verdicts.push({ check: check.name, verdict, detail: final });
    } catch (e) {
      span.error = e.message; span.end(false);
      console.error(`  ${R}✗ ${e.message}${E}`);
    }
  }

  console.log(`\n  ${B}Bilan :${E} ${verdicts.filter(v=>v.verdict==='VALID').length}/${verdicts.length} VALID`);
  return verdicts;
}

// ── full : triage + rca + verify ──────────────────────────────────────────────
async function cmdFull() {
  const triageResults = await cmdTriage();
  const rcaResults    = await cmdRca();
  const verifyResults = await cmdVerify();
  console.log(`\n${B}=== QUALITY FULL — TERMINÉ ===${E}`);
  return { triage: triageResults, rca: rcaResults, verify: verifyResults };
}

// ── Main ──────────────────────────────────────────────────────────────────────
async function main() {
  const [cmd] = process.argv.slice(2).filter(a => !a.startsWith('--'));
  await llm.assertRunning();

  switch (cmd) {
    case 'triage': await cmdTriage(); break;
    case 'rca':    await cmdRca();    break;
    case 'verify': await cmdVerify(); break;
    case 'full':   await cmdFull();   break;
    default:
      console.log(`
${B}Quality Agent${E} — Intelligence Qualité Performance

  triage    Classifie les seuils dépassés : backend_degradation / test_config_too_aggressive / network_flakiness / env_shared_demo
  rca       Root Cause Analysis avec Chain of Thought
  verify    Vérification adversariale des artefacts (scénarios k6, résultats)
  full      triage + rca + verify

Options:
  --dry-run                    Simulation sans écriture

Variables d'environnement:
  CONFIDENCE_THRESHOLD=0.70    Seuil déclenchant la vérification adversariale
`);
  }
}

main().catch(e => { console.error(R + e.message + E); process.exit(1); });
