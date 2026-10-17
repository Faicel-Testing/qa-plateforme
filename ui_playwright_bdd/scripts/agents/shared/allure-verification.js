'use strict';

// Deterministic checks based on the installed allure-js-commons model and:
// https://allurereport.org/docs/how-it-works-test-result-file/
// Scope: known field types, enums, timestamps, nested structures and root UUIDs.
// Optional/empty fields are accepted. This is not a renderer/attachment-file check.
const STATUSES = new Set(['passed', 'failed', 'broken', 'skipped', 'unknown']);
const STAGES = new Set(['scheduled', 'running', 'finished', 'pending', 'interrupted']);
const isObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);

function validateResult(result, file, errors) {
  const fail = (field, reason) => errors.push({ file, kind: 'invalid_structure', field, reason: `${field} : ${reason}` });
  const type = (object, key, expected, prefix, required = false) => {
    if (!Object.hasOwn(object, key) && !required) return;
    const valid = expected === 'array' ? Array.isArray(object[key]) : expected === 'object' ? isObject(object[key]) : typeof object[key] === expected;
    if (!valid) fail(`${prefix}.${key}`, `type ${expected} attendu${required ? ' (champ requis)' : ''}.`);
  };
  const strings = (object, keys, prefix) => keys.forEach(key => type(object, key, 'string', prefix));
  if (typeof result.uuid !== 'string' || !result.uuid.trim()) fail('$.uuid', 'identifiant non vide requis.');
  strings(result, ['historyId', 'testCaseId', 'fullName'], '$');
  type(result, 'titlePath', 'array', '$');
  if (Array.isArray(result.titlePath) && !result.titlePath.every(value => typeof value === 'string')) {
    fail('$.titlePath', 'tableau de chaînes attendu.');
  }

  const work = [{ item: result, prefix: '$' }];
  while (work.length) {
    const { item, prefix } = work.pop();
    strings(item, ['name', 'description', 'descriptionHtml', 'uuid'], prefix);
    if (Object.hasOwn(item, 'status') && !STATUSES.has(item.status)) fail(`${prefix}.status`, 'statut Allure inconnu.');
    if (Object.hasOwn(item, 'stage') && !STAGES.has(item.stage)) fail(`${prefix}.stage`, 'stage Allure inconnu.');
    for (const key of ['start', 'stop']) {
      if (Object.hasOwn(item, key) && !Number.isFinite(item[key])) fail(`${prefix}.${key}`, 'timestamp numérique fini attendu.');
    }
    if (Number.isFinite(item.start) && Number.isFinite(item.stop) && item.stop < item.start) {
      fail(`${prefix}.stop`, 'stop précède start.');
    }
    type(item, 'statusDetails', 'object', prefix);
    if (isObject(item.statusDetails)) {
      strings(item.statusDetails, ['message', 'trace', 'actual', 'expected'], `${prefix}.statusDetails`);
      for (const key of ['known', 'muted', 'flaky']) type(item.statusDetails, key, 'boolean', `${prefix}.statusDetails`);
    }
    for (const key of ['steps', 'attachments', 'parameters', 'labels', 'links']) {
      type(item, key, 'array', prefix);
      if (!Array.isArray(item[key])) continue;
      for (const [index, child] of item[key].entries()) {
        const childPath = `${prefix}.${key}[${index}]`;
        if (!isObject(child)) { fail(childPath, 'objet attendu.'); continue; }
        if (key === 'steps') work.push({ item: child, prefix: childPath });
        if (key === 'labels' || key === 'parameters') {
          type(child, 'name', 'string', childPath, true);
          type(child, 'value', 'string', childPath, true);
        }
        if (key === 'parameters') {
          type(child, 'excluded', 'boolean', childPath);
          if (Object.hasOwn(child, 'mode') && !['default', 'masked', 'hidden'].includes(child.mode)) fail(`${childPath}.mode`, 'mode inconnu.');
        }
        if (key === 'attachments') {
          type(child, 'name', 'string', childPath, true);
          type(child, 'source', 'string', childPath, true);
          type(child, 'type', 'string', childPath);
          if (Object.hasOwn(child, 'size') && (!Number.isFinite(child.size) || child.size < 0)) fail(`${childPath}.size`, 'taille positive ou nulle attendue.');
        }
        if (key === 'links') {
          type(child, 'url', 'string', childPath, true);
          strings(child, ['name', 'type'], childPath);
        }
      }
    }
  }
}
function fieldInfo(result, key) {
  if (!Object.hasOwn(result, key)) return { present: false };
  const value = result[key];
  const type = value === null ? 'null' : Array.isArray(value) ? 'array' : typeof value;
  const info = { present: true, type };
  if (Array.isArray(value)) info.count = value.length;
  else if (typeof value === 'string') info.length = value.length;
  else if (type === 'object') info.presentFields = Object.keys(value);
  return info;
}

function summarizeResult(file, result) {
  const values = {};
  for (const key of ['uuid', 'name', 'fullName', 'historyId', 'testCaseId', 'status', 'stage', 'start', 'stop']) {
    if (Object.hasOwn(result, key)) values[key] = result[key];
  }
  const fields = {};
  for (const key of ['steps', 'attachments', 'labels', 'links', 'parameters', 'description', 'statusDetails']) {
    fields[key] = fieldInfo(result, key);
  }
  if (result.statusDetails && typeof result.statusDetails === 'object') {
    fields.statusDetails.message = fieldInfo(result.statusDetails, 'message');
    fields.statusDetails.trace = fieldInfo(result.statusDetails, 'trace');
  }
  return { file, jsonValid: true, presentFields: Object.keys(result), values, fields };
}

function buildAllureSummary(files, readFile) {
  const summary = {
    totalFiles: files.length,
    parsedJsonFiles: 0,
    resultObjects: 0,
    checkedResultFiles: 0,
    statusCounts: {},
    fieldPresenceCounts: {},
    errors: [],
    samples: [],
    sampleLimit: 3,
    scope: 'Tous les JSON complets : syntaxe, objet racine, UUID uniques, types des champs connus, enums, timestamps et structures imbriquées. Les champs optionnels et tableaux vides sont acceptés. Pas de contrôle du rendu ni des fichiers de pièces jointes.',
    omittedDetails: 'Les contenus des steps, attachments, labels, links et parameters, les descriptions et les textes message/trace sont omis. Leur présence, type et taille sont calculés sur les fichiers complets.',
  };
  const statuses = new Map();
  const presence = new Map();
  const uuids = new Map();
  for (const file of files) {
    let content;
    try { content = readFile(file); }
    catch {
      summary.errors.push({ file, kind: 'read_error', reason: 'Fichier illisible : syntaxe JSON non vérifiée.' });
      continue;
    }
    let result;
    try { result = JSON.parse(content); }
    catch {
      summary.errors.push({ file, kind: 'invalid_json', reason: 'Le fichier complet ne peut pas être parsé en JSON.' });
      continue;
    }
    summary.parsedJsonFiles++;
    if (result === null || typeof result !== 'object' || Array.isArray(result)) {
      summary.errors.push({ file, kind: 'invalid_root', reason: 'Le JSON est valide mais sa racine n’est pas un objet résultat.' });
      continue;
    }
    summary.resultObjects++;
    validateResult(result, file, summary.errors);
    summary.checkedResultFiles++;
    if (typeof result.uuid === 'string' && result.uuid.trim()) {
      if (uuids.has(result.uuid)) summary.errors.push({ file, kind: 'duplicate_uuid', field: '$.uuid', reason: `UUID déjà utilisé dans ${uuids.get(result.uuid)}.` });
      else uuids.set(result.uuid, file);
    }
    const status = typeof result.status === 'string' ? result.status : '(absent ou non textuel)';
    statuses.set(status, (statuses.get(status) || 0) + 1);
    for (const key of Object.keys(result)) presence.set(key, (presence.get(key) || 0) + 1);
    if (summary.samples.length < summary.sampleLimit) summary.samples.push(summarizeResult(file, result));
  }
  summary.statusCounts = Object.fromEntries(statuses);
  summary.fieldPresenceCounts = Object.fromEntries(presence);
  summary.uniqueUuids = uuids.size;
  return summary;
}

function allureVerdict(evidence) {
  const defects = evidence.errors.filter(e => e.kind !== 'read_error');
  const verdict = defects.length ? 'INVALID' : !evidence.totalFiles || evidence.errors.length ? 'NOT_EVALUATED' : 'VALID';
  const reasoning = defects.length ? defects.map(e => `${e.file} : ${e.reason}`).join('\n')
    : !evidence.totalFiles ? 'Aucun résultat Allure à vérifier.'
    : evidence.errors.length ? 'Certains résultats Allure sont illisibles ; vérification incomplète.'
    : `${evidence.checkedResultFiles}/${evidence.totalFiles} résultats contrôlés localement : types, structures imbriquées, UUID et timestamps cohérents. ${evidence.scope}`;
  return { check: 'Allure Results', verdict, analysisStatus: verdict === 'NOT_EVALUATED' ? 'INCOMPLETE' : 'COMPLETE',
    method: 'deterministic', reasoning, detail: reasoning, evidence };
}

module.exports = { buildAllureSummary, allureVerdict };
