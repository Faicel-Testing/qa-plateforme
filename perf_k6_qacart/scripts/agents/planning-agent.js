'use strict';
// ============================================================
// Planning Agent — Gestion projet & couverture (k6)
// ============================================================
// Usage:
//   node scripts/agents/planning-agent.js stories              Liste les US Jira
//   node scripts/agents/planning-agent.js stories create       Crée les US dans Jira
//   node scripts/agents/planning-agent.js sprint list          Liste les sprints
//   node scripts/agents/planning-agent.js sprint create <nom>  Crée un sprint
//   node scripts/agents/planning-agent.js sprint start <id>    Démarre un sprint
//   node scripts/agents/planning-agent.js sprint close <id>    Ferme un sprint
//   node scripts/agents/planning-agent.js coverage analyze     Analyse la couverture des scénarios k6
//   node scripts/agents/planning-agent.js coverage gaps        Identifie les manques (types de charge)
//   node scripts/agents/planning-agent.js coverage suggest     Suggestions LLM
//
// Coût LLM : bas à moyen — seulement sur coverage suggest
// ============================================================
require('dotenv').config();
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';

const fs   = require('fs');
const path = require('path');
const https = require('https');
const llm  = require('./llm');
const jira = require('./jira-fetcher');
const tracer = require('./shared/tracer');

const FRAMEWORK     = path.join(__dirname, '..', '..');
const SCENARIOS_DIR  = path.join(FRAMEWORK, 'k6', 'scenarios');
const DOCS_DIR        = path.join(FRAMEWORK, 'docs');

fs.mkdirSync(DOCS_DIR, { recursive: true });

const DRY_RUN = process.argv.includes('--dry-run');
const PROJECT = process.env.JIRA_PROJECT || 'SCRUM';
const JIRA_BASE_URL = (process.env.JIRA_BASE_URL || '').replace(/\/$/, '');
const JIRA_AUTH = Buffer.from(`${process.env.JIRA_EMAIL}:${process.env.JIRA_TOKEN}`).toString('base64');

const G = '\x1b[32m', R = '\x1b[31m', Y = '\x1b[33m', C = '\x1b[36m', B = '\x1b[1m', E = '\x1b[0m';

// ── Agile API helper ───────────────────────────────────────────────────────────
function agileGet(endpoint) {
  return new Promise((resolve, reject) => {
    const url = `${JIRA_BASE_URL}/rest/agile/1.0${endpoint}`;
    https.get(url, { headers: { Authorization: `Basic ${JIRA_AUTH}`, Accept: 'application/json' } }, res => {
      let d = ''; res.on('data', c => d += c);
      res.on('end', () => { try { resolve({ status: res.statusCode, body: JSON.parse(d) }); } catch { reject(new Error(d.slice(0,200))); } });
    }).on('error', reject);
  });
}

function agilePost(endpoint, body) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(body);
    const url  = new URL(`${JIRA_BASE_URL}/rest/agile/1.0${endpoint}`);
    const req  = https.request({ hostname: url.hostname, path: url.pathname, method: 'POST',
      headers: { Authorization: `Basic ${JIRA_AUTH}`, 'Content-Type': 'application/json', Accept: 'application/json', 'Content-Length': Buffer.byteLength(data) }
    }, res => {
      let d = ''; res.on('data', c => d += c);
      res.on('end', () => { try { resolve({ status: res.statusCode, body: d ? JSON.parse(d) : {} }); } catch { resolve({ status: res.statusCode, body: d }); } });
    });
    req.on('error', reject); req.write(data); req.end();
  });
}

// ── STORIES ───────────────────────────────────────────────────────────────────
async function cmdStories(action) {
  console.log(`\n${B}=== PLANNING — STORIES ===${E}`);
  try {
    await jira.assertJira();
    const stories = await jira.fetchStories(PROJECT, 100);

    if (action === 'create') {
      console.log(`  ${Y}⚠  Création manuelle requise — utilisez Jira UI ou jira-ticket-agent${E}`);
      console.log(`  URL Backlog : ${JIRA_BASE_URL}/jira/software/projects/${PROJECT}/boards`);
      return;
    }

    console.log(`  ${C}${stories.length} User Stories dans ${PROJECT}${E}\n`);
    console.log(`  ${'Clé'.padEnd(12)} ${'Statut'.padEnd(15)} ${'Priorité'.padEnd(10)} Titre`);
    console.log(`  ${'─'.repeat(80)}`);
    for (const s of stories) {
      const statusColor = s.status === 'Done' ? G : s.status === 'In Progress' ? C : '';
      console.log(`  ${s.key.padEnd(12)} ${statusColor}${s.status.padEnd(15)}${E} ${s.priority.padEnd(10)} ${s.summary.slice(0,45)}`);
    }
  } catch (e) {
    console.error(`  ${R}✗ Jira: ${e.message}${E}`);
  }
}

// ── SPRINT ────────────────────────────────────────────────────────────────────
async function cmdSprint(action, arg) {
  console.log(`\n${B}=== PLANNING — SPRINT ${action?.toUpperCase()||''} ===${E}`);
  try {
    const { body: boardBody } = await agileGet(`/board?projectKeyOrId=${PROJECT}`);
    const board = boardBody.values?.[0];
    if (!board) { console.log(`  ${Y}⚠  Aucun board Agile trouvé pour ${PROJECT}${E}`); return; }
    const boardId = board.id;

    if (action === 'list' || !action) {
      const { body } = await agileGet(`/board/${boardId}/sprint?state=active,future,closed&maxResults=20`);
      const sprints  = body.values || [];
      console.log(`  ${C}Board : ${board.name}${E}\n`);
      sprints.forEach(s => {
        const stateColor = s.state === 'active' ? G : s.state === 'future' ? C : '\x1b[2m';
        console.log(`  ${stateColor}[${s.state.toUpperCase()}]${E}  #${s.id}  ${s.name}  ${s.startDate?.slice(0,10)||''}→${s.endDate?.slice(0,10)||''}`);
      });
    } else if (action === 'create') {
      const name = arg || `Sprint ${new Date().toLocaleDateString('fr-FR')}`;
      if (DRY_RUN) { console.log(`  ${Y}[DRY-RUN] Aurait créé: ${name}${E}`); return; }
      const { status, body } = await agilePost(`/sprint`, { name, originBoardId: boardId });
      if (status === 201) console.log(`  ${G}✓ Sprint créé : #${body.id} — ${name}${E}`);
      else console.error(`  ${R}✗ HTTP ${status}: ${JSON.stringify(body).slice(0,100)}${E}`);
    } else if (action === 'start') {
      if (!arg) { console.log(`  Usage: planning sprint start <id>`); return; }
      if (DRY_RUN) { console.log(`  ${Y}[DRY-RUN] Aurait démarré sprint #${arg}${E}`); return; }
      const start = new Date(); const end = new Date(start); end.setDate(end.getDate()+14);
      const { status } = await new Promise((resolve, reject) => {
        const data = JSON.stringify({ state: 'active', startDate: start.toISOString(), endDate: end.toISOString() });
        const url  = new URL(`${JIRA_BASE_URL}/rest/agile/1.0/sprint/${arg}`);
        const req  = https.request({ hostname: url.hostname, path: url.pathname, method: 'POST',
          headers: { Authorization: `Basic ${JIRA_AUTH}`, 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) }
        }, res => resolve({ status: res.statusCode }));
        req.on('error', reject); req.write(data); req.end();
      });
      console.log(status < 300 ? `  ${G}✓ Sprint #${arg} démarré${E}` : `  ${R}✗ HTTP ${status}${E}`);
    } else if (action === 'close') {
      if (!arg) { console.log(`  Usage: planning sprint close <id>`); return; }
      if (DRY_RUN) { console.log(`  ${Y}[DRY-RUN] Aurait fermé sprint #${arg}${E}`); return; }
      const data = JSON.stringify({ state: 'closed' });
      const url  = new URL(`${JIRA_BASE_URL}/rest/agile/1.0/sprint/${arg}`);
      const { status } = await new Promise((resolve, reject) => {
        const req = https.request({ hostname: url.hostname, path: url.pathname, method: 'POST',
          headers: { Authorization: `Basic ${JIRA_AUTH}`, 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) }
        }, res => resolve({ status: res.statusCode }));
        req.on('error', reject); req.write(data); req.end();
      });
      console.log(status < 300 ? `  ${G}✓ Sprint #${arg} fermé${E}` : `  ${R}✗ HTTP ${status}${E}`);
    }
  } catch (e) {
    console.error(`  ${R}✗ ${e.message}${E}`);
  }
}

// ── COVERAGE ──────────────────────────────────────────────────────────────────
// Types de charge attendus dans un framework k6 mature (pas des tags Gherkin ici,
// mais la présence de scénarios/patterns dans k6/scenarios/*.js).
const COVERAGE_TYPES = ['smoke', 'load', 'stress', 'soak', 'spike'];

async function cmdCoverage(action) {
  console.log(`\n${B}=== PLANNING — COVERAGE ===${E}`);
  if (!fs.existsSync(SCENARIOS_DIR)) {
    console.log(`  ${Y}⚠  Aucun scénario trouvé dans k6/scenarios/${E}`); return;
  }

  const files = fs.readdirSync(SCENARIOS_DIR).filter(f => f.endsWith('.js'));
  const present = files.map(f => f.replace('.js', ''));

  console.log(`  ${C}${files.length} scénario(s) k6 présents : ${present.join(', ')}${E}\n`);

  if (action === 'analyze' || !action) {
    for (const f of files) {
      const content = fs.readFileSync(path.join(SCENARIOS_DIR, f), 'utf8');
      const stages = (content.match(/duration:\s*'([^']+)'/g) || []).length;
      const thresholds = (content.match(/thresholds\s*:/g) || []).length;
      console.log(`  ${G}✓${E} ${f.padEnd(20)} ${stages} palier(s)  ${thresholds ? 'thresholds définis' : Y+'pas de threshold'+E}`);
    }
  } else if (action === 'gaps') {
    const missing = COVERAGE_TYPES.filter(t => !present.includes(t));
    if (missing.length) console.log(`  ${Y}⚠  Types de charge manquants : ${R}${missing.join(', ')}${E}`);
    else console.log(`  ${G}✓  Couverture complète (smoke/load/stress)${E}`);
    if (missing.includes('soak')) console.log(`  \x1b[2m  soak : charge modérée sur longue durée (30min+), détecte fuites mémoire/dégradation lente\x1b[0m`);
    if (missing.includes('spike')) console.log(`  \x1b[2m  spike : pic brutal de trafic, teste l'élasticité/l'auto-scaling\x1b[0m`);
  } else if (action === 'suggest') {
    const missing = COVERAGE_TYPES.filter(t => !present.includes(t));
    if (!missing.length) { console.log(`  ${G}✓ Couverture complète — aucune suggestion nécessaire${E}`); return; }
    console.log(`  ${C}Génération suggestions LLM pour ${missing.length} manque(s)...${E}\n`);

    const span = new tracer.Span('coverageSuggest', JSON.stringify(missing), llm.MODEL).begin();
    try {
      const prompt = `Tu es un expert k6. Suggère la configuration 'options' k6 pour ces types de charge manquants sur QACart Todo (démo publique partagée, garder les VUs modestes).

Manques identifiés: ${missing.join(', ')}

Pour chaque manque, génère un bloc 'options' k6 concis (stages + thresholds) avec un commentaire expliquant l'objectif.`;

      const resp = await llm.chat([{ role: 'user', content: prompt }]);
      span.response = resp.message.content; span.end(true);
      console.log(resp.message.content);
    } catch (e) {
      span.error = e.message; span.end(false);
      console.error(`  ${R}✗ ${e.message}${E}`);
    }
  }
}

// ── Main ──────────────────────────────────────────────────────────────────────
async function main() {
  const args = process.argv.slice(2).filter(a => !a.startsWith('--'));
  const [cmd, sub, arg3] = args;
  await llm.assertRunning();

  switch (cmd) {
    case 'stories':   await cmdStories(sub);         break;
    case 'sprint':    await cmdSprint(sub, arg3);     break;
    case 'coverage':  await cmdCoverage(sub);         break;
    default:
      console.log(`
${B}Planning Agent${E} — Gestion projet & couverture (k6)

  stories [create]         Liste ou crée les User Stories Jira
  sprint list              Liste les sprints du board
  sprint create [nom]      Crée un nouveau sprint
  sprint start <id>        Démarre un sprint
  sprint close <id>        Ferme un sprint
  coverage analyze         Analyse les scénarios k6 présents (paliers, thresholds)
  coverage gaps            Identifie les types de charge manquants (soak, spike...)
  coverage suggest         Suggestions LLM pour combler les manques

Options:
  --dry-run    Simulation sans écriture

Variables:
  JIRA_PROJECT=SCRUM       Projet Jira cible
`);
  }
}

main().catch(e => { console.error(R + e.message + E); process.exit(1); });
