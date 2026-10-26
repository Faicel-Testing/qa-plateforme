'use strict';
// ============================================================
// Bug Agent — Analyse + Réparation automatique
// ============================================================
// Absorbe et enrichit : bug-analyzer.js (existant)
//
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
const verifier = require('./shared/agent-verifier').createVerifier({ agent: 'bug', root: FRAMEWORK, runtimeProcess: process });
const RESULTS_DIR = require('./shared/pipeline-runtime').resultDirectory(FRAMEWORK);
const DOCS_DIR     = path.join(FRAMEWORK, 'docs');

fs.mkdirSync(DOCS_DIR, { recursive: true });

// ── Guard : limite les itérations de boucle agentique ─────────────────────────
const MAX_ITER_ENV = parseInt(process.env.AGENT_MAX_ITER || '5');
const MAX_ITER_ARG = parseInt(process.argv.find(a => a.startsWith('--max-iter='))?.split('=')[1] || String(MAX_ITER_ENV));
const MAX_ITER     = Math.min(MAX_ITER_ARG, 20); // hard cap à 20 même si forcé

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
      message: r.statusDetails?.message || '',
      trace: r.statusDetails?.trace || '',
      labels:  (r.labels || []).map(l => l.value),
    }));
}

// ── Outils disponibles dans la boucle agentique ───────────────────────────────
const TOOLS = [
  {
    name: 'read_file',
    description: 'Lit le contenu d\'un fichier TypeScript, .feature ou de configuration',
    input_schema: {
      type: 'object',
      properties: {
        file_path: { type: 'string', description: 'Chemin relatif depuis la racine du projet' },
        line_start: { type: 'integer', description: 'Première ligne, inclusive, défaut 1' },
        line_end: { type: 'integer', description: 'Dernière ligne inclusive, maximum 400 lignes par lecture. EOF indique la fin.' }
      },
      required: ['file_path']
    }
  },
  {
    name: 'apply_fix',
    description: 'Propose un correctif pour revue humaine; ne modifie jamais le fichier source (fix_applied=false)',
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
    return require('./shared/analysis-evidence').readSource(FRAMEWORK, args);
  }

  if (name === 'apply_fix') {
    if (DRY_RUN) return `[DRY-RUN] Correctif non appliqué : ${args.file_path}`;
    const proposals = require('./shared/change-proposals');
    const fp = proposals.target(FRAMEWORK, args.file_path);
    if (!fs.existsSync(fp)) return `Fichier introuvable : ${fp}`;
    const content = fs.readFileSync(fp, 'utf8');
    if (!content.includes(args.old_str)) return `Texte à remplacer non trouvé dans ${args.file_path}`;
    if (!args.old_str || content.split(args.old_str).length !== 2) throw new Error('Repair requires one unambiguous match');
    const proposal = proposals.propose(FRAMEWORK, fp, content.replace(args.old_str, args.new_str), 'bug-repair');
    return `REVIEW REQUIRED: ${proposal.id}; proposed only, fix_applied=false`;
  }

  if (name === 'report_analysis') {
    return `ANALYSIS_DONE:${JSON.stringify({ ...args, fix_applied: false })}`;
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
  let providerUnavailable = false;

  for (const failure of failures) {
    if (providerUnavailable) {
      analyses.push({ name: failure.name, status: 'NOT_EVALUATED', fix_applied: false, root_cause: '',
        error: 'Provider unavailable or rate limited earlier in this batch; no additional request sent.' });
      continue;
    }
    console.log(`  ${B}[${failure.name.slice(0,55)}]${E}`);
    const context = memory.getContextFor(failure.name);

    const systemPrompt = `Tu es un expert Playwright TypeScript. Analyse cet échec de test BDD et identifie la cause racine.

Test en échec : ${failure.name}
Statut       : ${failure.status}
Message      : ${failure.message}
Stack trace  : ${failure.trace}
Historique   : ${context}
${require('./shared/analysis-evidence').sourceContext(FRAMEWORK, failure)}

Tu as accès à ces outils :
- read_file   : lire les fichiers du projet (src/steps/, src/features/, src/pages/)
- report_analysis : terminer l'analyse avec ton verdict

Mode analyse en lecture seule : ne modifie aucun fichier ni assertion.
Lis les fichiers pertinents puis appelle report_analysis. EOF signifie fin du fichier : ne redemande pas de lignes au-delà.
Tu as ${MAX_ITER} appels au maximum, le dernier est réservé à la conclusion.
Distingue preuve et hypothèse. Le comportement attendu doit être confirmé par les exigences.
Si la correction relève de l'application testée, indique-le sans contourner le test.`;

    const reads = new Map();
    const modelContext = require('./shared/analysis-evidence').sourceContext(FRAMEWORK, failure) + '\nHistory:\n' + context;
    const span     = new tracer.Span('bugAnalyze', systemPrompt, llm.MODEL).begin();
    let analysis   = null;
    let iter       = 0;

    while (iter < MAX_ITER) {
      iter++;
      console.log(`  ${C}  Itération ${iter}/${MAX_ITER}${E}`);

      try {
        const { analysisPrompt, requestAnalysis } = require('./shared/llm-analysis');
        const decision = await requestAnalysis(llm,
          limit => analysisPrompt(failure, modelContext, reads, limit, iter === MAX_ITER), iter === MAX_ITER);
        if (decision.action === 'report_analysis') {
          const candidate = { name: failure.name, ...decision, fix_applied: false, status: 'HYPOTHESIS' };
          const verification = verifier.check('analyze', candidate, { failure, sourceReads: [...reads.values()] });
          analysis = { ...candidate, verification };
          console.log(`  Hypothèse non vérifiée: ${decision.root_cause.slice(0, 160)}`);
          break;
        }
        const key = JSON.stringify([decision.file_path, decision.line_start || 1, decision.line_end || null]);
        if (!reads.has(key)) reads.set(key, executeTool('read_file', decision));
        else reads.set(key, reads.get(key) + '\nAlready read: request another range or conclude.');
        console.log(`  Read: ${decision.file_path}`);
      } catch (e) {
        span.error = e.message;
        providerUnavailable = require('./shared/provider-errors').unavailable(e);
        console.error(`  ${R}  ✗ Erreur itération ${iter}: ${e.message}${E}`);
        break;
      }
    }

    span.end(!!analysis);
    if (!analysis) process.exitCode = 1;
    if (analysis) {
      analyses.push(analysis);
      memory.recordEpisode('bug-agent', [{ tc: failure.name, fix_applied: analysis.fix_applied, confidence: analysis.confidence }],
        `Bug analysis: ${analysis.root_cause?.slice(0,80)||''}`, 'analyze');
    }
    if (iter >= MAX_ITER && !analysis) {
      console.log(`  ${Y}⚠  Max itérations atteint sans conclusion${E}`);
    }
    if (!analysis) analyses.push({ name: failure.name, status: 'NOT_EVALUATED', fix_applied: false, root_cause: '', error: span.error || 'Iteration budget exhausted without a conclusion' });
    if (!DRY_RUN) {
      const report = JSON.stringify({ ts: new Date().toISOString(), resultsDir: RESULTS_DIR, analyses }, null, 2);
      fs.writeFileSync(path.join(DOCS_DIR, 'bug-analysis.json'), report);
      fs.writeFileSync(path.join(RESULTS_DIR, 'bug-analysis.json'), report);
    }
    console.log();
  }

  if (!DRY_RUN) {
    const report = JSON.stringify({ ts: new Date().toISOString(), resultsDir: RESULTS_DIR, analyses }, null, 2);
    fs.writeFileSync(path.join(DOCS_DIR, 'bug-analysis.json'), report);
    fs.writeFileSync(path.join(RESULTS_DIR, 'bug-analysis.json'), report);
  }
  return analyses;
}

// ── REPAIR — Mode réparation avec vérification ────────────────────────────────
async function cmdRepair() {
  console.log(`\n${B}=== BUG AGENT — REPAIR [max-iter=${MAX_ITER}] ===${E}`);
  console.log(`  ${Y}Mode repair : propositions de correctifs soumises à revue, sources inchangées${E}\n`);

  const failures = loadFailures();
  if (!failures.length) { console.log(`  ${G}✓ Aucun échec à réparer${E}`); return; }

  let repaired = 0, failed = 0;

  for (const failure of failures.slice(0, 5)) { // Limiter à 5 bugs par session
    console.log(`  ${B}[REPAIR] ${failure.name.slice(0,55)}${E}`);

    const _repairTpl = promptStore.get('repair_patch') ||
      'Tu es un expert Playwright TypeScript. Répare ce test en échec.\n\n' +
      'Test    : {test_name}\nErreur  : {error_message}\nTrace   : {stack_trace}\n\n' +
      'IMPORTANT :\n' +
      '1. Lis d\'abord le fichier de steps correspondant (src/steps/)\n' +
      '2. Identifie la ligne problématique\n' +
      '3. Propose le correctif minimal avec apply_fix; il sera soumis à revue, jamais appliqué automatiquement\n' +
      '4. Utilise report_analysis pour terminer\n\n' +
      'Sois conservateur : ne modifie que ce qui est nécessaire pour corriger l\'erreur.';
    const prompt = fmt(_repairTpl, {
      test_name: failure.name, tc: 'N/A',
      error_message: failure.message, stack_trace: failure.trace,
      source_context: 'Utilisez les outils read_file pour lire les fichiers sources.',
    });

    const messages = require('./shared/skill-store').messages('proposition-correction', prompt);
    const span     = new tracer.Span('bugRepair', prompt, llm.MODEL).begin();
    let fixed      = false;
    let repairError = false;

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
          messages.push({ role: 'tool', content: result, tool_call_id: tc.id });
        }
      } catch (e) {
        span.error = e.message;
        repairError = true;
        if (require('./shared/provider-errors').unavailable(e)) {
          console.error('Provider unavailable or rate limited: remaining repairs not evaluated.');
          span.end(false);
          process.exitCode = 1;
          return;
        }
        console.error(`  ${R}  ✗ Erreur itération ${i + 1}: ${e.message}${E}`);
        break;
      }
    }

    let verification;
    try { verification = verifier.check('repair', { applied: fixed, error: repairError }, { failure }); }
    catch (error) { verification = error.verification; repairError = true; }
    span.end(verification?.status === 'VALIDATED');
    promptStore.recordUsage('repair_patch');
    if (verification?.status === 'VALIDATED' && !repairError) { repaired++; console.log(`  ${G}✓ Réparé${E}\n`); }
    else { failed++; console.log(fixed ? 'Correctif appliqué mais NON VÉRIFIÉ : aucune réussite de réparation déclarée.' : 'Non réparé'); }
  }

  console.log(`  ${B}Bilan repair :${E} ${G}${repaired} réparés${E}  ${Y}${failed} non réparés${E}`);
  if (failed) process.exitCode = 1;
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
<h1>🐛 Bug Report — Playwright BDD</h1>
<p style="color:#64748b">Généré le ${new Date().toLocaleString('fr-FR')} | max-iter=${MAX_ITER}</p>
<div class="card">
  <p><strong style="color:#f87171">${analyses.length}/${failures.length}</strong> échec(s) analysés |
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

${Y}⚠  repair modifie les fichiers TypeScript — vérifier avec git diff avant de committer${E}
`);
  }
}

if (require.main === module) main().catch(e => { console.error(R + e.message + E); process.exitCode = 1; });
module.exports = { executeTool, cmdAnalyze, cmdRepair, loadFailures };
