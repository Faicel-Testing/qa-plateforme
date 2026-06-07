// ============================================
// Jira Agent — Groq + Jira REST API
// ============================================
// Récupère les user stories Jira via jira-fetcher, les mappe aux features
// Playwright avec Groq, et met à jour le RAG.
//
// Usage:    npm run agent:jira
// Output:
//   docs/JIRA_TRACEABILITY.md   — matrice traçabilité stories ↔ tests
//   RAG/qa-knowledge.md         — enrichi avec les stories Jira
// ============================================

require('dotenv').config();
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';

const llm  = require('./llm');
const jira = require('./jira-fetcher');
const fs   = require('fs');
const path = require('path');

const projectRoot = path.resolve(__dirname, '../../');
const srcDir      = path.join(projectRoot, 'src');
const docsDir     = path.join(projectRoot, 'docs');
const ragDir      = path.join(projectRoot, 'RAG');

// ── Lit les features existantes ───────────────────────────────────────────────
function readFeatures() {
  const featDir = path.join(srcDir, 'features');
  if (!fs.existsSync(featDir)) return {};
  const out = {};
  fs.readdirSync(featDir).filter(f => f.endsWith('.feature')).forEach(f => {
    out[f] = fs.readFileSync(path.join(featDir, f), 'utf-8');
  });
  return out;
}

// ── Main ──────────────────────────────────────────────────────────────────────
async function run() {
  await llm.assertRunning();

  const me = await jira.assertJira();
  console.log(`✅ Jira connecté — ${me.displayName} (${me.email})`);
  console.log(`\n=== JIRA AGENT  [${llm.MODEL}] ===`);
  console.log(`Projet: ${jira.JIRA_PROJECT}\n`);

  console.log('📋 Récupération des user stories...');
  const stories = await jira.fetchStories();
  console.log(`   ${stories.length} story(ies) trouvée(s)\n`);

  if (!stories.length) {
    console.log('Aucune story trouvée dans le projet.');
    return;
  }

  const features = readFeatures();
  const featuresText = Object.entries(features)
    .map(([f, c]) => `### ${f}\n\`\`\`gherkin\n${c}\n\`\`\``)
    .join('\n\n');

  const storiesText = stories.map(s =>
    `**${s.key}** [${s.status}] — ${s.summary}\n  ${s.description || '(pas de description)'}`
  ).join('\n\n');

  console.log('🤖 Analyse avec LLM...\n');

  const messages = [
    {
      role: 'system',
      content: 'Tu es un expert QA. Tu analyses des user stories Jira et les mappe aux tests Playwright BDD existants.'
    },
    {
      role: 'user',
      content: `Analyse ces user stories Jira et les feature files Playwright existants.

Pour chaque story, indique :
1. Si elle est couverte par un test existant (quel fichier .feature)
2. Si elle n'est PAS couverte → propose un scénario Gherkin à créer
3. Génère une matrice de traçabilité complète

## User Stories Jira (projet ${jira.JIRA_PROJECT})

${storiesText}

## Feature Files existants

${featuresText}

Format de sortie : Markdown structuré avec tableau de traçabilité + recommandations.`
    }
  ];

  let fullText = '';
  const stream = await llm.chatStream(messages);
  for await (const chunk of stream) {
    const text = chunk.message?.content || '';
    process.stdout.write(text);
    fullText += text;
    if (chunk.done) break;
  }
  console.log('\n');

  // ── Sauvegarde ──────────────────────────────────────────────────────────────
  const ts = new Date().toISOString();

  const traceability = [
    '# Jira ↔ Playwright Traceability Matrix',
    '',
    `_${ts} — Projet: ${jira.JIRA_PROJECT} — ${llm.PROVIDER} / ${llm.MODEL}_`,
    '',
    `## Stories analysées (${stories.length})`,
    '',
    stories.map(s => `- [${s.key}](${s.url}) [${s.status}] — ${s.summary}`).join('\n'),
    '',
    '## Analyse et traçabilité',
    '',
    fullText,
    ''
  ].join('\n');

  fs.mkdirSync(docsDir, { recursive: true });
  fs.mkdirSync(ragDir,  { recursive: true });

  fs.writeFileSync(path.join(docsDir, 'JIRA_TRACEABILITY.md'), traceability, 'utf-8');

  const ragFile = path.join(ragDir, 'qa-knowledge.md');
  const ragExtra = `\n\n## User Stories Jira (${ts})\n\n${storiesText}\n\n## Traçabilité\n\n${fullText}`;
  const existingRag = fs.existsSync(ragFile) ? fs.readFileSync(ragFile, 'utf-8') : '';
  fs.writeFileSync(ragFile, existingRag + ragExtra, 'utf-8');

  console.log(`✅ docs/JIRA_TRACEABILITY.md`);
  console.log(`✅ RAG/qa-knowledge.md enrichi`);
}

run().catch(err => { console.error('Jira agent error:', err.message || err); process.exit(1); });
