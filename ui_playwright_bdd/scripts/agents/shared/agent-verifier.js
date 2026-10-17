'use strict';

// No model judges another model here. PASS checks have an explicit, limited scope.
const fs = require('node:fs');
const path = require('node:path');
const { createHash, randomUUID } = require('node:crypto');
const { validateGenerated } = require('./generated-code');
const text = value => typeof value === 'string' && value.trim().length > 0;
const strings = value => Array.isArray(value) && value.every(text);
const range = (value, max = 1) => Number.isFinite(value) && value >= 0 && value <= max;
const hash = value => createHash('sha256').update(JSON.stringify(value) ?? 'undefined').digest('hex');
const AGENTS = ['codegen', 'quality', 'bug', 'advisor', 'planning', 'reporting', 'ci', 'runner'];

function compileCandidate(root, file, content) {
  const ts = require('typescript');
  const configFile = ts.findConfigFile(root, ts.sys.fileExists);
  if (!configFile) return null;
  const config = ts.readConfigFile(configFile, ts.sys.readFile);
  const parsed = ts.parseJsonConfigFileContent(config.config || {}, ts.sys, path.dirname(configFile), { noEmit: true }, configFile);
  const candidate = path.resolve(root, file);
  const relative = path.relative(root, candidate);
  if (relative.startsWith('..') || path.isAbsolute(relative) || !candidate.endsWith('.ts')) throw new Error('Candidate must be a project TypeScript file');
  const same = name => path.resolve(name).toLowerCase() === candidate.toLowerCase();
  const host = ts.createCompilerHost(parsed.options);
  const read = host.readFile.bind(host), exists = host.fileExists.bind(host);
  host.readFile = name => same(name) ? content : read(name);
  host.fileExists = name => same(name) || exists(name);
  const program = ts.createProgram([...new Set([...parsed.fileNames, candidate])], parsed.options, host);
  return [...(config.error ? [config.error] : []), ...parsed.errors, ...ts.getPreEmitDiagnostics(program)].map(d => ({
    code: d.code, file: d.file ? path.relative(root, d.file.fileName) : null,
    line: d.file && d.start != null ? d.file.getLineAndCharacterOfPosition(d.start).line + 1 : null,
  }));
}

function verify({ agent, operation, output, context = {}, root }) {
  const checks = [];
  const add = (name, ok, detail) => checks.push({ name, status: ok ? 'PASS' : 'FAIL', detail });
  let supported = true;
  let limitations;
  const raw = typeof output === 'string' ? output : JSON.stringify(output);
  add('available', !!raw && raw !== '{}' && raw !== 'null' && !/service\s+LLM[^\n]*(indisponible|hors ligne)/i.test(raw), 'Réponse exploitable, hors message de secours du fournisseur.');
  if ((agent === 'codegen' && ['gherkin', 'typescript'].includes(operation)) || (agent === 'planning' && operation === 'suggest')) {
    try {
      const source = agent === 'planning' ? `Feature: Suggested coverage\n${output}` : output;
      validateGenerated(source, operation === 'typescript' ? 'typescript' : 'gherkin');
      add('syntax', true, 'Parsing uniquement ; compilation complète et exécution non effectuées ici.');
    } catch (error) { add('syntax', false, error.message); }
    limitations = ['Code candidat : compilation du projet, exécution et conformité aux exigences restent à vérifier.'];
    if (operation === 'typescript' && root && context.filePath && checks.every(c => c.status === 'PASS')) {
      try {
        const diagnostics = compileCandidate(root, context.filePath, output);
        if (diagnostics) {
          add('typescript-project', diagnostics.length === 0, { diagnostics, scope: 'Compilation complète avec candidat en mémoire, sans écriture ni exécution.' });
          limitations = ['Compilation contrôlée ; exécution et conformité aux exigences non démontrées.'];
        }
      } catch (error) { add('typescript-project', false, error.message); }
    }
  } else if (agent === 'quality' && operation === 'triage') {
    add('schema', ['real_bug', 'flaky', 'env_issue', 'false_positive'].includes(output?.result) && range(output?.confidence) && text(output?.reasoning), 'Catégorie, justification et confiance dans [0,1].');
    limitations = ['La confiance déclarée et un second avis LLM ne démontrent pas la classification.'];
  } else if (agent === 'quality' && operation === 'rca') {
    add('schema', text(output?.root_cause) && text(output?.fix_action)
      && ['assertion', 'auth', 'data', 'network', 'config', 'selector', 'logic', 'unknown'].includes(output?.cause_category)
      && ['ui', 'api', 'database', 'network', 'config', 'test'].includes(output?.affected_layer)
      && ['immediate', 'high', 'medium', 'low'].includes(output?.fix_priority) && strings(output?.related_tests), 'Champs et catégories RCA.');
    limitations = ['Cause proposée non reproduite : hypothèse, pas fait établi.'];
  } else if (agent === 'bug' && operation === 'analyze') {
    add('schema', text(output?.root_cause) && text(output?.fix_summary) && range(output?.confidence), 'Conclusion, proposition et confiance dans [0,1].');
    add('honest-action', output?.fix_applied === false, 'Une analyse ne peut pas déclarer un correctif appliqué.');
    limitations = ['Lire les sources ne démontre pas une causalité ; reproduction nécessaire.'];
  } else if (agent === 'bug' && operation === 'repair') {
    add('patch-applied', output?.applied === true && output?.error === false, 'Modification effective sans erreur de la boucle de réparation.');
    limitations = ['Correctif non validé : exiger échec avant, réussite après, assertions préservées et régression.'];
  } else if (agent === 'advisor' && operation === 'predict') {
    add('schema', output?.tc === context.tc && range(output?.failure_risk)
      && ['stable', 'degrading', 'improving'].includes(output?.trend)
      && text(output?.predicted_cause) && text(output?.recommendation), 'Identité du test et schéma de prédiction.');
    limitations = ['Prédiction non vérifiable avant observation ; probabilité non calibrée.'];
  } else if (agent === 'advisor' && ['advise', 'gate'].includes(operation)) {
    const positive = operation === 'advise' ? 'GO' : 'PASS';
    add('schema', [positive, operation === 'advise' ? 'NO-GO' : 'FAIL'].includes(output?.verdict)
      && strings(output?.blockers) && (operation === 'advise'
        ? ['low', 'medium', 'high', 'critical'].includes(output?.risk) && strings(output?.warnings) && text(output?.reasoning)
        : Number.isInteger(output?.score) && range(output?.score, 100) && text(output?.improvement)), 'Schéma de décision complet.');
    if (output?.verdict === positive) {
      add('execution', context.run?.allowed === true, 'Exécution complète, identifiée et entièrement réussie.');
      add('no-blockers', Array.isArray(output?.blockers) && output.blockers.length === 0, 'Aucun bloquant déclaré pour une décision positive.');
    }
    limitations = ['Les résultats de tests ne démontrent pas à eux seuls une aptitude à la production. Décision IA consultative.'];
  } else if (agent === 'ci' && operation === 'pr') {
    add('schema', text(output?.title) && output.title.length <= 70 && text(output?.body), 'Titre et description non vides.');
    limitations = ['Description non confrontée à une revue du diff et aux preuves des tests ; publication automatique bloquée.'];
  } else if ((agent === 'ci' && ['release', 'commit'].includes(operation))
    || (agent === 'runner' && ['summary', 'flaky'].includes(operation))
    || (agent === 'quality' && operation === 'adversarial')
    || (agent === 'reporting' && operation === 'notify')) {
    add('text', text(output), 'Texte non vide.');
    if (operation === 'commit') add('commit-format', /^[a-z]+(?:\([^\r\n]+\))?!?: [^\r\n]+$/.test(output) && output.length <= 72, 'Message de commit sur une ligne, au plus 72 caractères.');
    limitations = ['Texte libre : fidélité factuelle non démontrée. Ne pas publier comme résultat vérifié.'];
  } else if (['reporting', 'runner'].includes(agent) && operation === 'factual-summary') {
    add('source-counts', Number.isSafeInteger(context.total) && context.total > 0 && Number.isSafeInteger(context.passed)
      && context.passed >= 0 && context.passed <= context.total, 'Comptages fournis par le code, pas par le modèle.');
    add('exact-summary', output === factualSummary(context), 'Égalité exacte avec le résumé déterministe.');
    limitations = [];
  } else { supported = false; limitations = ['Aucune règle enregistrée pour cette opération.']; }
  const status = checks.some(c => c.status === 'FAIL') ? 'REJECTED'
    : supported && !limitations.length ? 'VALIDATED' : 'UNVERIFIED';
  return { schemaVersion: 1, agent, operation, status, scope: operation === 'factual-summary' ? 'Résumé des comptages fournis uniquement' : 'Contrôles de structure et de cohérence ; aucune preuve de vérité métier',
    outputHash: hash(output), contextHash: hash(context), checks, limitations };
}

function factualSummary({ passed, total }) { return `Run : ${passed}/${total} tests passés.`; }

function createVerifier({ agent, root, runtimeProcess = process, logger = console }) {
  if (!AGENTS.includes(agent)) throw new Error(`Unknown verified agent: ${agent}`);
  const invocationId = randomUUID();
  const auditFile = runtimeProcess.env.QA_VERIFICATION_FILE || path.join(root, 'logs', 'agent-verification', `${agent}-${invocationId}.jsonl`);
  function check(operation, output, context = {}) {
    const result = { ...verify({ agent, operation, output, context, root }), invocationId,
      runId: runtimeProcess.env.QA_RUN_ID || null, timestamp: new Date().toISOString() };
    // Store fingerprints, never model text, source contents or credentials in the audit log.
    if (!runtimeProcess.argv.includes('--dry-run')) {
      fs.mkdirSync(path.dirname(auditFile), { recursive: true });
      fs.appendFileSync(auditFile, JSON.stringify(result) + '\n', 'utf8');
    }
    logger.log(`[VERIFY] ${agent}/${operation}: ${result.status} — ${result.limitations.join(' ') || result.scope}`);
    if (result.status === 'REJECTED') {
      runtimeProcess.exitCode = 1;
      const error = new Error(`Verification rejected ${agent}/${operation}: ${result.checks.filter(c => c.status === 'FAIL').map(c => c.name + (c.name === 'syntax' ? ' — ' + c.detail : '')).join(', ')}`);
      error.verification = result;
      throw error;
    }
    return result;
  }
  function requireValidated(result) {
    if (result.status !== 'VALIDATED') {
      runtimeProcess.exitCode = 1;
      const error = new Error(`${agent}/${result.operation}: ${result.status}; action bloquée, preuves indépendantes requises.`);
      error.verification = result;
      throw error;
    }
  }
  function failure(error) {
    runtimeProcess.exitCode = 1;
    if (error?.verification) return error.verification;
    try { return check('unavailable', null); }
    catch (rejected) {
      if (rejected.verification) return rejected.verification;
      throw rejected; // A broken audit sink must not silently authorize a result.
    }
  }
  return { check, requireValidated, failure };
}

function readVerification(file) {
  if (!fs.existsSync(file)) return { status: 'NOT_APPLICABLE', records: [] };
  try {
    const records = fs.readFileSync(file, 'utf8').split(/\r?\n/).filter(Boolean).map(line => JSON.parse(line));
    if (!records.length || records.some(r => r.schemaVersion !== 1 || !['VALIDATED', 'REJECTED', 'UNVERIFIED'].includes(r.status))) throw new Error('Invalid verification journal');
    return { status: records.some(r => r.status === 'REJECTED') ? 'REJECTED' : records.some(r => r.status === 'UNVERIFIED') ? 'UNVERIFIED' : 'VALIDATED', records };
  } catch (error) { return { status: 'REJECTED', records: [], error: error.message }; }
}

module.exports = { verify, createVerifier, factualSummary, readVerification };
