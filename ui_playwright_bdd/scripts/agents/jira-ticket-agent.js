// ============================================
// Jira Ticket Agent — Création automatique de tickets
// ============================================
// Lit les résultats allure-results, analyse les échecs avec Groq,
// et crée automatiquement des tickets Bug dans Jira.
// Vérifie les doublons avant création.
//
// Usage:
//   npm run agent:ticket              → tickets depuis allure-results
//   npm run agent:ticket -- --dry-run → simulation sans créer
//   npm run agent:ticket -- --type=Story → crée des Stories (défaut: Bug)
//
// Output:
//   docs/JIRA_TICKETS_CREATED.md     — rapport des tickets créés
// ============================================

require('dotenv').config();
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';

const llm  = require('./llm');
const jira = require('./jira-fetcher');
const fs   = require('fs');
const path = require('path');

const projectRoot = path.resolve(__dirname, '../../');
const resultsDir  = path.join(projectRoot, 'allure-results');
const docsDir     = path.join(projectRoot, 'docs');

// ── Arguments CLI ─────────────────────────────────────────────────────────────
const DRY_RUN     = process.argv.includes('--dry-run');
const ISSUE_TYPE  = (process.argv.find(a => a.startsWith('--type=')) || '--type=Bug').split('=')[1];
const ISSUE_TYPE_IDS = { Bug: '10005', Story: '10004', Task: '10003' };
const ISSUE_TYPE_ID  = ISSUE_TYPE_IDS[ISSUE_TYPE] || '10005';

// ── Lit les échecs allure-results ─────────────────────────────────────────────
function readFailures() {
  if (!fs.existsSync(resultsDir)) return [];
  return fs.readdirSync(resultsDir)
    .filter(f => f.endsWith('-result.json'))
    .map(f => {
      try { return JSON.parse(fs.readFileSync(path.join(resultsDir, f), 'utf-8')); }
      catch { return null; }
    })
    .filter(r => r && (r.status === 'failed' || r.status === 'broken'));
}

// ── Récupère les tickets existants pour éviter les doublons ──────────────────
async function fetchExistingTitles() {
  try {
    const stories = await jira.fetchStories();
    // Récupère aussi les bugs (type différent)
    const { body } = await require('https').get ? fetchBugs() : { body: { issues: [] } };
    return new Set(stories.map(s => s.summary.toLowerCase()));
  } catch { return new Set(); }
}

async function fetchBugs() {
  const https = require('https');
  const token = Buffer.from(`${process.env.JIRA_EMAIL}:${process.env.JIRA_TOKEN}`).toString('base64');
  const base  = (process.env.JIRA_BASE_URL || '').replace(/\/$/, '');
  const project = process.env.JIRA_PROJECT || 'SCRUM';
  const jql = encodeURIComponent(`project = ${project} AND issuetype = Bug ORDER BY created DESC`);
  return new Promise((resolve, reject) => {
    https.get(`${base}/rest/api/3/search/jql?jql=${jql}&maxResults=100&fields=summary`, {
      headers: { Authorization: `Basic ${token}`, Accept: 'application/json' }
    }, res => {
      let d = ''; res.on('data', c => d += c);
      res.on('end', () => {
        try { resolve(JSON.parse(d)); } catch { resolve({ issues: [] }); }
      });
    }).on('error', () => resolve({ issues: [] }));
  });
}

async function fetchAllExistingTitles() {
  const titles = new Set();
  try {
    const stories = await jira.fetchStories();
    stories.forEach(s => titles.add(s.summary.toLowerCase()));
    const bugsResp = await fetchBugs();
    (bugsResp.issues || []).forEach(i => titles.add((i.fields?.summary || '').toLowerCase()));
  } catch { /* ignore */ }
  return titles;
}

// ── Demande à Groq de structurer les tickets ──────────────────────────────────
async function generateTickets(failures) {
  const failureText = failures.map((f, i) => {
    const error = f.statusDetails?.message || 'No error message';
    const trace = (f.statusDetails?.trace || '').split('\n').slice(0, 8).join('\n');
    const steps = (f.steps || []).map(s => `  [${s.status}] ${s.name}`).slice(0, 6).join('\n');
    return `### Échec ${i + 1}: ${f.name}\n**Status:** ${f.status}\n**Erreur:** ${error}\n**Steps:**\n${steps}\n**Trace:**\n${trace}`;
  }).join('\n\n---\n\n');

  const messages = [
    {
      role: 'system',
      content: `Tu es un expert QA. Pour chaque échec de test, génère un ticket Jira structuré.
Réponds UNIQUEMENT avec un tableau JSON valide, sans texte autour.
Format de chaque ticket :
{
  "summary": "titre court et clair (max 100 chars)",
  "description": "description complète avec contexte, étapes pour reproduire, résultat attendu vs obtenu",
  "priority": "Highest|High|Medium|Low",
  "labels": ["regression", "automated-test"],
  "test_name": "nom du test concerné"
}`
    },
    {
      role: 'user',
      content: `Génère un ticket Jira de type ${ISSUE_TYPE} pour chaque échec ci-dessous.\n\n${failureText}`
    }
  ];

  const resp = await llm.chat(messages);
  const content = resp.message?.content || '[]';

  // Extrait le JSON de la réponse
  const match = content.match(/\[[\s\S]*\]/);
  if (!match) {
    console.warn('LLM response non-JSON, génération manuelle...');
    return failures.map(f => ({
      summary: `[Bug] ${f.name} — ${f.status}`,
      description: `**Test échoué:** ${f.name}\n**Status:** ${f.status}\n**Erreur:** ${f.statusDetails?.message || 'N/A'}\n**Trace:**\n${f.statusDetails?.trace?.slice(0, 800) || 'N/A'}`,
      priority: 'High',
      labels: ['regression', 'automated-test'],
      test_name: f.name
    }));
  }

  try { return JSON.parse(match[0]); }
  catch { return []; }
}

// ── Crée un ticket Bug dans Jira ──────────────────────────────────────────────
async function createTicket(ticket) {
  const https = require('https');
  const token  = Buffer.from(`${process.env.JIRA_EMAIL}:${process.env.JIRA_TOKEN}`).toString('base64');
  const base   = (process.env.JIRA_BASE_URL || '').replace(/\/$/, '');
  const project = process.env.JIRA_PROJECT || 'SCRUM';

  const body = JSON.stringify({
    fields: {
      project:     { key: project },
      issuetype:   { id: ISSUE_TYPE_ID },
      summary:     ticket.summary,
      description: {
        type: 'doc', version: 1,
        content: [{ type: 'paragraph', content: [{ type: 'text', text: ticket.description }] }]
      },
      priority: { name: ticket.priority || 'Medium' },
      labels:   ticket.labels || ['automated-test']
    }
  });

  return new Promise((resolve, reject) => {
    const url = new URL(`${base}/rest/api/3/issue`);
    const req = https.request({
      hostname: url.hostname,
      path: url.pathname,
      method: 'POST',
      headers: {
        Authorization: `Basic ${token}`,
        'Content-Type': 'application/json',
        Accept: 'application/json',
        'Content-Length': Buffer.byteLength(body)
      }
    }, res => {
      let d = ''; res.on('data', c => d += c);
      res.on('end', () => {
        try {
          const r = JSON.parse(d);
          resolve({ status: res.statusCode, key: r.key, error: r.errors });
        } catch { resolve({ status: res.statusCode, error: d }); }
      });
    });
    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

// ── Main ──────────────────────────────────────────────────────────────────────
async function run() {
  await llm.assertRunning();

  const me = await jira.assertJira();
  console.log(`✅ Jira connecté — ${me.displayName}`);
  console.log(`\n=== JIRA TICKET AGENT  [${llm.MODEL}] ===`);
  console.log(`Projet: ${process.env.JIRA_PROJECT}  |  Type: ${ISSUE_TYPE}${DRY_RUN ? '  |  DRY-RUN' : ''}\n`);

  // Lit les échecs
  const failures = readFailures();
  console.log(`📋 Échecs trouvés dans allure-results: ${failures.length}`);

  if (!failures.length) {
    console.log('✅ Aucun échec — aucun ticket à créer.');

    // Propose des tickets depuis le RAG si pas d'échecs
    const bugAnalysis = path.join(docsDir, 'BUG_ANALYSIS.md');
    if (fs.existsSync(bugAnalysis)) {
      console.log('\n💡 BUG_ANALYSIS.md trouvé — vérification des bugs documentés...');
    }
    return;
  }

  // Vérifie les doublons
  console.log('🔍 Vérification des doublons dans Jira...');
  const existingTitles = await fetchAllExistingTitles();
  console.log(`   ${existingTitles.size} ticket(s) existant(s) indexé(s)\n`);

  // Génère les tickets avec Groq
  console.log('🤖 Génération des tickets avec LLM...');
  const rawTickets = await generateTickets(failures);

  // Déduplique les tickets générés (même summary)
  const seen = new Set();
  const tickets = rawTickets.filter(t => {
    const key = t.summary.toLowerCase().trim();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  console.log(`   ${rawTickets.length} généré(s) → ${tickets.length} unique(s) après déduplication\n`);

  // Crée les tickets dans Jira
  const created = [];
  const skipped = [];

  for (const ticket of tickets) {
    const isDuplicate = existingTitles.has(ticket.summary.toLowerCase());

    if (isDuplicate) {
      console.log(`⏭️  Doublon ignoré: ${ticket.summary.slice(0, 60)}`);
      skipped.push(ticket);
      continue;
    }

    if (DRY_RUN) {
      console.log(`[DRY-RUN] Créerait: ${ticket.summary.slice(0, 70)}`);
      created.push({ key: 'DRY-RUN', summary: ticket.summary });
      continue;
    }

    const result = await createTicket(ticket);
    if (result.status === 201) {
      const url = `${process.env.JIRA_BASE_URL}/browse/${result.key}`;
      console.log(`✅ ${result.key} créé — ${ticket.summary.slice(0, 60)}`);
      console.log(`   ${url}`);
      created.push({ key: result.key, summary: ticket.summary, url, priority: ticket.priority });

      // Ajoute le ticket créé aux doublons pour les itérations suivantes
      existingTitles.add(ticket.summary.toLowerCase());
    } else {
      console.error(`❌ Échec création: ${JSON.stringify(result.error)}`);
    }
  }

  // ── Rapport final ────────────────────────────────────────────────────────────
  const ts = new Date().toISOString();
  const report = [
    '# Jira Tickets Created — Rapport',
    '',
    `_${ts} — Projet: ${process.env.JIRA_PROJECT} — Type: ${ISSUE_TYPE} — ${llm.MODEL}_`,
    '',
    `## Résumé`,
    `- Échecs analysés : ${failures.length}`,
    `- Tickets créés   : ${created.length}`,
    `- Doublons ignorés: ${skipped.length}`,
    '',
    '## Tickets créés',
    '',
    created.length
      ? created.map(t => `- [${t.key}](${t.url || '#'}) [${t.priority || 'Medium'}] — ${t.summary}`).join('\n')
      : '_Aucun ticket créé._',
    '',
    '## Doublons ignorés',
    '',
    skipped.length
      ? skipped.map(t => `- ${t.summary}`).join('\n')
      : '_Aucun._',
    ''
  ].join('\n');

  fs.mkdirSync(docsDir, { recursive: true });
  fs.writeFileSync(path.join(docsDir, 'JIRA_TICKETS_CREATED.md'), report, 'utf-8');

  console.log(`\n📄 Rapport: docs/JIRA_TICKETS_CREATED.md`);
  console.log(`🎟️  ${created.length} ticket(s) créé(s)  |  ${skipped.length} doublon(s) ignoré(s)`);
}

run().catch(err => { console.error('Jira ticket agent error:', err.message || err); process.exit(1); });
