'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { createHash } = require('node:crypto');
const { execFile } = require('node:child_process');

const sourceRules = () => require('./skill-store').instructions('audit-sources');
const SOURCE_SCHEMA = `Réponds uniquement en JSON : {"status":"COMPLETE ou INCOMPLETE","findings":[{"file":"chemin du manifeste","line":1,"quote":"extrait exact","severity":"warning ou error","message":"défaut et impact"}],"suggestions":["conseil facultatif"],"limitations":["limite éventuelle"]}.`;

function walkSources(root, directory = 'src') {
  const files = [], errors = [];
  function walk(relative) {
    let entries;
    try { entries = fs.readdirSync(path.join(root, relative), { withFileTypes: true }); }
    catch { errors.push({ file: relative, reason: 'Dossier absent ou illisible.' }); return; }
    for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
      const file = `${relative}/${entry.name}`;
      if (entry.isDirectory() && !/^(?:fixtures|credentials|sessions|\.auth)$/i.test(entry.name)) walk(file);
      else if (entry.isFile() && /\.(ts|feature)$/.test(file)) {
        try {
          const content = fs.readFileSync(path.join(root, file), 'utf8');
          files.push({ file, content, characters: content.length,
            lines: content.split(/\r?\n/).length,
            sha256: createHash('sha256').update(content).digest('hex') });
        } catch { errors.push({ file, reason: 'Fichier illisible.' }); }
      }
    }
  }
  walk(directory);
  return { files, errors };
}

function sourcePrompt(files, manifest, localChecks) {
  return `${sourceRules()}\n${SOURCE_SCHEMA}\n\nContrôles locaux :\n${JSON.stringify(localChecks)}\n\nManifeste (chemins seulement, pas le contenu des autres lots) :\n${JSON.stringify(manifest)}\n\nFichiers complets de ce lot :\n${JSON.stringify(files.map(({ file, content }) => ({ file, content })))}`;
}

function buildSourceBatches(files, localChecks, maxChars = 24000) {
  if (!Number.isSafeInteger(maxChars) || maxChars < 4000) throw new Error('VERIFY_MAX_PROMPT_CHARS doit être un entier >= 4000.');
  const manifest = files.map(f => f.file);
  // Repeat lifecycle code so a feature/step is never judged without its teardown context.
  const shared = files.filter(f => /^src\/(hooks|core)\//.test(f.file));
  const remaining = files.filter(f => !shared.includes(f));
  const batches = [], omitted = [];
  let current = [...shared];
  const flush = () => {
    if (current.length > shared.length) batches.push({ files: current, prompt: sourcePrompt(current, manifest, localChecks) });
    current = [...shared];
  };
  for (const file of remaining) {
    if (sourcePrompt([...current, file], manifest, localChecks).length > maxChars) flush();
    if (sourcePrompt([...current, file], manifest, localChecks).length > maxChars) {
      omitted.push({ file: file.file, reason: 'Fichier complet et contexte dépassant VERIFY_MAX_PROMPT_CHARS ; aucun extrait envoyé.' });
    } else current.push(file);
  }
  flush();
  if (!batches.length && shared.length && sourcePrompt(shared, manifest, localChecks).length <= maxChars) {
    batches.push({ files: shared, prompt: sourcePrompt(shared, manifest, localChecks) });
  }
  if (!batches.length) {
    for (const file of shared) omitted.push({ file: file.file, reason: 'Contexte complet trop volumineux.' });
  }
  return { batches, omitted };
}

function isUnavailable(value) {
  return typeof value === 'string' && /service\s+LLM[^\n]{0,80}(indisponible|hors ligne)/i.test(value);
}

function validateReview(raw, files, localChecks = {}) {
  if (isUnavailable(raw)) return { status: 'UNAVAILABLE', reason: 'Service LLM indisponible ; aucun verdict qualité.' };
  let data;
  try { data = JSON.parse(raw.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '')); }
  catch { return { status: 'INCOMPLETE', reason: 'Réponse LLM non JSON ou tronquée.' }; }
  if (!data || !['COMPLETE', 'INCOMPLETE'].includes(data.status) || !Array.isArray(data.findings)
      || !Array.isArray(data.suggestions) || !Array.isArray(data.limitations)
      || ![...data.suggestions, ...data.limitations].every(item => typeof item === 'string')) {
    return { status: 'INCOMPLETE', reason: 'Réponse LLM non conforme au format d’audit.' };
  }
  const findings = [], rejectedFindings = [], dismissedFindings = [];
  for (const original of data.findings) {
    let finding = original;
    const source = files.find(f => f.file === finding?.file);
    // trim() also removes U+FEFF: preserve the actual BOM when checking a quote.
    const quote = typeof finding?.quote === 'string' ? finding.quote.replace(/\r\n/g, '\n').replace(/^[\t ]+|[\t \n]+$/g, '') : '';
    const lines = source?.content.replace(/\r\n/g, '\n').split('\n');
    // Correct a miscounted line only if the full quote has exactly one occurrence.
    if (source && quote && Number.isInteger(finding.line)) {
      const text = lines.join('\n');
      const offset = text.indexOf(quote);
      if (offset >= 0 && text.indexOf(quote, offset + 1) < 0
          && /^[\t ]*$/.test(text.slice(text.lastIndexOf('\n', offset - 1) + 1, offset))) {
        const actualLine = text.slice(0, offset).split('\n').length;
        if (actualLine !== finding.line) finding = { ...finding, reportedLine: finding.line, line: actualLine };
      }
    }
    const valid = source && Number.isInteger(finding.line) && finding.line > 0 && finding.line <= lines.length
      && quote && lines.slice(finding.line - 1).join('\n').replace(/^[\t ]*/, '').startsWith(quote)
      && ['warning', 'error'].includes(finding.severity) && typeof finding.message === 'string' && finding.message.trim();
    if (source && !source.content.trim() && !quote && localChecks.typescript?.status === 'PASS') {
      dismissedFindings.push({ ...finding, reason: 'Un fichier vide seul ne démontre aucun défaut ; aucun usage défaillant cité.' });
    } else if (valid && source.content.charCodeAt(0) === 0xFEFF && finding.line === 1
        && /\bBOM\b|U\+FEFF/i.test(finding.message) && localChecks.typescript?.status === 'PASS') {
      dismissedFindings.push({ ...finding, reason: 'BOM UTF-8 accepté par le compilateur ; conseil de présentation.' });
    } else if (valid && localChecks.typescript?.status === 'PASS'
        && (localChecks.typescript.synchronousCalls || []).some(call => call.file === finding.file && call.line === finding.line && call.quote === quote)
        && /await|asynchrone|asynchronous|promesse flottante|floating promise/i.test(finding.message)) {
      dismissedFindings.push({ ...finding, reason: 'TypeScript confirme un retour void pour cet appel ; aucun await requis sur sa valeur de retour.' });
    } else if (valid) findings.push(finding);
    else rejectedFindings.push(finding);
  }
  return {
    status: data.status,
    reviewStatus: rejectedFindings.length ? 'NEEDS_REVIEW' : 'COMPLETE',
    findings, rejectedFindings, dismissedFindings,
    suggestions: [...data.suggestions, ...dismissedFindings.map(f => `${f.file} : ${f.reason}`)], limitations: data.limitations,
    ...(rejectedFindings.length ? { reason: 'Constats sans référence source vérifiable ; revue nécessaire.' } : {}),
  };
}

function runLocalChecks(root) {
  return new Promise(resolve => {
    execFile(process.execPath, [path.join(__dirname, 'verify-local.js')], {
      cwd: root, timeout: 120000, maxBuffer: 2 * 1024 * 1024, windowsHide: true,
    }, (error, stdout) => {
      const line = stdout?.split(/\r?\n/).find(line => line.startsWith('QA_VERIFY_RESULT='));
      try { if (!error && line) return resolve(JSON.parse(line.slice('QA_VERIFY_RESULT='.length))); } catch {}
      const reason = error?.killed ? 'Délai des contrôles locaux dépassé.' : 'Contrôles locaux indisponibles (processus Node ou dépendances).';
      resolve({ typescript: { status: 'NOT_EVALUATED', reason }, cucumber: { status: 'NOT_EVALUATED', reason } });
    });
  });
}

async function verifySources(root, llm, { localOnly = false, maxChars = 24000, onProgress = () => {}, localChecks, retryDelayMs = 45000, cacheDir } = {}) {
  const { files, errors } = walkSources(root);
  onProgress('Contrôles locaux TypeScript et Cucumber, sans exécution UI…');
  const local = localChecks || await runLocalChecks(root);
  onProgress(`Contrôles locaux : TypeScript ${local.typescript.status} ; Cucumber ${local.cucumber.status}.`);
  // The full diagnostics remain in the report. Prompts need the established facts and scope only.
  const facts = Object.fromEntries(Object.entries(local).map(([name, check]) => [name, {
    status: check.status, scope: check.scope, scenarios: check.scenarios, steps: check.steps,
    diagnosticCount: check.diagnostics?.length,
    synchronousCalls: check.synchronousCalls,
  }]));
  const { batches, omitted } = buildSourceBatches(files, facts, maxChars - 100);
  const reviews = [], reviewed = new Set(), findings = new Map();
  if (!localOnly) {
    for (const [index, batch] of batches.entries()) {
      onProgress(`Sources : lot ${index + 1}/${batches.length}, ${batch.files.length} fichiers complets, ${batch.prompt.length} caractères.`);
      let review;
      let attempts = 0;
      let cached = false;
      const key = createHash('sha256').update(JSON.stringify(['source-review-v1', llm.MODEL, batch.prompt])).digest('hex');
      const cacheFile = cacheDir && path.join(cacheDir, key + '.json');
      if (cacheFile) {
        try {
          const entry = JSON.parse(fs.readFileSync(cacheFile, 'utf8'));
          if (entry.key === key && Date.now() - entry.savedAt < 86400000) {
            const candidate = validateReview(entry.raw, batch.files, local);
            if (candidate.status === 'COMPLETE' && candidate.reviewStatus === 'COMPLETE') { review = candidate; cached = true; }
          }
        } catch { /* Cache missing or invalid: perform a fresh review. */ }
      }
      if (cached) onProgress(`Lot ${index + 1} repris du cache validé (sources, contexte et modèle identiques).`);
      while (!cached && attempts < 2) {
        attempts++;
        try {
          const prompt = (attempts > 1 ? 'Retry: return complete valid JSON, concise findings, all required lists.\n' : '') + batch.prompt;
          const response = await llm.chat([{ role: 'user', content: prompt }], { temperature: 0, _fnName: 'verifySources' });
          review = validateReview(response?.message?.content || '', batch.files, local);
          if (cacheFile && review.status === 'COMPLETE' && review.reviewStatus === 'COMPLETE') {
            try {
              fs.mkdirSync(cacheDir, { recursive: true });
              fs.writeFileSync(cacheFile, JSON.stringify({ key, savedAt: Date.now(), raw: response.message.content }));
            } catch { onProgress('Cache non enregistrable ; verdict courant conservé.'); }
          }
        } catch {
          review = { status: 'UNAVAILABLE', reason: 'Appel LLM impossible ; aucun verdict qualité.' };
        }
        if (!['UNAVAILABLE', 'INCOMPLETE'].includes(review.status) || attempts === 2) break;
        const delay = review.status === 'UNAVAILABLE' ? retryDelayMs : 0;
        onProgress(`Lot ${index + 1} ${review.status} ; une reprise dans ${delay / 1000} s.`);
        if (delay) await new Promise(resolve => setTimeout(resolve, delay));
      }
      reviews.push({ batch: index + 1, attempts, cached, files: batch.files.map(f => f.file), ...review });
      if (review.status === 'COMPLETE') batch.files.forEach(f => reviewed.add(f.file));
      for (const finding of review.findings || []) findings.set(JSON.stringify(finding), finding);
      // Avoid multiplying provider calls when the service cannot answer.
      if (review.status === 'UNAVAILABLE') break;
    }
  }
  const unresolved = reviews.flatMap(r => r.rejectedFindings || []);
  const evidence = {
    scope: 'Sources .feature et .ts complètes de src/, y compris hooks, World, pages et helpers. Les contenus ne sont jamais tronqués.',
    files: files.map(({ content, ...metadata }) => metadata), errors, omitted,
    totalFiles: files.length, reviewedFiles: reviewed.size,
    unreviewedFiles: files.filter(f => !reviewed.has(f.file)).map(f => f.file),
    plannedBatches: batches.length, completedBatches: reviews.filter(r => r.status === 'COMPLETE').length,
    maxPromptCharacters: maxChars, localChecks: local, reviews,
    unresolvedFindings: unresolved,
  };
  return [
    { name: 'Features Gherkin', select: f => f.file.startsWith('src/features/') && f.file.endsWith('.feature'), checks: [local.cucumber] },
    { name: 'Step Definitions', select: f => !f.file.endsWith('.feature'), checks: [local.typescript, local.cucumber] },
  ].map(category => {
    const categoryFiles = files.filter(category.select);
    const targetFiles = category.name === 'Step Definitions' ? categoryFiles.filter(f => f.file.startsWith('src/steps/')) : categoryFiles;
    const requiredFiles = files.filter(f => category.select(f) || /^src\/(hooks|core)\//.test(f.file));
    const knownFiles = new Set(files.map(f => f.file));
    const pending = unresolved.filter(f => !knownFiles.has(f?.file) || category.select(f));
    const complete = !localOnly && requiredFiles.length > 0 && requiredFiles.every(f => reviewed.has(f.file))
      && !errors.some(e => e.file === 'src' || (category.name === 'Features Gherkin'
        ? /^src\/(features|hooks|core)(\/|$)/.test(e.file) : !/^src\/features(\/|$)/.test(e.file)));
    const relevant = [...findings.values()].filter(category.select);
    const localFailure = category.checks.some(c => c.status === 'FAIL');
    const localComplete = category.checks.every(c => c.status === 'PASS');
    const analysisStatus = localOnly ? 'SKIPPED' : !complete && reviews.some(r => r.status === 'UNAVAILABLE') ? 'UNAVAILABLE'
      : !complete ? 'INCOMPLETE' : pending.length ? 'NEEDS_REVIEW' : 'COMPLETE';
    const verdict = localFailure ? 'INVALID' : !complete || !localComplete || !targetFiles.length || pending.length ? 'NOT_EVALUATED'
      : relevant.some(f => f.severity === 'error') ? 'INVALID' : relevant.length ? 'WARNING' : 'VALID';
    const reasoning = localFailure ? 'Un contrôle local a confirmé un défaut ; consulter evidence.localChecks.'
      : !targetFiles.length ? 'Aucun fichier cible à vérifier.'
      : localOnly ? 'Contrôles locaux terminés ; audit LLM non demandé (--local-only).'
      : !complete || !localComplete ? `Audit incomplet : ${reviewed.size}/${files.length} sources analysées ; consulter les limites et contrôles locaux.`
      : pending.length ? `${reviewed.size}/${files.length} sources analysées ; ${pending.length} constat(s) sans référence vérifiable nécessitent une revue.`
      : relevant.length ? relevant.map(f => `${f.file}:${f.line} : ${f.message}`).join('\n')
      : 'Contrôles locaux réussis et sources complètes analysées ; aucun défaut concret signalé dans ce périmètre.';
    return { check: category.name, verdict, analysisStatus, targetFiles: targetFiles.length, reasoning, detail: reasoning, findings: relevant,
      coverage: { totalFiles: requiredFiles.length, reviewedFiles: requiredFiles.filter(f => reviewed.has(f.file)).length }, evidence };
  });
}

module.exports = { walkSources, buildSourceBatches, validateReview, verifySources, runLocalChecks, isUnavailable };
