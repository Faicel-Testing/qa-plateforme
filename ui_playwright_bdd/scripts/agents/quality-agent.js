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

const fs     = require('fs');
const path   = require('path');
const llm    = require('./llm');
const tracer = require('./shared/tracer');
const memory      = require('./shared/memory-store');
const promptStore = require('./shared/prompt-store');
const { buildAllureSummary, allureVerdict } = require('./shared/allure-verification');
const { verifySources } = require('./shared/source-verification');

function fmt(template, vars) {
  let result = template;
  for (const [k, v] of Object.entries(vars)) {
    result = result.split('{' + k + '}').join(String(v ?? '?'));
  }
  return result;
}

const FRAMEWORK   = path.join(__dirname, '..', '..');
const verifier = require('./shared/agent-verifier').createVerifier({ agent: 'quality', root: FRAMEWORK, runtimeProcess: process });
const RESULTS_DIR = require('./shared/pipeline-runtime').resultDirectory(FRAMEWORK);
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
      message: r.statusDetails?.message || '',
      trace:   r.statusDetails?.trace || '',
      labels:  (r.labels || []).map(l => l.value),
    }));
}

// ── TRIAGE ────────────────────────────────────────────────────────────────────
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
      const result = await llm.chatConfident(require('./shared/skill-store').messages('triage-rca', prompt), CONFIDENCE_THRESHOLD);
      const verification = verifier.check('triage', result, { failure: f });
      span.confidence = result.confidence; span.end(true);
      promptStore.recordUsage('triage_classify', result.confidence);

      const icon = { real_bug: R+'🐛'+E, flaky: Y+'⚡'+E, env_issue: C+'🔧'+E, false_positive: '\x1b[2m'+'❓'+E }[result.result] || '?';
      const confIcon = result.confidence >= CONFIDENCE_THRESHOLD ? G : Y;
      console.log(`  ${icon} ${f.name.slice(0,50).padEnd(50)} ${confIcon}${Math.round(result.confidence*100)}%${E}  ${result.result}`);

      // Adversarial si confidence faible (Guard)
      if (!result.above_threshold) {
        console.log(`     ${Y}→ confidence faible, vérification adversariale...${E}`);
        const adv = await llm.chatAdversarial(require('./shared/skill-store').messages('triage-rca', prompt));
        verifier.check('adversarial', adv.final, { failure: f });
        results.push({ ...f, category: result.result, confidence: result.confidence, verification, adversarial: adv.final });
      } else {
        results.push({ ...f, category: result.result, confidence: result.confidence, verification });
      }

      memory.recordEpisode('quality-agent', [{ tc: f.name, category: result.result, confidence: result.confidence, verification }], `Triage: ${result.result}`, 'triage');
    } catch (e) {
      span.error = e.message; span.end(false);
      console.error(`  ${R}✗ ${f.name}: ${e.message}${E}`);
      results.push({ ...f, category: 'unknown', confidence: 0 });
      process.exitCode = 1;
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

    const _rcaTpl = promptStore.get('rca_analyze') ||
      'Tu es un expert QA Playwright. Analyse la cause racine de ces échecs.\n\n' +
      'Groupe d\'échecs ({count} tests):\n{fail_list}\n\n' +
      'Raisonne étape par étape (ÉTAPE 1, ÉTAPE 2, CONCLUSION) avant de conclure.';
    const prompt = fmt(_rcaTpl, require('./shared/analysis-evidence').rcaVariables(key, group, { compact: true })) +
      '\nDistingue les observations des hypothèses. Un timeout ne prouve pas un sélecteur incorrect. Ne propose pas de modifier une assertion pour masquer une divergence applicative. Sans inspection du code et des exigences, une cause racine reste une hypothèse.';

    try {
      const { reasoning, structured } = await llm.chatCot(
        require('./shared/skill-store').messages('triage-rca', prompt),
        `Maintenant extrais la cause racine en JSON selon ce schéma:\n${JSON.stringify(RCA_SCHEMA, null, 2)}\n\nRéponds UNIQUEMENT avec le JSON.`,
        { rag: false }
      );

      if (/service\s+LLM[^\n]*(indisponible|hors ligne)/i.test(reasoning || '')) throw new Error('RCA reasoning unavailable');
      let rca = {};
      const m = (structured || '').match(/\{[\s\S]*\}/);
      if (m) { try { rca = JSON.parse(m[0]); } catch {} }
      const verification = verifier.check('rca', rca, { failures: group });

      span.end(true);
      promptStore.recordUsage('rca_analyze');
      console.log(`  ${G}→ ${rca.cause_category || '?'}${E} | ${rca.fix_priority || '?'} | ${rca.fix_action?.slice(0,50)||''}`);
      console.log(`\x1b[2m  Raisonnement: ${reasoning.slice(0,100)}...\x1b[0m\n`);

      analyses.push({ group: key, tests: group.map(f=>f.name), rca, reasoning, verification });
    } catch (e) {
      span.error = e.message; span.end(false);
      console.error(`  ${R}✗ ${e.message}${E}`);
      process.exitCode = 1;
      analyses.push({ group: key, tests: group.map(f => f.name), status: 'NOT_EVALUATED', error: e.message });
    }
  }

  if (!process.argv.includes('--dry-run')) {
    fs.writeFileSync(path.join(DOCS_DIR, 'rca-report.json'), JSON.stringify({ ts: new Date().toISOString(), analyses }, null, 2), 'utf8');
    console.log(`  ${G}✓ docs/rca-report.json${E}`);
  }
  return analyses;
}

// ── VERIFY — Sources complètes, contrôles locaux et audit Allure ──────────────
async function cmdVerify() {
  const localOnly = process.argv.includes('--local-only');
  console.log(`\n${B}=== QUALITY — VERIFY (sources complètes) [${localOnly ? 'local-only' : llm.MODEL}] ===${E}`);

  const verdicts = await verifySources(FRAMEWORK, llm, {
    localOnly,
    maxChars: Number(process.env.VERIFY_MAX_PROMPT_CHARS || 24000),
    cacheDir: process.argv.includes('--dry-run') ? undefined : path.join(FRAMEWORK, 'logs', 'verify-cache'),
    onProgress: message => console.log(`  ${C}${message}${E}`),
  });
  const localChecks = verdicts[0]?.evidence.localChecks;
  if (localChecks) {
    console.log(`  TypeScript : ${localChecks.typescript.status} ; Cucumber dry-run : ${localChecks.cucumber.status}`);
    if (localChecks.cucumber.scenarios != null) {
      console.log(`  ${localChecks.cucumber.scenarios} scénarios / ${localChecks.cucumber.steps} steps vérifiés sans exécution UI.`);
    }
  }
  for (const result of verdicts) {
    console.log(`\n  ${B}[${result.check}]${E} ${result.targetFiles} fichier(s)`);
    console.log(`  ${result.verdict === 'VALID' ? G : result.verdict === 'INVALID' ? R : Y}${result.verdict} [${result.analysisStatus}] : ${result.reasoning}${E}`);
  }

  let allure;
  try {
    const files = fs.readdirSync(RESULTS_DIR).filter(file => file.endsWith('-result.json')).sort();
    allure = allureVerdict(buildAllureSummary(files, file => fs.readFileSync(path.join(RESULTS_DIR, file), 'utf8')));
  } catch {
    const reasoning = 'Dossier de résultats absent ou illisible ; vérification Allure impossible.';
    allure = { check: 'Allure Results', verdict: 'NOT_EVALUATED', analysisStatus: 'INCOMPLETE', method: 'deterministic', reasoning, detail: reasoning };
  }
  verdicts.push(allure);
  console.log(`\n  ${B}[Allure Results]${E} ${allure.evidence?.totalFiles ?? '?'} fichier(s)`);
  console.log(`  ${allure.verdict === 'VALID' ? G : allure.verdict === 'INVALID' ? R : Y}${allure.verdict} [LOCAL] : ${allure.reasoning}${E}`);

  const counts = Object.fromEntries(['VALID', 'WARNING', 'INVALID', 'NOT_EVALUATED'].map(status => [status, verdicts.filter(v => v.verdict === status).length]));
  if (counts.INVALID || (!localOnly && counts.NOT_EVALUATED)) process.exitCode = 1;
  console.log(`\n  ${B}Bilan :${E} ${counts.VALID}/${verdicts.length} VALID | ${counts.WARNING} WARNING | ${counts.INVALID} INVALID | ${counts.NOT_EVALUATED} NON ÉVALUÉ(S)`);
  if (!process.argv.includes('--dry-run')) {
    fs.writeFileSync(path.join(DOCS_DIR, 'verify-report.json'), JSON.stringify({ schemaVersion: 3, ts: new Date().toISOString(), mode: localOnly ? 'local-only' : 'full', counts, verdicts }, null, 2), 'utf8');
    console.log(`  ${G}✓ docs/verify-report.json${E}`);
  }
  return verdicts;
}

// ── full : triage + rca + verify ──────────────────────────────────────────────
async function cmdFull() {
  const checkpoint = { ts: new Date().toISOString(), resultsDir: RESULTS_DIR, status: 'RUNNING' };
  const save = () => {
    if (process.argv.includes('--dry-run')) return;
    const json = JSON.stringify(checkpoint, null, 2);
    fs.writeFileSync(path.join(DOCS_DIR, 'quality-full-report.json'), json);
    fs.writeFileSync(path.join(RESULTS_DIR, 'quality-analysis.json'), json);
  };
  save();
  const triageResults = await cmdTriage();
  checkpoint.triage = triageResults; checkpoint.phase = 'rca'; save();
  const rcaResults    = await cmdRca();
  checkpoint.rca = rcaResults; checkpoint.phase = 'verify'; save();
  const verifyResults = await cmdVerify();
  checkpoint.verify = verifyResults;
  checkpoint.aiVerification = [...triageResults, ...rcaResults].some(r => r.verification?.status === 'UNVERIFIED') ? 'UNVERIFIED' : 'NOT_APPLICABLE';
  const incompleteTriage = triageResults.some(r => !['real_bug', 'flaky', 'env_issue', 'false_positive'].includes(r.category));
  checkpoint.status = incompleteTriage || verifyResults.some(v => ['INVALID', 'NOT_EVALUATED'].includes(v.verdict)) || process.exitCode ? 'INCOMPLETE_OR_FAILED' : 'COMPLETE';
  if (checkpoint.status !== 'COMPLETE') process.exitCode = 1;
  save();
  console.log(`\n${B}=== QUALITY FULL — TERMINÉ ===${E}`);
  return { triage: triageResults, rca: rcaResults, verify: verifyResults };
}

// ── Main ──────────────────────────────────────────────────────────────────────
async function main() {
  const [cmd] = process.argv.slice(2).filter(a => !a.startsWith('--'));
  // VERIFY must save local evidence even when the provider is unavailable.
  if (cmd !== 'verify') await llm.assertRunning();

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
  verify    Sources complètes et contrôles locaux, puis audit des résultats Allure
  full      triage + rca + verify

Options:
  --dry-run                    Simulation sans écriture
  --local-only                 verify : contrôles locaux sans appel LLM

Variables d'environnement:
  CONFIDENCE_THRESHOLD=0.70    Seuil déclenchant la vérification adversariale
  VERIFY_MAX_PROMPT_CHARS=24000 Taille maximale d'un lot de sources complètes
`);
  }
}

main().catch(e => { console.error(R + e.message + E); process.exit(1); });
