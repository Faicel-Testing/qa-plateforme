'use strict';
// ============================================================
// Circuit Breaker — Résilience + Cache LLM
// États : CLOSED (normal) → OPEN (en panne) → HALF_OPEN (test)
// Cache SHA256 : même prompt → réponse en cache (TTL 1h)
// ============================================================
const fs     = require('fs');
const path   = require('path');
const crypto = require('crypto');

const FRAMEWORK  = path.join(__dirname, '..', '..', '..');
const LOGS_DIR   = path.join(FRAMEWORK, 'logs');
const CB_FILE    = path.join(LOGS_DIR, 'circuit_breaker_state.json');
const CACHE_FILE = path.join(LOGS_DIR, 'llm_cache.json');

fs.mkdirSync(LOGS_DIR, { recursive: true });

const CONFIG = {
  failureThreshold:  3,
  successThreshold:  2,
  cooldownSeconds:   30,
  cacheMaxEntries:   200,
  cacheTtlSeconds:   3600,
};

const STATE = { CLOSED: 'CLOSED', OPEN: 'OPEN', HALF_OPEN: 'HALF_OPEN' };

const DEFAULT_RESPONSES = {
  chat:           'Service LLM temporairement indisponible.',
  chatStructured: '{}',
  chatConfident:  JSON.stringify({ result: null, confidence: 0.0 }),
  chatCot:        'Analyse indisponible — service LLM hors ligne.',
  chatSelfConsistent: JSON.stringify({ winner: null }),
};

// ── Persistence état CB ────────────────────────────────────────────────────────
function loadCbState() {
  try { if (fs.existsSync(CB_FILE)) return JSON.parse(fs.readFileSync(CB_FILE, 'utf8')); } catch {}
  return { state: STATE.CLOSED, failures: 0, successes: 0, openedAt: null };
}
function saveCbState(s) {
  try { fs.writeFileSync(CB_FILE, JSON.stringify(s, null, 2), 'utf8'); } catch {}
}

// ── Cache LLM ─────────────────────────────────────────────────────────────────
function loadCache() {
  try { if (fs.existsSync(CACHE_FILE)) return JSON.parse(fs.readFileSync(CACHE_FILE, 'utf8')); } catch {}
  return {};
}
function saveCache(c) {
  try { fs.writeFileSync(CACHE_FILE, JSON.stringify(c, null, 2), 'utf8'); } catch {}
}

function cacheKey(messages) {
  return crypto.createHash('sha256').update(JSON.stringify(messages)).digest('hex');
}

function cacheGet(messages) {
  const cache = loadCache();
  const entry = cache[cacheKey(messages)];
  if (!entry) return null;
  if (Date.now() / 1000 - entry.ts > CONFIG.cacheTtlSeconds) return null;
  return entry.value;
}

function cacheSet(messages, value) {
  const cache = loadCache();
  const key   = cacheKey(messages);
  cache[key]  = { value, ts: Math.floor(Date.now() / 1000) };
  const keys  = Object.keys(cache);
  if (keys.length > CONFIG.cacheMaxEntries) {
    delete cache[keys.sort((a, b) => cache[a].ts - cache[b].ts)[0]];
  }
  saveCache(cache);
}

// ── Exécution avec CB + cache ──────────────────────────────────────────────────
// fn       : async (messages) => string | object
// messages : tableau de messages LLM
// fnName   : clé pour DEFAULT_RESPONSES
async function execute(fn, messages, fnName = 'chat') {
  // 1. Cache hit → pas d'appel LLM
  const cached = cacheGet(messages);
  if (cached !== null) return { value: cached, fromCache: true, fallback: false };

  const s   = loadCbState();
  const now = Date.now() / 1000;

  // 2. OPEN → vérifier cooldown
  if (s.state === STATE.OPEN) {
    if (now - s.openedAt < CONFIG.cooldownSeconds) {
      return { value: DEFAULT_RESPONSES[fnName] || '', fromCache: false, fallback: true };
    }
    s.state = STATE.HALF_OPEN; s.successes = 0;
    saveCbState(s);
  }

  // 3. Appel LLM
  try {
    const result = await fn(messages);
    const value  = typeof result === 'string' ? result : JSON.stringify(result);
    cacheSet(messages, value);

    s.failures = 0;
    if (s.state === STATE.HALF_OPEN) {
      s.successes = (s.successes || 0) + 1;
      if (s.successes >= CONFIG.successThreshold) { s.state = STATE.CLOSED; s.successes = 0; }
    }
    saveCbState(s);
    return { value, fromCache: false, fallback: false };

  } catch (err) {
    s.failures = (s.failures || 0) + 1;
    if (s.failures >= CONFIG.failureThreshold) { s.state = STATE.OPEN; s.openedAt = now; }
    saveCbState(s);
    throw err;
  }
}

function getStatus() {
  return { ...loadCbState(), config: CONFIG, cacheSize: Object.keys(loadCache()).length };
}

function reset() {
  saveCbState({ state: STATE.CLOSED, failures: 0, successes: 0, openedAt: null });
}

function clearCache() { saveCache({}); }

module.exports = { execute, getStatus, reset, clearCache, STATE, CONFIG, CB_FILE, CACHE_FILE };
