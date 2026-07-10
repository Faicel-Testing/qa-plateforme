'use strict';
// ============================================================
// Bug Agent — Analyse + Réparation automatique
// ============================================================
// Usage:
//   node scripts/agents/bug-agent.js analyze              Analyse les échecs (boucle agentique)
//   node scripts/agents/bug-agent.js repair [--max-iter=N] Tente la réparation automatique
//   node scripts/agents/bug-agent.js report               Génère docs/bug-report.html
//
// Guards:
//   AGENT_MAX_ITER=5      Limite les itérations de la boucle (défaut: 5)
//   --max-iter=N          Override par ligne de commande
//
// Coût LLM : élevé (boucle agentique) — contrôlé par AGENT_MAX_ITER
// ============================================================
require('dotenv').config();
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';

const fs   = require('fs');
const path = require('path');
const llm  = require('./llm');
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

const FRAMEWORK    = path.join(__dirname, '..', '..');
const RESULTS_DIR  = path.join(FRAMEWORK, 'allure-results');
const STEPS_DIR     = path.join(FRAMEWORK, 'cypress', 'step_definitions');
const PAGES_DIR     = path.join(FRAMEWORK, 'cypress', 'support', 'pages');
const FEATURES_DIR  = path.join(FRAMEWORK, 'cypress', 'e2e', 'features');
const DOCS_DIR      = path.join(FRAMEWORK, 'docs');

fs.mkdirSync(DOCS_DIR, { recursive: true });

const MAX_ITER_ENV = parseInt(process.env.AGENT_MAX_ITER || '5');
const MAX_ITER_ARG = parseInt(process.argv.find(a => a.startsWith('--max-iter='))?.split('=')[1] || String(MAX_ITER_ENV));
const MAX_ITER     = Math.min(MAX_ITER_ARG, 20);

const DRY_RUN = process.argv.includes('--dry-run');
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
      message: (r.statusDetails?.message || '').slice(0, 500),
      trace:   (r.statusDetails?.trace   || '').slice(0, 300),
      labels:  (r.labels || []).map(l => l.value),
    }));
}

// ── Outils disponibles dans la boucle agentique ───────────────────────────────
const TOOLS = [
  {
    name: 'read_file',
    description: 'Lit le contenu d\'un fichier JavaScript, .feature ou de configuration',
    input_schema: {
      type: 'object',
      properties: {
        file_path: { type: 'string', description: 'Chemin relatif depuis la racine du projet' }
      },
      required: ['file_path']
    }
  },
  {
    name: 'apply_fix',
    description: 'Applique un correctif à un fichier existant (remplace old_str par new_str)',
    input_schema: {
      type: 'object',
      properties: {
        file_path: { type: 'string' },
        old_str:   { type: 'string', description: 'Texte exact à remplacer' },
        new_str:   { type: 'string', description: 'Nouveau texte de remplacement' }
      },
      required: ['file_path', 'old_str', 'new_str']
    }
  },
  {
    name: 'report_analysis',
    description: 'Signale l\'analyse finale et termine la boucle agentique',
    input_schema: {
      type: 'object',
      properties: {
        root_cause:  { type: 'string' },
        fix_applied: { type: 'boolean' },
        fix_summary: { type: 'string' },
        confidence:  { type: 'number' }
      },
      required: ['root_cause', 'fix_applied']
    }
  }
];

// ── Exécution des outils ───────────────────────────────────────────────────────
function executeTool(name, args) {
  if (name === 'read_file') {
    const fp = path.join(FRAMEWORK, args.file_path.replace(/^\/+/, ''));
    if (!fs.existsSync(fp)) return `Fichier introuvable : ${fp}`;
    return fs.readFileSync(fp, 'utf8').slice(0, 3000);
  }

  if (name === 'apply_fix') {
    if (DRY_RUN) return `[DRY-RUN] Correctif non appliqué : ${args.file_path}`;
    const fp = path.join(FRAMEWORK, args.file_path.replace(/^\/+/, ''));
    if (!fs.existsSync(fp)) return `Fichier introuvable : ${fp}`;
    const content = fs.readFileSync(fp, 'utf8');
    if (!content.includes(args.old_str)) return `Texte à remplacer non trouvé dans ${args.file_path}`;
    fs.writeFileSync(fp, content.replace(args.old_str, args.new_str), 'utf8');
    return `✓ Correctif appliqué dans ${args.file_path}`;
  }

  if (name === 'report_analysis') {
    return `ANALYSIS_DONE:${JSON.stringify(args)}`;
  }

  return `Outil inconnu : ${name}`;
}

// ── ANALYZE — Boucle agentique ────────────────────────────────────────────────
async function cmdAnalyze() {
  console.log(`\n${B}=== BUG AGENT — ANALYZE [max-iter=${MAX_ITER}] [${llm.MODEL}] ===${E}`);
  const failures = loadFailures();
  if (!failures.length) { console.log(`  ${G}✓ Aucun échec dans allure-results${E}`); return []; }
  console.log(`  ${C}${failures.length} échec(s) à analyser${E}\n`);

  const analyses = [];

  for (const failure of failures) {
    console.log(`  ${B}[${failure.name.slice(0,55)}]${E}`);
    const context = memory.getContextFor(failure.name);

    const systemPrompt = `Tu es un expert Cypress + Cucumber JavaScript. Analyse cet échec de test BDD et identifie la cause racine.

Test en échec : ${failure.name}
Statut       : ${failure.status}
Message      : ${failure.message}
Stack trace  : ${failure.trace}
Historique   : ${context}

Tu as accès à ces outils :
- read_file   : lire les fichiers du projet (cypress/step_definitions/, cypress/e2e/features/, cypress/support/pages/)
- apply_fix   : appliquer un correctif si tu trouves le bug
- report_analysis : terminer l'analyse avec ton verdict

Commence par lire les fichiers pertinents, puis analyse et propose/applique un correctif.`;

    const messages = [{ role: 'user', content: systemPrompt }];
    const span     = new tracer.Span('bugAnalyze', systemPrompt, llm.MODEL).begin();
    let analysis   = null;
    let iter       = 0;

    while (iter < MAX_ITER) {
      iter++;
      console.log(`  ${C}  Itération ${iter}/${MAX_ITER}${E}`);

      try {
        const resp = await llm.chat(messages, { tools: TOOLS });
        const msg  = resp.message;
        messages.push({ role: 'assistant', content: msg.content || '', tool_calls: msg.tool_calls });

        if (!msg.tool_calls?.length) {
          console.log(`  ${G}  → ${(msg.content || '').slice(0,80)}${E}`);
          analysis = { name: failure.name, fix_applied: false, root_cause: msg.content?.slice(0,200) || '', confidence: 0.5 };
          break;
        }

        for (const tc of msg.tool_calls) {
          const toolName = tc.function.name;
          const toolArgs = llm.parseArgs(tc.function.arguments);
          console.log(`  ${Y}  → ${toolName}(${JSON.stringify(toolArgs).slice(0,60)})${E}`);

          const result = executeTool(toolName, toolArgs);

          if (toolName === 'report_analysis' && result.startsWith('ANALYSIS_DONE:')) {
            const data = JSON.parse(result.replace('ANALYSIS_DONE:', ''));
            analysis   = { name: failure.name, ...data };
            span.confidence = data.confidence || 0;
            console.log(`  ${data.fix_applied ? G+'✓ Fix appliqué' : Y+'⚠ Pas de fix'} | ${data.root_cause?.slice(0,60)}${E}`);
            iter = MAX_ITER;
            break;
          }

          messages.push({ role: 'tool', content: result });
        }
      } catch (e) {
        span.error = e.message;
        console.error(`  ${R}  ✗ Erreur itération ${iter}: ${e.message}${E}`);
        break;
      }
    }

    span.end(!!analysis);
    if (analysis) {
      analyses.push(analysis);
      memory.recordEpisode('bug-agent', [{ tc: failure.name, fix_applied: analysis.fix_applied, confidence: analysis.confidence }],
        `Bug analysis: ${analysis.root_cause?.slice(0,80)||''}`, 'analyze');
    }
    if (iter >= MAX_ITER && !analysis) {
      console.log(`  ${Y}⚠  Max itérations atteint sans conclusion${E}`);
    }
    console.log();
  }

  return analyses;
}

// ── REPAIR — Mode réparation avec vérification ────────────────────────────────
async function cmdRepair() {
  console.log(`\n${B}=== BUG AGENT — REPAIR [max-iter=${MAX_ITER}] ===${E}`);
  console.log(`  ${Y}⚠  Mode repair : les fichiers JavaScript peuvent être modifiés${E}\n`);

  const failures = loadFailures();
  if (!failures.length) { console.log(`  ${G}✓ Aucun échec à réparer${E}`); return; }

  let repaired = 0, failed = 0;

  for (const failure of failures.slice(0, 5)) {
    console.log(`  ${B}[REPAIR] ${failure.name.slice(0,55)}${E}`);

    const _repairTpl = promptStore.get('repair_patch') ||
      'Tu es un expert Cypress JavaScript. Répare ce test en échec.\n\n' +
      'Test    : {test_name}\nErreur  : {error_message}\nTrace   : {stack_trace}\n\n' +
      'IMPORTANT :\n' +
      '1. Lis d\'abord le fichier de steps correspondant (cypress/step_definitions/)\n' +
      '2. Identifie la ligne problématique\n' +
      '3. Applique le correctif minimal avec apply_fix\n' +
      '4. Utilise report_analysis pour terminer\n\n' +
      'Sois conservateur : ne modifie que ce qui est nécessaire pour corriger l\'erreur.';
    const prompt = fmt(_repairTpl, {
      test_name: failure.name, tc: 'N/A',
      error_message: failure.message, stack_trace: failure.trace,
      source_context: 'Utilisez les outils read_file pour lire les fichiers sources.',
    });

    const messages = [{ role: 'user', content: prompt }];
    const span     = new tracer.Span('bugRepair', prompt, llm.MODEL).begin();
    let fixed      = false;

    for (let i = 0; i < MAX_ITER; i++) {
      try {
        const resp = await llm.chat(messages, { tools: TOOLS });
        const msg  = resp.message;
        messages.push({ role: 'assistant', content: msg.content || '', tool_calls: msg.tool_calls });

        if (!msg.tool_calls?.length) break;

        for (const tc of msg.tool_calls) {
          const result = executeTool(tc.function.name, llm.parseArgs(tc.function.arguments));
          if (tc.function.name === 'apply_fix' && result.includes('✓')) { fixed = true; console.log(`  ${G}  ✓ Fix appliqué${E}`); }
          if (tc.function.name === 'report_analysis') { i = MAX_ITER; break; }
          messages.push({ role: 'tool', content: result });
        }
      } catch (e) {
        span.error = e.message; break;
      }
    }

    span.end(fixed);
    promptStore.recordUsage('repair_patch');
    if (fixed) { repaired++; console.log(`  ${G}✓ Réparé${E}\n`); }
    else { failed++; console.log(`  ${Y}⚠  Non réparé${E}\n`); }
  }

  console.log(`  ${B}Bilan repair :${E} ${G}${repaired} réparés${E}  ${Y}${failed} non réparés${E}`);
}

// ── REPORT ────────────────────────────────────────────────────────────────────
async function cmdReport() {
  console.log(`\n${B}=== BUG AGENT — REPORT ===${E}`);
  const analyses = await cmdAnalyze();
  const failures = loadFailures();

  const html = `<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><title>Bug Report</title>
<style>body{font-family:sans-serif;background:#0f172a;color:#e2e8f0;padding:24px}
h1{color:#7c3aed}h2{color:#94a3b8;font-size:1rem;margin-top:24px}
.card{background:#1e293b;border-radius:8px;padding:16px;margin:12px 0}
.fixed{color:#4ade80}.notfixed{color:#fbbf24}.err{color:#f87171}
table{width:100%;border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #1e293b;font-size:.85rem}
th{color:#64748b;text-align:left}pre{background:#0f172a;padding:12px;border-radius:6px;font-size:.75rem;overflow-x:auto}</style></head>
<body>
<h1>🐛 Bug Report — Cypress BDD</h1>
<p style="color:#64748b">Généré le ${new Date().toLocaleString('fr-FR')} | max-iter=${MAX_ITER}</p>
<div class="card">
  <p><strong style="color:#f87171">${failures.length}</strong> échec(s) analysés |
     <strong style="color:#4ade80">${analyses.filter(a=>a.fix_applied).length}</strong> réparés</p>
</div>
<div class="card"><h2>Analyses</h2>
<table><tr><th>Test</th><th>Cause</th><th>Fix</th><th>Confiance</th></tr>
${analyses.map(a=>`<tr>
  <td>${a.name?.slice(0,50)||''}</td>
  <td style="color:#94a3b8">${a.root_cause?.slice(0,60)||''}</td>
  <td class="${a.fix_applied?'fixed':'notfixed'}">${a.fix_applied?'✓ Appliqué':'○ Non appliqué'}</td>
  <td>${a.confidence!=null?Math.round((a.confidence||0)*100)+'%':'?'}</td>
</tr>`).join('')}
</table></div>
${failures.filter(f=>!analyses.find(a=>a.name===f.name)).length?`<div class="card"><h2 class="err">Non analysés</h2>
${failures.filter(f=>!analyses.find(a=>a.name===f.name)).map(f=>`<p class="err">✗ ${f.name} — ${f.message?.slice(0,80)}</p>`).join('')}
</div>`:''}
</body></html>`;

  const outPath = path.join(DOCS_DIR, 'bug-report.html');
  if (!DRY_RUN) { fs.writeFileSync(outPath, html, 'utf8'); console.log(`  ${G}✓ ${outPath}${E}`); }
}

// ── Main ──────────────────────────────────────────────────────────────────────
async function main() {
  const [cmd] = process.argv.slice(2).filter(a => !a.startsWith('--'));
  await llm.assertRunning();

  switch (cmd) {
    case 'analyze': await cmdAnalyze(); break;
    case 'repair':  await cmdRepair();  break;
    case 'report':  await cmdReport();  break;
    default:
      console.log(`
${B}Bug Agent${E} — Analyse & Réparation automatique

  analyze         Boucle agentique : lit les fichiers, identifie la cause racine
  repair          Tente la réparation automatique des tests en échec
  report          Analyse complète + génère docs/bug-report.html

Options:
  --dry-run             Simulation sans modification des fichiers
  --max-iter=N          Limite les itérations de la boucle (défaut: ${MAX_ITER_ENV})

Variables:
  AGENT_MAX_ITER=5      Limite globale des itérations (hard cap: 20)

${Y}⚠  repair modifie les fichiers JavaScript — vérifier avec git diff avant de committer${E}
`);
  }
}

main().catch(e => { console.error(R + e.message + E); process.exit(1); });
