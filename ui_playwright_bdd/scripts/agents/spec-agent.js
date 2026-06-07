// ============================================
// Spec Agent — Conversion de specs en User Stories
// ============================================
// Lit un fichier de spécification (markdown, txt, ou texte libre),
// utilise Groq pour extraire des user stories, génère les .feature
// et .ts correspondants, et crée les tickets dans Jira.
//
// Usage:
//   npm run agent:spec -- --file=specs/my-feature.md
//   npm run agent:spec -- --text="L'utilisateur doit pouvoir..."
//   npm run agent:spec -- --jira=SCRUM-5     → depuis une issue Jira
//   npm run agent:spec -- --dry-run          → sans créer de fichiers/tickets
//
// Output:
//   src/features/IdXX_<Name>.feature         — feature file Gherkin
//   src/steps/IdXX_<Name>.ts                 — step definitions TypeScript
//   Jira: Stories créées dans le projet SCRUM
//   docs/SPEC_REPORT.md                      — rapport complet
// ============================================

require('dotenv').config();
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';

const llm  = require('./llm');
const jira = require('./jira-fetcher');
const fs   = require('fs');
const path = require('path');

const projectRoot = path.resolve(__dirname, '../../');
const srcDir      = path.join(projectRoot, 'src');
const featDir     = path.join(srcDir, 'features');
const stepsDir    = path.join(srcDir, 'steps');
const specsDir    = path.join(projectRoot, 'specs');
const docsDir     = path.join(projectRoot, 'docs');

// ── Arguments CLI ─────────────────────────────────────────────────────────────
const DRY_RUN   = process.argv.includes('--dry-run');
const fileArg   = process.argv.find(a => a.startsWith('--file='));
const textArg   = process.argv.find(a => a.startsWith('--text='));
const jiraArg   = process.argv.find(a => a.startsWith('--jira='));

// ── Calcule le prochain IdXX disponible ───────────────────────────────────────
function nextId() {
  if (!fs.existsSync(featDir)) return 'Id06';
  const ids = fs.readdirSync(featDir)
    .map(f => f.match(/^Id(\d+)/))
    .filter(Boolean)
    .map(m => parseInt(m[1], 10));
  const max = ids.length ? Math.max(...ids) : 5;
  return `Id${String(max + 1).padStart(2, '0')}`;
}

// ── Lit la spécification selon la source ─────────────────────────────────────
async function readSpec() {
  if (jiraArg) {
    const key = jiraArg.replace('--jira=', '');
    console.log(`📥 Lecture depuis Jira: ${key}`);
    const issue = await jira.fetchIssue(key);
    return `## ${issue.key} — ${issue.summary}\n\n${issue.description || issue.summary}`;
  }
  if (fileArg) {
    const filePath = fileArg.replace('--file=', '');
    const abs = path.isAbsolute(filePath) ? filePath : path.join(projectRoot, filePath);
    if (!fs.existsSync(abs)) throw new Error(`Fichier introuvable: ${abs}`);
    console.log(`📥 Lecture depuis fichier: ${abs}`);
    return fs.readFileSync(abs, 'utf-8');
  }
  if (textArg) {
    const text = textArg.replace('--text=', '');
    console.log(`📥 Texte fourni directement`);
    return text;
  }
  // Fallback: cherche dans specs/
  fs.mkdirSync(specsDir, { recursive: true });
  const specFiles = fs.existsSync(specsDir)
    ? fs.readdirSync(specsDir).filter(f => f.match(/\.(md|txt|spec)$/))
    : [];
  if (specFiles.length) {
    const latest = specFiles[specFiles.length - 1];
    console.log(`📥 Lecture depuis specs/${latest}`);
    return fs.readFileSync(path.join(specsDir, latest), 'utf-8');
  }
  throw new Error('Aucune spec fournie. Usage: --file=specs/... ou --text="..." ou --jira=SCRUM-5');
}

// ── Tools pour le mode agentic ────────────────────────────────────────────────
const TOOLS = [
  {
    name: 'create_user_story',
    description: 'Crée une user story extraite de la spec avec ses scénarios Gherkin',
    input_schema: {
      type: 'object',
      properties: {
        title:       { type: 'string', description: 'Titre de la user story (max 100 chars)' },
        as_a:        { type: 'string', description: 'En tant que... (rôle utilisateur)' },
        i_want:      { type: 'string', description: 'Je veux... (action souhaitée)' },
        so_that:     { type: 'string', description: 'Afin de... (bénéfice)' },
        priority:    { type: 'string', enum: ['Highest', 'High', 'Medium', 'Low'] },
        feature_id:  { type: 'string', description: 'Identifiant ex: Id06' },
        feature_name:{ type: 'string', description: 'Nom court sans espaces ex: ProfileUpdate' },
        tags:        { type: 'array', items: { type: 'string' }, description: 'Tags Cucumber ex: ["profile","smoke"]' },
        scenarios: {
          type: 'array',
          description: 'Scénarios Gherkin à générer',
          items: {
            type: 'object',
            properties: {
              name:     { type: 'string' },
              steps:    { type: 'array', items: { type: 'string' }, description: 'Étapes Given/When/Then' },
              is_negative: { type: 'boolean', description: 'true si cas négatif/erreur' }
            },
            required: ['name', 'steps']
          }
        }
      },
      required: ['title', 'as_a', 'i_want', 'so_that', 'priority', 'feature_id', 'feature_name', 'tags', 'scenarios']
    }
  },
  {
    name: 'finalize',
    description: 'Signale que toutes les user stories ont été extraites',
    input_schema: {
      type: 'object',
      properties: {
        total_stories: { type: 'number' },
        summary:       { type: 'string' }
      },
      required: ['total_stories', 'summary']
    }
  }
];

// ── Génère le contenu du fichier .feature ─────────────────────────────────────
function buildFeatureFile(story) {
  const { feature_id, feature_name, title, tags, scenarios } = story;
  const allTags = ['@ui', `@${feature_id.toLowerCase()}`, ...tags.map(t => `@${t}`)].join(' ');
  const lines = [
    `${allTags}`,
    `Feature: ${title}`,
    ''
  ];
  scenarios.forEach((sc, i) => {
    lines.push(`  Scenario: ${feature_id}_${feature_name} - ${sc.name}`);
    sc.steps.forEach(step => lines.push(`    ${step}`));
    if (i < scenarios.length - 1) lines.push('');
  });
  return lines.join('\n') + '\n';
}

// ── Génère le squelette du fichier .ts (steps) ────────────────────────────────
function buildStepsFile(story) {
  const { feature_id, feature_name, scenarios } = story;
  const allSteps = new Map();

  scenarios.forEach(sc => {
    sc.steps.forEach(step => {
      const match = step.match(/^(Given|When|Then|And)\s+(.+)$/);
      if (!match) return;
      const [, keyword, text] = match;
      const baseKw = keyword === 'And' ? null : keyword;
      if (baseKw && !allSteps.has(text)) allSteps.set(text, baseKw);
    });
  });

  const imports = [
    `import { Given, When, Then } from '@cucumber/cucumber';`,
    `import { CustomWorld } from '../core/world';`,
    ``
  ];

  const stepDefs = [];
  allSteps.forEach((kw, text) => {
    const fnName = text.replace(/[^a-zA-Z0-9]+(.)/g, (_, c) => c.toUpperCase())
                       .replace(/^./, c => c.toLowerCase())
                       .slice(0, 40);
    stepDefs.push(
      `${kw}('${text}', async function (this: CustomWorld) {`,
      `  // TODO: implement ${fnName}`,
      `  throw new Error('Step not implemented: ${text}');`,
      `});`,
      ``
    );
  });

  return [...imports, ...stepDefs].join('\n');
}

// ── Boucle agentique ──────────────────────────────────────────────────────────
async function extractStories(specText, startId) {
  let currentId = parseInt(startId.replace('Id', ''), 10);

  const messages = [
    {
      role: 'system',
      content: `Tu es un expert QA et Business Analyst. Tu extrais des user stories BDD à partir de spécifications.
Pour chaque fonctionnalité distincte trouvée dans la spec, appelle l'outil create_user_story.
Quand tu as tout extrait, appelle finalize.
Les feature_id doivent commencer à ${startId} et s'incrémenter (Id${currentId}, Id${currentId+1}...).
Les scénarios Gherkin doivent utiliser le langage du framework existant.`
    },
    {
      role: 'user',
      content: `Analyse cette spécification et extrais les user stories BDD avec scénarios Gherkin.\n\n${specText}`
    }
  ];

  const stories = [];
  let done = false;
  let iter = 0;

  while (!done && iter < 15) {
    iter++;
    const resp = await llm.chat(messages, { tools: TOOLS });
    const msg  = resp.message;
    const toolCalls = msg.tool_calls || [];

    if (!toolCalls.length) {
      if (msg.content?.trim()) console.log(msg.content);
      break;
    }

    messages.push(msg);

    for (const tc of toolCalls) {
      const name = tc.function.name;
      const args = llm.parseArgs(tc.function.arguments);
      let result;

      if (name === 'create_user_story') {
        // Assigne l'ID séquentiellement
        args.feature_id = `Id${String(currentId).padStart(2, '0')}`;
        currentId++;
        stories.push(args);
        console.log(`  📌 Story: [${args.feature_id}] ${args.title}`);
        console.log(`     ${args.scenarios.length} scénario(s) — priorité: ${args.priority}`);
        result = `Story enregistrée: ${args.feature_id}_${args.feature_name}`;

      } else if (name === 'finalize') {
        console.log(`\n  ✅ Extraction terminée — ${args.total_stories} story(ies)`);
        done = true;
        result = 'OK';

      } else {
        result = `Unknown tool: ${name}`;
      }

      messages.push({ role: 'tool', content: result });
    }
  }

  return stories;
}

// ── Main ──────────────────────────────────────────────────────────────────────
async function run() {
  await llm.assertRunning();

  const me = await jira.assertJira();
  console.log(`✅ Jira connecté — ${me.displayName}`);
  console.log(`\n=== SPEC AGENT  [${llm.MODEL}] ===`);
  if (DRY_RUN) console.log('   MODE DRY-RUN — aucun fichier ni ticket créé\n');

  // Lit la spec
  const specText = await readSpec();
  console.log(`\n📄 Spec chargée (${specText.length} chars)\n`);

  // Calcule l'ID de départ
  const startId = nextId();
  console.log(`🔢 Prochain ID disponible: ${startId}\n`);
  console.log('🤖 Extraction des user stories avec LLM...\n');

  const stories = await extractStories(specText, startId);

  if (!stories.length) {
    console.log('\n⚠️  Aucune story extraite.');
    return;
  }

  console.log(`\n📦 ${stories.length} story(ies) extraite(s)\n`);

  const created = { features: [], steps: [], jiraTickets: [] };

  for (const story of stories) {
    const baseName = `${story.feature_id}_${story.feature_name}`;

    // ── Fichier .feature ──────────────────────────────────────────────────────
    const featContent = buildFeatureFile(story);
    const featPath    = path.join(featDir, `${baseName}.feature`);
    if (!DRY_RUN) {
      fs.mkdirSync(featDir, { recursive: true });
      fs.writeFileSync(featPath, featContent, 'utf-8');
    }
    console.log(`${DRY_RUN ? '[DRY]' : '✅'} Feature: src/features/${baseName}.feature`);
    created.features.push(featPath);

    // ── Fichier .ts (steps) ───────────────────────────────────────────────────
    const stepsContent = buildStepsFile(story);
    const stepsPath    = path.join(stepsDir, `${baseName}.ts`);
    if (!DRY_RUN) {
      fs.mkdirSync(stepsDir, { recursive: true });
      fs.writeFileSync(stepsPath, stepsContent, 'utf-8');
    }
    console.log(`${DRY_RUN ? '[DRY]' : '✅'} Steps:   src/steps/${baseName}.ts`);
    created.steps.push(stepsPath);

    // ── Ticket Jira Story ─────────────────────────────────────────────────────
    const jiraDesc = [
      `En tant que ${story.as_a},`,
      `Je veux ${story.i_want}`,
      `Afin de ${story.so_that}`,
      ``,
      `Critères d'acceptation:`,
      ...story.scenarios.map(sc => `- ${sc.name}`),
      ``,
      `Feature file: src/features/${baseName}.feature`
    ].join('\n');

    if (!DRY_RUN) {
      try {
        const ticket = await jira.createStory({ summary: story.title, description: jiraDesc });
        console.log(`✅ Jira:    ${ticket.key} — ${story.title.slice(0, 50)}`);
        console.log(`           ${ticket.url}`);
        created.jiraTickets.push({ key: ticket.key, url: ticket.url, title: story.title, priority: story.priority });
      } catch (e) {
        console.error(`⚠️  Jira story échoué: ${e.message}`);
      }
    } else {
      console.log(`[DRY] Jira: créerait Story — ${story.title.slice(0, 60)}`);
    }
    console.log('');
  }

  // ── Epic Jira — regroupe toutes les stories ───────────────────────────────
  if (!DRY_RUN && created.jiraTickets.length) {
    try {
      // Titre de l'Epic = titre de la spec (première ligne ou nom de fichier)
      const epicTitle = specText.split('\n').find(l => l.startsWith('#'))?.replace(/^#+\s*/, '') || 'Feature Group';

      // Description de l'Epic = spec complète reformulée
      const epicDesc = [
        epicTitle,
        '',
        'User Stories incluses:',
        ...created.jiraTickets.map(t => `- ${t.key} [${t.priority || 'Medium'}] — ${t.title}`),
        '',
        'Feature files:',
        ...created.features.map(f => `- ${path.relative(projectRoot, f).replace(/\\/g, '/')}`)
      ].join('\n');

      console.log('🏷️  Création de l\'Epic Jira...');
      const epic = await jira.createEpic({ summary: epicTitle, description: epicDesc });
      console.log(`✅ Epic:    ${epic.key} — ${epicTitle}`);
      console.log(`           ${epic.url}`);

      // Rattache les stories à l'Epic
      const links = await jira.linkToEpic(epic.key, created.jiraTickets.map(t => t.key));
      links.forEach(l => console.log(`   ${l.ok ? '✅' : '❌'} ${l.key} → ${epic.key}`));

      created.epic = epic;
    } catch (e) {
      console.error(`⚠️  Epic échoué: ${e.message}`);
    }
    console.log('');
  }

  // ── Rapport final ─────────────────────────────────────────────────────────
  const ts = new Date().toISOString();
  const report = [
    '# Spec Agent — Rapport de conversion',
    '',
    `_${ts} — ${llm.PROVIDER} / ${llm.MODEL}${DRY_RUN ? ' — DRY-RUN' : ''}_`,
    '',
    `## Résumé`,
    `- Epic Jira         : ${created.epic ? `[${created.epic.key}](${created.epic.url})` : 'N/A'}`,
    `- Stories extraites : ${stories.length}`,
    `- Features créées   : ${created.features.length}`,
    `- Steps créés       : ${created.steps.length}`,
    `- Tickets Jira      : ${created.jiraTickets.length}`,
    '',
    '## User Stories',
    '',
    ...stories.map(s => [
      `### [${s.feature_id}] ${s.title}`,
      `- **En tant que** : ${s.as_a}`,
      `- **Je veux**     : ${s.i_want}`,
      `- **Afin de**     : ${s.so_that}`,
      `- **Priorité**    : ${s.priority}`,
      `- **Scénarios**   : ${s.scenarios.map(sc => sc.name).join(', ')}`,
      ''
    ].join('\n')),
    '## Tickets Jira créés',
    '',
    created.jiraTickets.length
      ? created.jiraTickets.map(t => `- [${t.key}](${t.url}) — ${t.title}`).join('\n')
      : '_Aucun (dry-run ou erreur)._',
    ''
  ].join('\n');

  fs.mkdirSync(docsDir, { recursive: true });
  fs.writeFileSync(path.join(docsDir, 'SPEC_REPORT.md'), report, 'utf-8');
  console.log(`📄 docs/SPEC_REPORT.md`);
}

run().catch(err => { console.error('Spec agent error:', err.message || err); process.exit(1); });
