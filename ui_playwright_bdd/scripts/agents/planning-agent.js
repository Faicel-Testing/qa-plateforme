'use strict';
// ============================================================
// Planning Agent — Gestion projet & couverture
// ============================================================
// Absorbe : user-stories-agent, test-case-agent, sprint-agent, coverage-agent
//
// Usage:
//   node scripts/agents/planning-agent.js stories              Liste les US Plane
//   node scripts/agents/planning-agent.js stories create       Crée les US dans Plane
//   node scripts/agents/planning-agent.js testcases            Liste les TCs existants
//   node scripts/agents/planning-agent.js cycles list          Liste les cycles Plane
//   node scripts/agents/planning-agent.js coverage analyze     Analyse la couverture .feature
//   node scripts/agents/planning-agent.js coverage gaps        Identifie les manques
//   node scripts/agents/planning-agent.js coverage suggest     Suggestions LLM
//
// Coût LLM : bas à moyen — seulement sur coverage suggest
// ============================================================
require('dotenv').config();

const fs   = require('fs');
const path = require('path');
const llm  = require('./llm');
const tracer = require('./shared/tracer');

const FRAMEWORK    = path.join(__dirname, '..', '..');
const verifier = require('./shared/agent-verifier').createVerifier({ agent: 'planning', root: FRAMEWORK, runtimeProcess: process });
const FEATURES_DIR = path.join(FRAMEWORK, 'src', 'features');
const DOCS_DIR     = path.join(FRAMEWORK, 'docs');

fs.mkdirSync(DOCS_DIR, { recursive: true });

const DRY_RUN = process.argv.includes('--dry-run');

const G = '\x1b[32m', R = '\x1b[31m', Y = '\x1b[33m', C = '\x1b[36m', B = '\x1b[1m', E = '\x1b[0m';

// Plane is the only remote planning provider.
async function connectedPlane() {
  const plane = require('./plane-fetcher').client();
  const project = await plane.request();
  console.log('Planning connecté à Plane : ' + project.name + ' (' + project.identifier + ')');
  return plane;
}
async function cmdStories(action) {
  if (action && !['list', 'create'].includes(action)) throw Error('Usage: stories [list|create]');
  const plane = await connectedPlane();
  const result = action === 'create'
    ? await require('./shared/plane-stories').importStories(plane, { dryRun: DRY_RUN })
    : await plane.fetchStories();
  console.log(JSON.stringify(result, null, 2));
}
async function cmdTestCases() {
  const plane = await connectedPlane();
  const items = await plane.list('work-items/');
  const cases = items.filter(i => i.external_source === require('./shared/plane-testcases').SOURCE);
  console.log(JSON.stringify(cases.sort((a,b) => a.sequence_id-b.sequence_id).map(i => ({ id:i.id, sequence:i.sequence_id, name:i.name, parent:i.parent, state:i.state, labels:i.labels })), null, 2));
}
async function cmdCycles(action) {
  if (action && action !== 'list') throw Error('Seule la consultation des cycles Plane est prise en charge : cycles list. Gérer leurs dates dans Plane.');
  const plane = await connectedPlane();
  console.log(JSON.stringify(await plane.list('cycles/'), null, 2));
}

// ── COVERAGE ──────────────────────────────────────────────────────────────────
const COVERAGE_TYPES = ['positif', 'negatif', 'auth', 'limite', 'securite', 'performance'];

async function cmdCoverage(action) {
  console.log(`\n${B}=== PLANNING — COVERAGE ===${E}`);
  if (!fs.existsSync(FEATURES_DIR)) {
    console.log(`  ${Y}⚠  Aucun .feature trouvé dans src/features/${E}`); return;
  }

  const features = fs.readdirSync(FEATURES_DIR).filter(f => f.endsWith('.feature'));
  const coverage = {};

  for (const f of features) {
    const content = fs.readFileSync(path.join(FEATURES_DIR, f), 'utf8');
    const scenarios = (content.match(/Scenario:/g) || []).length;
    const tags      = (content.match(/@\w+/g) || []).map(t => t.slice(1));
    const types     = COVERAGE_TYPES.filter(t => tags.includes(t));
    coverage[f] = { scenarios, types, tags };
  }

  console.log(`  ${C}${features.length} features analysées${E}\n`);

  if (action === 'analyze' || !action) {
    let total = 0;
    features.forEach(f => {
      const c = coverage[f];
      total += c.scenarios;
      const typeStr = c.types.length ? c.types.join(', ') : Y+'aucun type détecté'+E;
      console.log(`  ${G}✓${E} ${f.padEnd(35)} ${String(c.scenarios).padEnd(4)} scénarios  [${typeStr}]`);
    });
    console.log(`\n  Total : ${total} scénarios dans ${features.length} features`);

  } else if (action === 'gaps') {
    console.log(`  ${B}Couverture manquante par feature :${E}\n`);
    features.forEach(f => {
      const missing = COVERAGE_TYPES.filter(t => !coverage[f].types.includes(t));
      if (missing.length) console.log(`  ${Y}⚠${E}  ${f.padEnd(35)} manque: ${R}${missing.join(', ')}${E}`);
      else console.log(`  ${G}✓${E}  ${f.padEnd(35)} couverture complète`);
    });

  } else if (action === 'suggest') {
    const gaps = features.flatMap(f => {
      const missing = COVERAGE_TYPES.filter(t => !coverage[f].types.includes(t));
      return missing.map(t => ({ feature: f, missing: t }));
    });

    if (!gaps.length) { console.log(`  ${G}✓ Couverture complète — aucune suggestion nécessaire${E}`); return; }
    console.log(`  ${C}Génération suggestions LLM pour ${gaps.length} manques...${E}\n`);

    const span = new tracer.Span('coverageSuggest', JSON.stringify(gaps), llm.MODEL).begin();
    try {
      const prompt = `Tu es un expert QA BDD. Suggère des scénarios Gherkin manquants.

Manques identifiés:
${gaps.map(g => `- ${g.feature}: manque couverture ${g.missing}`).join('\n')}

Pour chaque manque, génère 1 Scenario Gherkin concis en français avec tags appropriés.
Format: @feature @type\nScenario: ...\n  Given...\n  When...\n  Then...`;

      const resp = await llm.chat([{ role: 'user', content: prompt }]);
      span.response = resp.message.content; span.end(true);
      verifier.check('suggest', resp.message.content, { gaps });
      console.log('[PROPOSITION NON VÉRIFIÉE]\n' + resp.message.content);
    } catch (e) {
      verifier.failure(e);
      span.error = e.message; span.end(false);
      console.error(`  ${R}✗ ${e.message}${E}`);
    }
  }
}

// ── Main ──────────────────────────────────────────────────────────────────────
async function main() {
  const args = process.argv.slice(2).filter(a => !a.startsWith('--'));
  const [cmd, sub] = args;
  if (cmd === 'coverage' && sub === 'suggest') await llm.assertRunning();

  switch (cmd) {
    case 'stories':   await cmdStories(sub);         break;
    case 'testcases': await cmdTestCases();           break;
    case 'check':     await connectedPlane();         break;
    case 'cycles':
    case 'sprint':    await cmdCycles(sub);           break;
    case 'coverage':  await cmdCoverage(sub);         break;
    default:
      console.log(`
${B}Planning Agent${E} — Gestion projet & couverture

  check                    Vérifie la connexion au projet Plane
  stories [create]         Liste ou importe les User Stories Plane
  testcases                Liste les cas de test enfants dans Plane
  cycles list              Liste les cycles Plane (sprint list : alias)
  coverage analyze         Analyse la couverture des .feature
  coverage gaps            Identifie les types de test manquants
  coverage suggest         Suggestions LLM pour combler les manques

Options:
  --dry-run    Simulation sans écriture

Variables:
  PLANE_WORKSPACE / PLANE_PROJECT_ID / PLANE_API_KEY
`);
  }
}

if (require.main === module) main().catch(e => { console.error(R + e.message + E); process.exitCode = 1; });
module.exports = { main, connectedPlane, cmdStories, cmdTestCases, cmdCycles };
