'use strict';
// ============================================================
// Bug Agent — Analyse + Réparation automatique (config k6)
// ============================================================
// Usage:
//   node scripts/agents/bug-agent.js analyze              Analyse les seuils dépassés (boucle agentique)
//   node scripts/agents/bug-agent.js repair [--max-iter=N] Tente la recalibration automatique des seuils/VUs
//   node scripts/agents/bug-agent.js report               Génère docs/bug-report.html
//
// Note : contrairement aux frameworks fonctionnels, un seuil dépassé ici n'est
// pas forcément un "bug" — c'est souvent une dégradation backend réelle sous
// charge (résultat legitime) ou un scénario k6 mal calibré. La boucle 'repair'
// ne touche donc QUE k6/scenarios/*.js et k6/config/*.js, jamais l'app testée.
//
// Guards:
//   AGENT_MAX_ITER=5      Limite les itérations de la boucle (défaut: 5)
//   --max-iter=N          Override par ligne de commande
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

const FRAMEWORK     = path.join(__dirname, '..', '..');
const REPORTS_DIR   = path.join(FRAMEWORK, 'reports');
const SCENARIOS_DIR  = path.join(FRAMEWORK, 'k6', 'scenarios');
const LIB_DIR        = path.join(FRAMEWORK, 'k6', 'lib');
const DOCS_DIR        = path.join(FRAMEWORK, 'docs');
const SCENARIOS       = ['smoke', 'load', 'stress'];

fs.mkdirSync(DOCS_DIR, { recursive: true });

const MAX_ITER_ENV = parseInt(process.env.AGENT_MAX_ITER || '5');
const MAX_ITER_ARG = parseInt(process.argv.find(a => a.startsWith('--max-iter='))?.split('=')[1] || String(MAX_ITER_ENV));
const MAX_ITER     = Math.min(MAX_ITER_ARG, 20);

const DRY_RUN = process.argv.includes('--dry-run');
const G = '\x1b[32m', R = '\x1b[31m', Y = '\x1b[33m', C = '\x1b[36m', B = '\x1b[1m', E = '\x1b[0m';

// ── Lecture reports/summary-*.json ─────────────────────────────────────────────
function loadBreaches() {
  const breaches = [];
  for (const scenario of SCENARIOS) {
    const fp = path.join(REPORTS_DIR, `summary-${scenario}.json`);
    if (!fs.existsSync(fp)) continue;
    let summary;
    try { summary = JSON.parse(fs.readFileSync(fp, 'utf8')); } catch { continue; }
    for (const [metricName, metric] of Object.entries(summary.metrics || {})) {
      for (const [expr, wasBreached] of Object.entries(metric.thresholds || {})) {
        if (!wasBreached) continue;
        breaches.push({
          name: `${scenario}/${metricName}`, scenario, metric: metricName, expr,
          value: metric['p(95)'] ?? metric.value ?? metric.avg ?? null,
        });
      }
    }
  }
  return breaches;
}

// ── Outils disponibles dans la boucle agentique ───────────────────────────────
const TOOLS = [
  {
    name: 'read_file',
    description: 'Lit le contenu d\'un fichier k6 (scénario, lib, config)',
    input_schema: {
      type: 'object',
      properties: { file_path: { type: 'string', description: 'Chemin relatif depuis la racine du projet' } },
      required: ['file_path']
    }
  },
  {
    name: 'apply_fix',
    description: 'Applique un correctif à un scénario k6 existant (remplace old_str par new_str)',
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

const ALLOWED_PREFIXES = ['k6/scenarios', 'k6/lib', 'k6/config'];

function isAllowed(relPath) {
  const norm = relPath.replace(/^\/+/, '').replace(/\\/g, '/');
  return ALLOWED_PREFIXES.some(p => norm.startsWith(p));
}

// ── Exécution des outils ───────────────────────────────────────────────────────
function executeTool(name, args) {
  if (name === 'read_file') {
    if (!isAllowed(args.file_path)) return `Accès refusé : hors périmètre k6/ (${args.file_path})`;
    const fp = path.join(FRAMEWORK, args.file_path.replace(/^\/+/, ''));
    if (!fs.existsSync(fp)) return `Fichier introuvable : ${fp}`;
    return fs.readFileSync(fp, 'utf8').slice(0, 3000);
  }

  if (name === 'apply_fix') {
    if (!isAllowed(args.file_path)) return `Accès refusé : hors périmètre k6/ (${args.file_path})`;
    if (DRY_RUN) return `[DRY-RUN] Correctif non appliqué : ${args.file_path}`;
    const fp = path.join(FRAMEWORK, args.file_path.replace(/^\/+/, ''));
    if (!fs.existsSync(fp)) return `Fichier introuvable : ${fp}`;
    const content = fs.readFileSync(fp, 'utf8');
    if (!content.includes(args.old_str)) return `Texte à remplacer non trouvé dans ${args.file_path}`;
    fs.writeFileSync(fp, content.replace(args.old_str, args.new_str), 'utf8');
    return `✓ Correctif appliqué dans ${args.file_path}`;
  }

  if (name === 'report_analysis') return `ANALYSIS_DONE:${JSON.stringify(args)}`;
  return `Outil inconnu : ${name}`;
}

// ── ANALYZE — Boucle agentique ────────────────────────────────────────────────
async function cmdAnalyze() {
  console.log(`\n${B}=== BUG AGENT — ANALYZE [max-iter=${MAX_ITER}] [${llm.MODEL}] ===${E}`);
  const breaches = loadBreaches();
  if (!breaches.length) { console.log(`  ${G}✓ Aucun seuil dépassé dans reports/${E}`); return []; }
  console.log(`  ${C}${breaches.length} dépassement(s) à analyser${E}\n`);

  const analyses = [];

  for (const breach of breaches) {
    console.log(`  ${B}[${breach.name.slice(0,55)}]${E}`);
    const context = memory.getContextFor(breach.name);

    const systemPrompt = `Tu es un expert k6 (tests de performance). Analyse ce dépassement de seuil et identifie la cause racine.

Scénario     : ${breach.scenario}
Métrique     : ${breach.metric}
Seuil        : ${breach.expr}
Valeur observée : ${breach.value}
Historique   : ${context}

Tu as accès à ces outils :
- read_file   : lire les fichiers du projet (k6/scenarios/, k6/lib/, k6/config/) — RIEN d'autre
- apply_fix   : recalibrer un seuil ou un palier de VUs si le scénario est mal configuré
- report_analysis : terminer l'analyse avec ton verdict

Important : QACart Todo est une démo publique partagée, pas un environnement dédié. Une dégradation
sous charge peut être un résultat LÉGITIME (backend réel plus lent), pas un bug de scénario.
Ne "corrige" un seuil que si tu es sûr qu'il est mal calibré, pas pour masquer une vraie dégradation.

Commence par lire les fichiers pertinents, puis analyse et propose/applique un correctif si justifié.`;

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
          analysis = { name: breach.name, fix_applied: false, root_cause: msg.content?.slice(0,200) || '', confidence: 0.5 };
          break;
        }

        for (const tc of msg.tool_calls) {
          const toolName = tc.function.name;
          const toolArgs = llm.parseArgs(tc.function.arguments);
          console.log(`  ${Y}  → ${toolName}(${JSON.stringify(toolArgs).slice(0,60)})${E}`);

          const result = executeTool(toolName, toolArgs);

          if (toolName === 'report_analysis' && result.startsWith('ANALYSIS_DONE:')) {
            const data = JSON.parse(result.replace('ANALYSIS_DONE:', ''));
            analysis   = { name: breach.name, ...data };
            span.confidence = data.confidence || 0;
            console.log(`  ${data.fix_applied ? G+'✓ Fix appliqué' : Y+'⚠ Pas de fix'} | ${data.root_cause?.slice(0,60)}${E}`);
            iter = MAX_ITER;
            break;
          }

          messages.push({ role: 'tool', tool_call_id: tc.id, content: result });
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
      memory.recordEpisode('bug-agent', [{ tc: breach.name, fix_applied: analysis.fix_applied, confidence: analysis.confidence }],
        `Analyse: ${analysis.root_cause?.slice(0,80)||''}`, 'analyze');
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
  console.log(`  ${Y}⚠  Mode repair : seuls k6/scenarios/, k6/lib/, k6/config/ peuvent être modifiés${E}\n`);

  const breaches = loadBreaches();
  if (!breaches.length) { console.log(`  ${G}✓ Aucun seuil à recalibrer${E}`); return; }

  let repaired = 0, failed = 0;

  for (const breach of breaches.slice(0, 5)) {
    console.log(`  ${B}[REPAIR] ${breach.name.slice(0,55)}${E}`);

    const _repairTpl = promptStore.get('repair_patch') ||
      'Tu es un expert k6. Recalibre ce scénario si son seuil ou sa charge est mal configuré.\n\n' +
      'Scénario : {test_name}\nSeuil    : {error_message}\nObservé  : {stack_trace}\n\n' +
      'IMPORTANT :\n' +
      '1. Lis d\'abord le fichier de scénario (k6/scenarios/)\n' +
      '2. Ne recalibre QUE si le seuil est manifestement irréaliste pour une démo publique\n' +
      '3. Applique le correctif minimal avec apply_fix\n' +
      '4. Utilise report_analysis pour terminer\n\n' +
      'Sois conservateur : ne modifie que ce qui est nécessaire.';
    const prompt = fmt(_repairTpl, {
      test_name: breach.name, tc: 'N/A',
      error_message: breach.expr, stack_trace: `valeur observée: ${breach.value}`,
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
          messages.push({ role: 'tool', tool_call_id: tc.id, content: result });
        }
      } catch (e) {
        span.error = e.message; break;
      }
    }

    span.end(fixed);
    promptStore.recordUsage('repair_patch');
    if (fixed) { repaired++; console.log(`  ${G}✓ Recalibré${E}\n`); }
    else { failed++; console.log(`  ${Y}⚠  Non modifié${E}\n`); }
  }

  console.log(`  ${B}Bilan repair :${E} ${G}${repaired} recalibrés${E}  ${Y}${failed} inchangés${E}`);
}

// ── REPORT ────────────────────────────────────────────────────────────────────
async function cmdReport() {
  console.log(`\n${B}=== BUG AGENT — REPORT ===${E}`);
  const analyses = await cmdAnalyze();
  const breaches = loadBreaches();

  const html = `<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><title>Bug Report — k6 Performance</title>
<style>body{font-family:sans-serif;background:#0f172a;color:#e2e8f0;padding:24px}
h1{color:#7c3aed}h2{color:#94a3b8;font-size:1rem;margin-top:24px}
.card{background:#1e293b;border-radius:8px;padding:16px;margin:12px 0}
.fixed{color:#4ade80}.notfixed{color:#fbbf24}.err{color:#f87171}
table{width:100%;border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #1e293b;font-size:.85rem}
th{color:#64748b;text-align:left}pre{background:#0f172a;padding:12px;border-radius:6px;font-size:.75rem;overflow-x:auto}</style></head>
<body>
<h1>🐢 Bug Report — k6 Performance</h1>
<p style="color:#64748b">Généré le ${new Date().toLocaleString('fr-FR')} | max-iter=${MAX_ITER}</p>
<div class="card">
  <p><strong style="color:#f87171">${breaches.length}</strong> seuil(s) dépassé(s) analysés |
     <strong style="color:#4ade80">${analyses.filter(a=>a.fix_applied).length}</strong> recalibrés</p>
</div>
<div class="card"><h2>Analyses</h2>
<table><tr><th>Scénario/Métrique</th><th>Cause</th><th>Fix</th><th>Confiance</th></tr>
${analyses.map(a=>`<tr>
  <td>${a.name?.slice(0,50)||''}</td>
  <td style="color:#94a3b8">${a.root_cause?.slice(0,60)||''}</td>
  <td class="${a.fix_applied?'fixed':'notfixed'}">${a.fix_applied?'✓ Recalibré':'○ Inchangé'}</td>
  <td>${a.confidence!=null?Math.round((a.confidence||0)*100)+'%':'?'}</td>
</tr>`).join('')}
</table></div>
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
${B}Bug Agent${E} — Analyse & Recalibration automatique (k6)

  analyze         Boucle agentique : lit les fichiers, identifie la cause racine
  repair          Tente la recalibration automatique des seuils/scénarios mal configurés
  report          Analyse complète + génère docs/bug-report.html

Options:
  --dry-run             Simulation sans modification des fichiers
  --max-iter=N          Limite les itérations de la boucle (défaut: ${MAX_ITER_ENV})

Variables:
  AGENT_MAX_ITER=5      Limite globale des itérations (hard cap: 20)

${Y}⚠  repair modifie uniquement k6/scenarios/, k6/lib/, k6/config/ — jamais l'app testée${E}
`);
  }
}

main().catch(e => { console.error(R + e.message + E); process.exit(1); });
