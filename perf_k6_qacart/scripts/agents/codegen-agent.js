'use strict';
// ============================================================
// Codegen Agent — Génération de scénarios k6
// ============================================================
// Usage:
//   node scripts/agents/codegen-agent.js scenario <key>  Génère un scénario k6 depuis une US Jira
//   node scripts/agents/codegen-agent.js batch           Génère un scénario par US Jira restante
//   node scripts/agents/codegen-agent.js preview <key>   Aperçu sans écriture
//
// Guards:
//   CODEGEN_BATCH=N   Limite le nombre d'éléments générés par run (0=tous)
// ============================================================
require('dotenv').config();
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';

const fs   = require('fs');
const path = require('path');
const llm  = require('./llm');
const jira = require('./jira-fetcher');
const tracer = require('./shared/tracer');

const FRAMEWORK     = path.join(__dirname, '..', '..');
const SCENARIOS_DIR  = path.join(FRAMEWORK, 'k6', 'scenarios');
const DOCS_DIR        = path.join(FRAMEWORK, 'docs');

fs.mkdirSync(SCENARIOS_DIR, { recursive: true });
fs.mkdirSync(DOCS_DIR, { recursive: true });

const BATCH_LIMIT = parseInt(process.env.CODEGEN_BATCH || '0');
const DRY_RUN     = process.argv.includes('--dry-run') || process.argv.includes('preview');

const G = '\x1b[32m', R = '\x1b[31m', Y = '\x1b[33m', C = '\x1b[36m', B = '\x1b[1m', E = '\x1b[0m';

const GUIDELINES = `Contraintes strictes :
- import { randomUser } from '../lib/testData.js';
- import les fonctions nécessaires depuis '../lib/api.js' (registerUser, loginUser, loginWrongPassword, getHomepage)
- 'export const options' avec stages OU vus/iterations, ET un bloc 'thresholds' réaliste
- QACart Todo est une démo publique partagée (dyno Heroku gratuit) : VUs modestes (≤20), jamais de rupture volontaire
- 'export default function () { ... }' — style k6 natif, pas d'async/await inutile
- Commentaire en tête expliquant l'objectif du scénario

Réponds UNIQUEMENT avec le JavaScript complet (pas de markdown).`;

// ── scenario : génère un scénario k6 depuis 1 US ──────────────────────────────
async function cmdScenario(usKey) {
  console.log(`\n${B}=== CODEGEN — SCENARIO [${llm.MODEL}] ===${E}`);
  if (!usKey) { console.log(`  Usage: codegen scenario SCRUM-5`); return; }

  let story;
  try {
    await jira.assertJira();
    story = await jira.fetchIssue(usKey);
  } catch (e) {
    console.error(`  ${R}✗ Jira: ${e.message}${E}`); return;
  }
  console.log(`  ${C}${story.key} — ${story.summary}${E}\n`);

  const prompt = `Tu es un expert k6 (tests de performance JavaScript). Génère un scénario k6 complet pour cette User Story.

${story.key} — ${story.summary}
${story.description ? `Description: ${story.description}` : ''}

${GUIDELINES}`;

  const span = new tracer.Span('chatScenario', prompt, llm.MODEL).begin();
  try {
    const resp = await llm.chat([{ role: 'user', content: prompt }]);
    const code = (resp.message.content || '').replace(/```javascript\n?|```js\n?|```\n?/g, '').trim();
    span.response = code; span.end(true);

    console.log(code);
    const filepath = path.join(SCENARIOS_DIR, `${story.key.toLowerCase()}.js`);
    if (!DRY_RUN) {
      fs.writeFileSync(filepath, code, 'utf8');
      console.log(`\n  ${G}✓ ${filepath}${E}`);
    } else {
      console.log(`\n  ${Y}[DRY-RUN] ${path.basename(filepath)} non écrit${E}`);
    }
  } catch (e) {
    span.error = e.message; span.end(false);
    console.error(`  ${R}✗ ${e.message}${E}`);
  }
}

// ── batch : génère un scénario par US restante ────────────────────────────────
async function cmdBatch() {
  console.log(`\n${B}=== CODEGEN — BATCH [${llm.MODEL}] ===${E}`);
  let stories;
  try {
    await jira.assertJira();
    stories = await jira.fetchStories();
  } catch (e) {
    console.error(`  ${R}✗ Jira indisponible: ${e.message}${E}`);
    return;
  }
  if (!stories.length) { console.log(`  ${Y}⚠  Aucune story Jira${E}`); return; }

  const existing = fs.existsSync(SCENARIOS_DIR) ? fs.readdirSync(SCENARIOS_DIR).map(f => f.replace('.js','')) : [];
  const pending  = stories.filter(s => !existing.includes(s.key.toLowerCase()));
  const items    = BATCH_LIMIT ? pending.slice(0, BATCH_LIMIT) : pending;

  console.log(`  ${C}${items.length} stories sans scénario → génération${E}\n`);

  let ok = 0, ko = 0;
  for (const story of items) {
    console.log(`  ${B}[${story.key}]${E} ${story.summary.slice(0, 55)}`);
    try {
      await cmdScenario(story.key);
      ok++;
    } catch (e) {
      console.error(`  ${R}✗ ${story.key}: ${e.message}${E}`);
      ko++;
    }
  }
  console.log(`\n  ${G}✓ ${ok} générés${E}${ko ? `  ${R}✗ ${ko} erreurs${E}` : ''}`);
}

// ── Main ──────────────────────────────────────────────────────────────────────
async function main() {
  const args = process.argv.slice(2).filter(a => !a.startsWith('--'));
  const [cmd, arg] = args;

  await llm.assertRunning();

  switch (cmd) {
    case 'scenario': await cmdScenario(arg);  break;
    case 'batch':    await cmdBatch();        break;
    case 'preview':  await cmdScenario(arg);  break;
    default:
      console.log(`
${B}Codegen Agent${E} — Génération de scénarios k6

  scenario <key>  Génère un scénario k6 depuis une US Jira (ex: SCRUM-5)
  batch           Génère un scénario pour chaque US sans scénario existant
  preview <key>   Aperçu sans écriture

Options:
  --dry-run            Simulation sans écriture sur disque

Variables d'environnement:
  CODEGEN_BATCH=N      Limite le nombre d'items générés (0 = tous)
`);
  }
}

main().catch(e => { console.error(R + e.message + E); process.exit(1); });
