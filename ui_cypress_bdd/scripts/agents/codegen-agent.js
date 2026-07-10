'use strict';
// ============================================================
// Codegen Agent — Génération de code BDD
// ============================================================
// Usage:
//   node scripts/agents/codegen-agent.js spec           Génère .feature depuis US Jira
//   node scripts/agents/codegen-agent.js steps          Génère step definitions JavaScript
//   node scripts/agents/codegen-agent.js pages          Génère page objects JavaScript
//   node scripts/agents/codegen-agent.js gherkin <key>  Génère gherkin pour 1 US
//   node scripts/agents/codegen-agent.js preview        Aperçu sans écriture
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

const FRAMEWORK    = path.join(__dirname, '..', '..');
const FEATURES_DIR = path.join(FRAMEWORK, 'cypress', 'e2e', 'features');
const STEPS_DIR    = path.join(FRAMEWORK, 'cypress', 'step_definitions');
const PAGES_DIR    = path.join(FRAMEWORK, 'cypress', 'support', 'pages');
const DOCS_DIR     = path.join(FRAMEWORK, 'docs');

[FEATURES_DIR, STEPS_DIR, PAGES_DIR, DOCS_DIR].forEach(d => fs.mkdirSync(d, { recursive: true }));

const BATCH_LIMIT = parseInt(process.env.CODEGEN_BATCH || '0');
const DRY_RUN     = process.argv.includes('--dry-run') || process.argv.includes('preview');

const G = '\x1b[32m', R = '\x1b[31m', Y = '\x1b[33m', C = '\x1b[36m', B = '\x1b[1m', E = '\x1b[0m';

// ── spec : génère .feature depuis Jira ────────────────────────────────────────
async function cmdSpec() {
  console.log(`\n${B}=== CODEGEN — SPEC [${llm.MODEL}] ===${E}`);
  let stories;
  try {
    await jira.assertJira();
    stories = await jira.fetchStories();
  } catch (e) {
    console.error(`  ${R}✗ Jira indisponible: ${e.message}${E}`);
    return;
  }
  if (!stories.length) { console.log(`  ${Y}⚠  Aucune story Jira${E}`); return; }

  const items = BATCH_LIMIT ? stories.slice(0, BATCH_LIMIT) : stories;
  console.log(`  ${C}${items.length} stories → .feature${E}\n`);

  let ok = 0, ko = 0;
  for (const story of items) {
    console.log(`  ${B}[${story.key}]${E} ${story.summary.slice(0, 55)}`);
    const span = new tracer.Span('chatSpec', story.summary, llm.MODEL).begin();
    try {
      const prompt = `Tu es un expert QA BDD. Génère un fichier .feature Gherkin complet pour cette User Story.

Clé Jira  : ${story.key}
Titre      : ${story.summary}
Description: ${story.description || 'Non fournie'}
Statut     : ${story.status}

Exigences:
- Feature avec description claire
- Background si nécessaire
- 3 à 5 Scenarios: positif, négatif, limite
- Tags: @${story.key.toLowerCase()} @regression
- Steps en français, style BDD (Given/When/Then)

Réponds UNIQUEMENT avec le contenu .feature (pas de bloc markdown).`;

      const resp    = await llm.chat([{ role: 'user', content: prompt }]);
      const content = (resp.message.content || '').replace(/```[a-z]*\n?/g, '').trim();
      span.response = content; span.end(true);

      const filepath = path.join(FEATURES_DIR, `${story.key.toLowerCase()}.feature`);
      if (DRY_RUN) {
        console.log(`  ${Y}[DRY-RUN]${E} ${path.basename(filepath)}`);
        console.log(`\x1b[2m${content.slice(0, 150)}...\x1b[0m\n`);
      } else {
        fs.writeFileSync(filepath, content, 'utf8');
        console.log(`  ${G}✓ ${filepath}${E}`);
        ok++;
      }
    } catch (e) {
      span.error = e.message; span.end(false);
      console.error(`  ${R}✗ ${story.key}: ${e.message}${E}`);
      ko++;
    }
  }
  console.log(`\n  ${G}✓ ${ok} générés${E}${ko ? `  ${R}✗ ${ko} erreurs${E}` : ''}`);
}

// ── steps : génère step definitions JavaScript (Cypress) ──────────────────────
async function cmdSteps() {
  console.log(`\n${B}=== CODEGEN — STEPS [${llm.MODEL}] ===${E}`);
  if (!fs.existsSync(FEATURES_DIR)) {
    console.log(`  ${Y}⚠  Aucun .feature — lance d'abord: codegen spec${E}`); return;
  }
  const features = fs.readdirSync(FEATURES_DIR).filter(f => f.endsWith('.feature'));
  if (!features.length) { console.log(`  ${Y}⚠  Dossier cypress/e2e/features/ vide${E}`); return; }

  const items = BATCH_LIMIT ? features.slice(0, BATCH_LIMIT) : features;
  console.log(`  ${C}${items.length} features → step definitions${E}\n`);

  for (const featureFile of items) {
    const content = fs.readFileSync(path.join(FEATURES_DIR, featureFile), 'utf8');
    const base    = featureFile.replace('.feature', '');
    console.log(`  ${B}[${featureFile}]${E}`);

    const span = new tracer.Span('chatSteps', content, llm.MODEL).begin();
    try {
      const prompt = `Tu es un expert Cypress + @badeball/cypress-cucumber-preprocessor (JavaScript, pas TypeScript). Génère les step definitions pour ce .feature.

${content}

Contraintes strictes:
- const { Given, When, Then } = require('@badeball/cypress-cucumber-preprocessor');
- Fonctions non-async (style Cypress natif, pas de await sur les commandes cy.*)
- État partagé via le contexte Mocha 'this' (pas de World custom, pas de variables globales)
- Utilise cy.get/cy.contains/.should (retry intégré, pas de waitFor explicite)
- Assertions via .should(), pas de bibliothèque externe

Réponds UNIQUEMENT avec le JavaScript complet (pas de markdown).`;

      const resp = await llm.chat([{ role: 'user', content: prompt }]);
      let code   = (resp.message.content || '').replace(/```javascript\n?|```js\n?|```\n?/g, '').trim();
      span.response = code; span.end(true);

      const filepath = path.join(STEPS_DIR, `${base}.js`);
      if (DRY_RUN) {
        console.log(`  ${Y}[DRY-RUN]${E} ${path.basename(filepath)}\n`);
      } else {
        fs.writeFileSync(filepath, code, 'utf8');
        console.log(`  ${G}✓ ${filepath}${E}`);
      }
    } catch (e) {
      span.error = e.message; span.end(false);
      console.error(`  ${R}✗ ${featureFile}: ${e.message}${E}`);
    }
  }
}

// ── pages : génère page object models (Cypress) ────────────────────────────────
async function cmdPages() {
  console.log(`\n${B}=== CODEGEN — PAGES [${llm.MODEL}] ===${E}`);
  if (!fs.existsSync(FEATURES_DIR)) {
    console.log(`  ${Y}⚠  Aucun .feature — lance d'abord: codegen spec${E}`); return;
  }
  const features = fs.readdirSync(FEATURES_DIR).filter(f => f.endsWith('.feature'));
  const items    = BATCH_LIMIT ? features.slice(0, BATCH_LIMIT) : features;
  console.log(`  ${C}${items.length} features → page objects${E}\n`);

  for (const featureFile of items) {
    const content = fs.readFileSync(path.join(FEATURES_DIR, featureFile), 'utf8');
    const base    = featureFile.replace('.feature', '');
    const className = base.charAt(0).toUpperCase() + base.slice(1) + 'Page';
    console.log(`  ${B}[${featureFile}]${E} → ${className}.js`);

    const span = new tracer.Span('chatPages', content, llm.MODEL).begin();
    try {
      const prompt = `Tu es un expert Cypress JavaScript POM. Génère un Page Object pour ce .feature.

${content}

Contraintes:
- Classe: ${className} (extends BasePage si pertinent, require('./BasePage'))
- Sélecteurs CSS en dur dans les méthodes (cy.get, cy.contains)
- Méthodes non-async pour chaque action (open, fill, click, assert)
- module.exports = { ${className} }
- Aucun cy.wrap(Promise) ni await sur des commandes cy.*

Réponds UNIQUEMENT avec le JavaScript complet.`;

      const resp = await llm.chat([{ role: 'user', content: prompt }]);
      let code   = (resp.message.content || '').replace(/```javascript\n?|```js\n?|```\n?/g, '').trim();
      span.response = code; span.end(true);

      const filepath = path.join(PAGES_DIR, `${className}.js`);
      if (DRY_RUN) {
        console.log(`  ${Y}[DRY-RUN]${E} ${path.basename(filepath)}\n`);
      } else {
        fs.writeFileSync(filepath, code, 'utf8');
        console.log(`  ${G}✓ ${filepath}${E}`);
      }
    } catch (e) {
      span.error = e.message; span.end(false);
      console.error(`  ${R}✗ ${featureFile}: ${e.message}${E}`);
    }
  }
}

// ── gherkin : génère gherkin pour 1 US ────────────────────────────────────────
async function cmdGherkin(usKey) {
  console.log(`\n${B}=== CODEGEN — GHERKIN [${llm.MODEL}] ===${E}`);
  if (!usKey) { console.log(`  Usage: codegen gherkin SCRUM-5`); return; }

  let story;
  try {
    await jira.assertJira();
    story = await jira.fetchIssue(usKey);
  } catch (e) {
    console.error(`  ${R}✗ Jira: ${e.message}${E}`); return;
  }
  console.log(`  ${C}${story.key} — ${story.summary}${E}\n`);

  const prompt = `Génère un fichier .feature Gherkin BDD complet et professionnel.

${story.key} — ${story.summary}
${story.description ? `Description: ${story.description}` : ''}

Exigences:
- Feature descriptif
- Background avec préconditions
- Minimum 5 Scenarios: 2 positifs, 2 négatifs, 1 limite
- Tags: @${story.key.toLowerCase()} @regression
- Steps en français

Réponds uniquement avec le contenu .feature.`;

  const span = new tracer.Span('chatGherkin', prompt, llm.MODEL).begin();
  try {
    const resp    = await llm.chat([{ role: 'user', content: prompt }]);
    const content = (resp.message.content || '').replace(/```[a-z]*\n?/g, '').trim();
    span.response = content; span.end(true);

    console.log(content);
    if (!DRY_RUN) {
      const filepath = path.join(FEATURES_DIR, `${usKey.toLowerCase()}.feature`);
      fs.writeFileSync(filepath, content, 'utf8');
      console.log(`\n  ${G}✓ ${filepath}${E}`);
    }
  } catch (e) {
    span.error = e.message; span.end(false);
    console.error(`  ${R}✗ ${e.message}${E}`);
  }
}

// ── Main ──────────────────────────────────────────────────────────────────────
async function main() {
  const args = process.argv.slice(2).filter(a => !a.startsWith('--'));
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
${B}Codegen Agent${E} — Génération de code BDD Cypress

  spec           Génère .feature depuis les User Stories Jira
  steps          Génère step definitions JavaScript depuis .feature
  pages          Génère page objects JavaScript depuis .feature
  gherkin <key>  Génère gherkin pour une US spécifique (ex: SCRUM-5)
  preview        Aperçu sans écriture

Options:
  --dry-run            Simulation sans écriture sur disque

Variables d'environnement:
  CODEGEN_BATCH=N      Limite le nombre d'items générés (0 = tous)
`);
  }
}

main().catch(e => { console.error(R + e.message + E); process.exit(1); });
