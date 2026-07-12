'use strict';
// ============================================================
// Prompt Store — Versioning git-like des prompts LLM
// Stocke chaque prompt dans prompts/<name>.json
// Semver auto-bump : 1.0.0 → 1.0.1 (patch) → 1.1.0 (minor) → 2.0.0 (major)
// ============================================================
const fs   = require('fs');
const path = require('path');

const FRAMEWORK   = path.join(__dirname, '..', '..', '..');
const PROMPTS_DIR = path.join(FRAMEWORK, 'prompts');

fs.mkdirSync(PROMPTS_DIR, { recursive: true });

function nowStr() { return new Date().toISOString().replace(/\.\d+Z$/, 'Z'); }

function bumpVersion(v, part = 'patch') {
  const p = v.split('.').map(Number); while (p.length < 3) p.push(0);
  if (part === 'major')      { p[0]++; p[1] = 0; p[2] = 0; }
  else if (part === 'minor') { p[1]++; p[2] = 0; }
  else                       { p[2]++; }
  return p.join('.');
}

function pPath(name)  { return path.join(PROMPTS_DIR, `${name}.json`); }
function pLoad(name)  { try { return JSON.parse(fs.readFileSync(pPath(name), 'utf8')); } catch { return null; } }
function pSave(name, data) { fs.writeFileSync(pPath(name), JSON.stringify(data, null, 2), 'utf8'); }

// ── Création (v1.0.0) ──────────────────────────────────────────────────────────
function create(name, content, { description = '', agent = '', tags = [] } = {}) {
  if (pLoad(name)) throw new Error(`Prompt '${name}' existe déjà — utilise saveVersion()`);
  const data = {
    name, description, agent, tags,
    current_version: '1.0.0',
    metrics: { calls: 0, avg_confidence: null, last_used: null },
    history: [{ version: '1.0.0', content, created_at: nowStr(), note: 'Version initiale' }],
  };
  pSave(name, data); return '1.0.0';
}

// ── Nouvelle version (auto-bump) ───────────────────────────────────────────────
function saveVersion(name, content, note = '', bump = 'patch') {
  const data = pLoad(name);
  if (!data) return create(name, content, { description: note });
  const nv = bumpVersion(data.current_version, bump);
  data.history.push({ version: nv, content, created_at: nowStr(), note: note || `bump=${bump}` });
  data.current_version = nv;
  pSave(name, data); return nv;
}

// ── Lecture ────────────────────────────────────────────────────────────────────
function get(name, version = null) {
  const data = pLoad(name); if (!data) return null;
  const v = version || data.current_version;
  return data.history.find(e => e.version === v)?.content || null;
}

function getMeta(name) { return pLoad(name); }

function listAll() {
  if (!fs.existsSync(PROMPTS_DIR)) return [];
  return fs.readdirSync(PROMPTS_DIR)
    .filter(f => f.endsWith('.json'))
    .map(f => { const d = JSON.parse(fs.readFileSync(path.join(PROMPTS_DIR, f), 'utf8'));
      return { name: d.name, current_version: d.current_version, description: d.description, nb_versions: d.history.length, metrics: d.metrics }; });
}

function listVersions(name) {
  const data = pLoad(name); if (!data) return [];
  return data.history.map(e => ({ ...e, is_current: e.version === data.current_version }));
}

// ── Gestion versions ───────────────────────────────────────────────────────────
function promote(name, version) {
  const data = pLoad(name); if (!data) throw new Error(`Prompt '${name}' introuvable`);
  if (!data.history.find(e => e.version === version)) throw new Error(`Version ${version} introuvable`);
  data.current_version = version; pSave(name, data);
}

function rollback(name) {
  const data = pLoad(name);
  if (!data || data.history.length < 2) throw new Error(`Pas de version précédente pour '${name}'`);
  const idx = data.history.findIndex(e => e.version === data.current_version);
  if (idx <= 0) throw new Error('Impossible de rollback');
  data.current_version = data.history[idx - 1].version;
  pSave(name, data); return data.current_version;
}

// ── Métriques ──────────────────────────────────────────────────────────────────
function recordUsage(name, confidence = null) {
  const data = pLoad(name); if (!data) return;
  data.metrics.calls = (data.metrics.calls || 0) + 1;
  data.metrics.last_used = nowStr();
  if (confidence !== null) {
    const n = data.metrics.calls, prev = data.metrics.avg_confidence || confidence;
    data.metrics.avg_confidence = Math.round((prev * (n-1) + confidence) / n * 1000) / 1000;
  }
  pSave(name, data);
}

module.exports = { create, saveVersion, get, getMeta, listAll, listVersions, promote, rollback, recordUsage, PROMPTS_DIR };
