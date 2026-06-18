'use strict';
// ============================================================
// Quality Agent — Intelligence Qualité
// ============================================================
// Absorbe : triage-agent, rca-agent, verifier-agent
//
// Usage:
//   node scripts/agents/quality-agent.js triage          Classifie les échecs Allure
//   node scripts/agents/quality-agent.js rca             Root Cause Analysis (CoT)
//   node scripts/agents/quality-agent.js verify          Vérification adversariale
//   node scripts/agents/quality-agent.js full            triage + rca + verify
//
// Guards:
//   CONFIDENCE_THRESHOLD=0.70   Seuil en dessous duquel l'adversarial se déclenche
//   AGENT_MAX_ITER=5            Non utilisé ici (pas de boucle)
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
const RESULTS_DIR = path.join(FRAMEWORK, 'allure-results');
const DOCS_DIR    = path.join(FRAMEWORK, 'docs');

fs.mkdirSync(DOCS_DIR, { recursive: true });

// Guard : adversarial uniquement si confidence < seuil → économie 50% tokens
const CONFIDENCE_THRESHOLD = parseFloat(process.env.CONFIDENCE_THRESHOLD || '0.70');

const G = '\x1b[32m', R = '\x1b[31m', Y = '\x1b[33m', C = '\x1b[36m', B = '\x1b[1m', E = '\x1b[0m';

// ── Lecture allure-results ─────────────────────────────────────────────────────
function loadFailures() {
  if (!fs.existsSync(RESULTS_DIR)) return [];
  return fs.readdirSync(RESULTS_DIR)
    .filter(f => f.endsWith('-result.json'))
    .map(f => { try { return JSON.parse(fs.readFileSync(path.join(RESULTS_DIR, f), 'utf8')); } catch { return null; } })
    .filter(r => r && ['failed','broken'].includes(r.status))
    .map(r => ({
      name:    r.name || r.fullName || 'unknown',
      status:  r.status,
      message: (r.statusDetails?.message || '').slice(0, 300),
      trace:   (r.statusDetails?.trace   || '').slice(0, 200),
      labels:  (r.labels || []).map(l => l.value),
    }));
}

// ── TRIAGE ────────────────────────────────────────────────────────────────────
const TRIAGE_SCHEMA = {
  category:   'real_bug | flaky | env_issue | false_positive',
  confidence: 'float 0.0-1.0',
  reasoning:  'string — justification courte (1-2 phrases)',
};

async function cmdTriage() {
  console.log(`\n${B}=== QUALITY — TRIAGE [${llm.MODEL}] ===${E}`);
  const failures = loadFailures();
  if (!failures.length) { console.log(`  ${G}✓ Aucun échec dans allure-results${E}`); return []; }
  console.log(`  ${C}${failures.length} échec(s) à analyser${E}\n`);

  const results = [];
  for (const f of failures) {
    const context = memory.getContextFor(f.name);
    const span    = new tracer.Span('triageChatConfident', f.name, llm.MODEL).begin();

    const _tpl = promptStore.get('triage_classify') ||
      'Tu es un expert QA. Classifie cet échec de test Playwright.\n\n' +
      'Test : {test_name}\nStatut : {status}\nMessage : {error_message}\n' +
      'Trace : {stack_trace}\nHistorique : {context}\n\n' +
      'Catégories possibles:\n' +
      '- real_bug      : Le code de l\'application est buggé\n' +
      '- flaky         : Test instable (timing, réseau, état)\n' +
      '- env_issue     : Problème d\'environnement (config, données)\n' +
      '- false_positive: Le test est mal écrit';
    const prompt = fmt(_tpl, {
      test_name: f.name, status: f.status, error_message: f.message,
      stack_trace: f.trace, context,
      feature_file: 'N/A', scenario_name: 'N/A', failed_step: 'N/A',
      screenshot_path: 'N/A', browser: 'chromium', current_url: 'N/A',
    });

    try {
      const result = await llm.chatConfident([{ role: 'user', content: prompt }], CONFIDENCE_THRESHOLD);
      span.confidence = result.confidence; span.end(true);
      promptStore.recordUsage('triage_classify', result.confidence);

      const icon = { real_bug: R+'🐛'+E, flaky: Y+'⚡'+E, env_issue: C+'🔧'+E, false_positive: '\x1b[2m'+'❓'+E }[result.result] || '?';
      const confIcon = result.confidence >= CONFIDENCE_THRESHOLD ? G : Y;
      console.log(`  ${icon} ${f.name.slice(0,50).padEnd(50)} ${confIcon}${Math.round(result.confidence*100)}%${E}  ${result.result}`);

      // Adversarial si confidence faible (Guard)
      if (!result.above_threshold) {
        console.log(`     ${Y}→ confidence faible, vérification adversariale...${E}`);
        const adv = await llm.chatAdversarial([{ role: 'user', content: prompt }]);
        results.push({ ...f, category: result.result, confidence: result.confidence, adversarial: adv.final });
      } else {
        results.push({ ...f, category: result.result, confidence: result.confidence });
      }

      memory.recordEpisode('quality-agent', [{ tc: f.name, category: result.result, confidence: result.confidence }], `Triage: ${result.result}`, 'triage');
    } catch (e) {
      span.error = e.message; span.end(false);
      console.error(`  ${R}✗ ${f.name}: ${e.message}${E}`);
      results.push({ ...f, category: 'unknown', confidence: 0 });
    }
  }

  // Résumé
  const byCategory = results.reduce((acc, r) => { acc[r.category] = (acc[r.category]||0)+1; return acc; }, {});
  console.log(`\n  ${B}Résumé :${E} ${Object.entries(byCategory).map(([k,v])=>`${k}×${v}`).join('  ')}`);
  return results;
}

// ── RCA — Root Cause Analysis (Chain of Thought) ──────────────────────────────
const RCA_SCHEMA = {
  root_cause:     'string — cause racine en 1 phrase',
  cause_category: 'assertion | auth | data | network | config | selector | logic | unknown',
  affected_layer: 'ui | api | database | network | config | test',
  fix_action:     'string — action corrective concrète',
  fix_priority:   'immediate | high | medium | low',
  related_tests:  'array of string — noms des tests similaires potentiellement affectés',
};

async function cmdRca() {
  console.log(`\n${B}=== QUALITY — RCA [${llm.MODEL}] ===${E}`);
  const failures = loadFailures();
  if (!failures.length) { console.log(`  ${G}✓ Aucun échec${E}`); return []; }

  // Grouper par message d'erreur similaire
  const groups = {};
  for (const f of failures) {
    const key = f.message.slice(0, 80) || f.status;
    if (!groups[key]) groups[key] = [];
    groups[key].push(f);
  }

  console.log(`  ${C}${failures.length} échec(s) regroupés en ${Object.keys(groups).length} groupes${E}\n`);
  const analyses = [];

  for (const [key, group] of Object.entries(groups)) {
    console.log(`  ${B}Groupe (${group.length} tests) :${E} ${key.slice(0,60)}`);
    const span = new tracer.Span('rcaChatCot', key, llm.MODEL).begin();

    const failList = group.map(f => `- ${f.name}: ${f.message}`).join('\n');
    const _rcaTpl = promptStore.get('rca_analyze') ||
      'Tu es un expert QA Playwright. Analyse la cause racine de ces échecs.\n\n' +
      'Groupe d\'échecs ({count} tests):\n{fail_list}\n\n' +
      'Raisonne étape par étape (ÉTAPE 1, ÉTAPE 2, CONCLUSION) avant de conclure.';
    const prompt = fmt(_rcaTpl, {
      count: group.length, fail_list: failList,
      test_name: key, tc: key, tc_id: key, us: 'N/A', us_id: 'N/A',
      error_message: key, stack_trace: failList, suite: 'playwright',
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

      analyses.push({ group: key, tests: group.map(f=>f.name), rca, reasoning });
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
    { name: 'Features Gherkin', path: path.join(FRAMEWORK, 'src', 'features'), ext: '.feature' },
    { name: 'Step Definitions', path: path.join(FRAMEWORK, 'src', 'steps'),    ext: '.ts' },
    { name: 'Allure Results',   path: RESULTS_DIR,                              ext: '-result.json' },
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

      const prompt = `Tu es un auditeur QA expert. Vérifie la qualité de ces fichiers ${check.name}.

Échantillon:
${sample}

Évalue: complétude, correctitude, cohérence, bonnes pratiques.`;

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
${B}Quality Agent${E} — Intelligence Qualité

  triage    Classifie les échecs : real_bug / flaky / env_issue / false_positive
  rca       Root Cause Analysis avec Chain of Thought
  verify    Vérification adversariale des artefacts (features, steps, résultats)
  full      triage + rca + verify

Options:
  --dry-run                    Simulation sans écriture

Variables d'environnement:
  CONFIDENCE_THRESHOLD=0.70    Seuil déclenchant la vérification adversariale
`);
  }
}

main().catch(e => { console.error(R + e.message + E); process.exit(1); });
