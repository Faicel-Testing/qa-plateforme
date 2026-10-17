'use strict';
// ============================================================
// Codegen Agent — Génération de code BDD
// ============================================================
// Absorbe : generate-agent, spec-agent, tc-generator
//
// Usage:
//   node scripts/agents/codegen-agent.js spec           Génère .feature depuis US Plane
//   node scripts/agents/codegen-agent.js steps          Génère step definitions TypeScript
//   node scripts/agents/codegen-agent.js pages          Génère page objects TypeScript
//   node scripts/agents/codegen-agent.js gherkin <key>  Génère gherkin pour 1 US
//   node scripts/agents/codegen-agent.js preview        Aperçu sans écriture
//
// Guards:
//   CODEGEN_BATCH=N   Limite le nombre d'éléments générés par run (0=tous)
// ============================================================
require('dotenv').config();

const fs   = require('fs');
const path = require('path');
const llm         = require('./llm');
const plane       = require('./plane-fetcher');
const tracer      = require('./shared/tracer');
const promptStore = require('./shared/prompt-store');
const { generationBlocker } = require('./shared/story-readiness');

function fmt(template, vars) {
  let result = template;
  for (const [k, v] of Object.entries(vars)) {
    result = result.split('{' + k + '}').join(String(v ?? '?'));
  }
  return result;
}

const FRAMEWORK    = path.join(__dirname, '..', '..');
const verifier = require('./shared/agent-verifier').createVerifier({ agent: 'codegen', root: FRAMEWORK, runtimeProcess: process });
const FEATURES_DIR = path.join(FRAMEWORK, 'src', 'features');
const STEPS_DIR    = path.join(FRAMEWORK, 'src', 'steps');
const PAGES_DIR    = path.join(FRAMEWORK, 'src', 'pages');
const DOCS_DIR     = path.join(FRAMEWORK, 'docs');

[FEATURES_DIR, STEPS_DIR, PAGES_DIR, DOCS_DIR].forEach(d => fs.mkdirSync(d, { recursive: true }));

const BATCH_LIMIT = parseInt(process.env.CODEGEN_BATCH || '0');
const DRY_RUN     = process.argv.includes('--dry-run') || process.argv.includes('preview');

const R = '\x1b[31m', Y = '\x1b[33m', C = '\x1b[36m', B = '\x1b[1m', E = '\x1b[0m';

// ── spec : génère .feature depuis Plane ────────────────────────────────────────
async function cmdSpec() {
  console.log(`\n${B}=== CODEGEN — SPEC [${llm.MODEL}] ===${E}`);
  let stories;
  try {
    await plane.assertConnection();
    stories = await plane.fetchStories();
  } catch (e) {
    console.error(`  ${R}✗ Source des stories indisponible: ${e.message}${E}`);
    process.exitCode = 1;
    return;
  }
  if (!stories.length) { console.log(`  ${Y}⚠  Aucune story dans la source configurée${E}`); process.exitCode = 1; return; }

  const items = BATCH_LIMIT ? stories.slice(0, BATCH_LIMIT) : stories;
  console.log(`  ${C}${items.length} stories → .feature${E}\n`);

  let ok = 0, ko = 0, pending = 0;
  for (const story of items) {
    console.log(`  ${B}[${story.key}]${E} ${story.summary.slice(0, 55)}`);
    const blocker = generationBlocker(story);
    if (blocker) {
      console.log(`  A CLARIFIER ${story.key}: ${blocker}; aucun appel IA ni proposition.`);
      pending++;
      process.exitCode = 1;
      continue;
    }
    const span = new tracer.Span('chatSpec', story.summary, llm.MODEL).begin();
    try {
      const _tpl = promptStore.get('tc_generate_ui') ||
        'Tu es un expert QA BDD. Génère un fichier .feature Gherkin complet pour cette User Story.\n\n' +
        'Clé Plane  : {us_key}\nTitre      : {us_title}\nDescription: {us_description}\nStatut     : {us_status}\n\n' +
        'Exigences:\n- Feature avec description claire\n- Background si nécessaire\n' +
        '- Scénarios justifiés par les exigences, sans quota artificiel\n- Tags avant Feature: @{us_key_lower} @regression\n' +
        '- Steps en français, style BDD (Given/When/Then)\n\nRéponds UNIQUEMENT avec le contenu .feature (pas de bloc markdown).';
      const prompt = fmt(_tpl, {
        us_key: story.key, us_title: story.summary,
        us_description: story.description || 'Non fournie', us_status: story.status,
        us_key_lower: story.key.toLowerCase(),
      }) + '\n\n' + require('./shared/gherkin-contract').contract(story.key);

      const resp    = await llm.chat(require('./shared/skill-store').messages('generation-gherkin', prompt));
      const content = (resp.message.content || '').replace(/```[a-z]*\n?/g, '').trim();
      verifier.check('gherkin', content, { prompt });
      span.response = content; span.end(true);
      promptStore.recordUsage('tc_generate_ui');

      const filepath = path.join(FEATURES_DIR, `${story.key.toLowerCase()}.feature`);
      if (DRY_RUN) {
        console.log(`  ${Y}[DRY-RUN]${E} ${path.basename(filepath)}`);
        console.log(`\x1b[2m${content.slice(0, 150)}...\x1b[0m\n`);
      } else {
        require('./shared/change-proposals').propose(FRAMEWORK, filepath, content, 'codegen');
        console.log(`  ${Y}Proposition à relire pour ${filepath}${E}`);
      }
      ok++;
    } catch (e) {
      span.error = e.message; span.end(false);
      console.error(`  ${R}✗ ${story.key}: ${e.message}${E}`);
      ko++;
      process.exitCode = 1;
    }
  }
  console.log(`\n  ${ok} propositions ${DRY_RUN ? 'verifiees en apercu' : 'enregistrees, non appliquees'}; ${ko} erreurs techniques; ${pending} stories a clarifier.`);
}

// ── steps : génère step definitions TypeScript ────────────────────────────────
async function cmdSteps() {
  console.log(`\n${B}=== CODEGEN — STEPS [${llm.MODEL}] ===${E}`);
  if (!fs.existsSync(FEATURES_DIR)) {
    console.log(`  ${Y}⚠  Aucun .feature — lance d'abord: codegen spec${E}`); process.exitCode = 1; return;
  }
  const features = fs.readdirSync(FEATURES_DIR).filter(f => f.endsWith('.feature'));
  if (!features.length) { console.log(`  ${Y}⚠  Dossier src/features/ vide${E}`); process.exitCode = 1; return; }

  const items = BATCH_LIMIT ? features.slice(0, BATCH_LIMIT) : features;
  console.log(`  ${C}${items.length} features → step definitions${E}\n`);

  for (const featureFile of items) {
    const content = fs.readFileSync(path.join(FEATURES_DIR, featureFile), 'utf8');
    const base    = featureFile.replace('.feature', '');
    console.log(`  ${B}[${featureFile}]${E}`);

    const span = new tracer.Span('chatSteps', content, llm.MODEL).begin();
    try {
      const prompt = require('./shared/skill-store').instructions('generation-steps') + `\nFeature fournie :\n${content}`;

      const resp = await llm.chat([{ role: 'user', content: prompt }]);
      let code   = (resp.message.content || '').replace(/```typescript\n?|```ts\n?|```\n?/g, '').trim();
      verifier.check('typescript', code, { prompt, filePath: path.join(STEPS_DIR, `${base}.steps.ts`) });
      span.response = code; span.end(true);

      const filepath = path.join(STEPS_DIR, `${base}.steps.ts`);
      if (DRY_RUN) {
        console.log(`  ${Y}[DRY-RUN]${E} ${path.basename(filepath)}\n`);
      } else {
        require('./shared/change-proposals').propose(FRAMEWORK, filepath, code, 'codegen');
        console.log(`  ${Y}Proposition à relire pour ${filepath}${E}`);
      }
    } catch (e) {
      span.error = e.message; span.end(false);
      console.error(`  ${R}✗ ${featureFile}: ${e.message}${E}`);
      process.exitCode = 1;
    }
  }
}

// ── pages : génère page object models ─────────────────────────────────────────
async function cmdPages() {
  console.log(`\n${B}=== CODEGEN — PAGES [${llm.MODEL}] ===${E}`);
  if (!fs.existsSync(FEATURES_DIR)) {
    console.log(`  ${Y}⚠  Aucun .feature — lance d'abord: codegen spec${E}`); process.exitCode = 1; return;
  }
  const features = fs.readdirSync(FEATURES_DIR).filter(f => f.endsWith('.feature'));
  const items    = BATCH_LIMIT ? features.slice(0, BATCH_LIMIT) : features;
  if (!items.length) { process.exitCode = 1; console.error('No features to generate pages from'); return; }
  console.log(`  ${C}${items.length} features → page objects${E}\n`);

  for (const featureFile of items) {
    const content = fs.readFileSync(path.join(FEATURES_DIR, featureFile), 'utf8');
    const base    = featureFile.replace('.feature', '');
    const className = base.charAt(0).toUpperCase() + base.slice(1) + 'Page';
    console.log(`  ${B}[${featureFile}]${E} → ${className}.ts`);

    const span = new tracer.Span('chatPages', content, llm.MODEL).begin();
    try {
      const prompt = require('./shared/skill-store').instructions('generation-pages') + `\nFeature fournie :\n${content}\nClasse demandée : ${className}`;

      const resp = await llm.chat([{ role: 'user', content: prompt }]);
      let code   = (resp.message.content || '').replace(/```typescript\n?|```ts\n?|```\n?/g, '').trim();
      verifier.check('typescript', code, { prompt, filePath: path.join(PAGES_DIR, `${className}.ts`) });
      span.response = code; span.end(true);

      const filepath = path.join(PAGES_DIR, `${className}.ts`);
      if (DRY_RUN) {
        console.log(`  ${Y}[DRY-RUN]${E} ${path.basename(filepath)}\n`);
      } else {
        require('./shared/change-proposals').propose(FRAMEWORK, filepath, code, 'codegen');
        console.log(`  ${Y}Proposition à relire pour ${filepath}${E}`);
      }
    } catch (e) {
      span.error = e.message; span.end(false);
      console.error(`  ${R}✗ ${featureFile}: ${e.message}${E}`);
      process.exitCode = 1;
    }
  }
}

// ── gherkin : génère gherkin pour 1 US ────────────────────────────────────────
async function cmdGherkin(usKey) {
  console.log(`\n${B}=== CODEGEN — GHERKIN [${llm.MODEL}] ===${E}`);
  if (!usKey) { console.log(`  Usage: codegen gherkin SCRUM-5`); process.exitCode = 1; return; }

  let story;
  try {
    await plane.assertConnection();
    story = await plane.fetchIssue(usKey);
  } catch (e) {
    console.error(`  ${R}✗ Source des stories: ${e.message}${E}`); process.exitCode = 1; return;
  }
  console.log(`  ${C}${story.key} — ${story.summary}${E}\n`);
  const blocker = generationBlocker(story);
  if (blocker) {
    console.log(`A CLARIFIER ${story.key}: ${blocker}; aucun appel IA ni proposition.`);
    process.exitCode = 1;
    return;
  }

  const _tpl = promptStore.get('tc_generate_ui') ||
    'Génère un fichier .feature Gherkin BDD complet et professionnel.\n\n' +
    '{us_key} — {us_title}\nDescription: {us_description}\n\n' +
    'Exigences:\n- Feature descriptif\n- Background avec préconditions\n' +
    '- Scénarios justifiés par les exigences, sans quota artificiel\n- Tags avant Feature: @{us_key_lower} @regression\n' +
    '- Steps en français\n\nRéponds uniquement avec le contenu .feature.';
  const prompt = fmt(_tpl, {
    us_key: story.key, us_title: story.summary,
    us_description: story.description || 'Non fournie', us_status: story.status,
    us_key_lower: story.key.toLowerCase(),
  }) + '\n\n' + require('./shared/gherkin-contract').contract(story.key);

  const span = new tracer.Span('chatGherkin', prompt, llm.MODEL).begin();
  try {
    const resp    = await llm.chat(require('./shared/skill-store').messages('generation-gherkin', prompt));
    const content = (resp.message.content || '').replace(/```[a-z]*\n?/g, '').trim();
    verifier.check('gherkin', content, { prompt });
    span.response = content; span.end(true);
    promptStore.recordUsage('tc_generate_ui');

    console.log(content);
    if (!DRY_RUN) {
      const filepath = path.join(FEATURES_DIR, `${usKey.toLowerCase()}.feature`);
      require('./shared/change-proposals').propose(FRAMEWORK, filepath, content, 'codegen');
      console.log(`\n  ${Y}Proposition à relire pour ${filepath}${E}`);
    }
  } catch (e) {
    span.error = e.message; span.end(false);
    console.error(`  ${R}✗ ${e.message}${E}`);
    process.exitCode = 1;
  }
}

// ── Main ──────────────────────────────────────────────────────────────────────
async function main() {
  const args = process.argv.slice(2).filter(a => !a.startsWith('--'));
  if (args[0] === 'source') {
    if (!args[1]) throw Error('Usage: codegen-agent.js source <story key>');
    const story = await plane.fetchIssue(args[1]);
    console.log(JSON.stringify(story, null, 2));
    return;
  }
  const [cmd, arg] = args;

  await llm.assertRunning();

  switch (cmd) {
    case 'spec':    await cmdSpec();          break;
    case 'steps':   await cmdSteps();         break;
    case 'pages':   await cmdPages();         break;
    case 'gherkin': await cmdGherkin(arg);    break;
    case 'preview': DRY_RUN || process.argv.push('--dry-run'); await cmdSpec(); break;
    default:
      console.log(`
${B}Codegen Agent${E} — Génération de code BDD Playwright

  spec           Génère .feature depuis les User Stories Plane
  steps          Génère step definitions TypeScript depuis .feature
  pages          Génère page objects TypeScript depuis .feature
  gherkin <key>  Génère gherkin pour une US spécifique (ex: SCRUM-5)
  preview        Aperçu sans écriture

Options:
  --dry-run            Simulation sans écriture sur disque

Variables d'environnement:
  CODEGEN_BATCH=N      Limite le nombre d'items générés (0 = tous)
`);
  }
}

if (require.main === module) main().catch(e => { console.error(R + e.message + E); process.exitCode = 1; });
module.exports = { cmdSpec, cmdSteps, cmdPages, cmdGherkin };
