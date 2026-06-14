'use strict';
// ============================================================
// Memory Store — Mémoire épisodique des agents
// Chaque run d'agent = un épisode dans memory/episodes.jsonl
// Structure : { id, ts, agent, trigger, results[], summary, metrics }
// ============================================================
const fs   = require('fs');
const path = require('path');

const FRAMEWORK    = path.join(__dirname, '..', '..', '..');
const MEMORY_DIR   = path.join(FRAMEWORK, 'memory');
const EPISODES_FILE = path.join(MEMORY_DIR, 'episodes.jsonl');

fs.mkdirSync(MEMORY_DIR, { recursive: true });

function nowStr() { return new Date().toISOString(); }
function epId()   { return `ep_${Date.now()}`; }

// ── Écriture ───────────────────────────────────────────────────────────────────
function recordEpisode(agent, results = [], summary = '', trigger = 'manual', metrics = {}) {
  const ep = { id: epId(), ts: nowStr(), agent, trigger, results, summary, metrics };
  fs.appendFileSync(EPISODES_FILE, JSON.stringify(ep) + '\n', 'utf8');
  return ep.id;
}

// ── Lecture ────────────────────────────────────────────────────────────────────
function loadAllEpisodes(agent = null, limit = null) {
  if (!fs.existsSync(EPISODES_FILE)) return [];
  const all = fs.readFileSync(EPISODES_FILE, 'utf8')
    .split('\n').filter(Boolean)
    .map(l => { try { return JSON.parse(l); } catch { return null; } })
    .filter(ep => ep && (!agent || ep.agent === agent));
  return limit ? all.slice(-limit) : all;
}

// ── Historique d'un TC ─────────────────────────────────────────────────────────
function getTcHistory(tcId, lastN = 10) {
  const key  = tcId.toLowerCase();
  const hist = [];
  for (const ep of loadAllEpisodes()) {
    for (const r of (ep.results || [])) {
      if ((r.tc || '').toLowerCase() === key) {
        hist.push({ ts: ep.ts, episode_id: ep.id, agent: ep.agent, ...r });
      }
    }
  }
  return hist.slice(-lastN);
}

// ── Échecs récurrents ──────────────────────────────────────────────────────────
function getRecurringFailures(minOccurrences = 3) {
  const stats = {};
  for (const ep of loadAllEpisodes()) {
    for (const r of (ep.results || [])) {
      if (!r.tc) continue;
      if (!stats[r.tc]) stats[r.tc] = { count: 0, categories: {}, confidences: [], last_seen: ep.ts, agents: new Set() };
      const s = stats[r.tc];
      s.count++; s.last_seen = ep.ts; s.agents.add(ep.agent);
      const cat = r.category || r.verdict || 'unknown';
      s.categories[cat] = (s.categories[cat] || 0) + 1;
      if (r.confidence != null) s.confidences.push(r.confidence);
    }
  }
  const result = {};
  for (const [tc, s] of Object.entries(stats)) {
    if (s.count < minOccurrences) continue;
    result[tc] = {
      count:             s.count,
      last_seen:         s.last_seen,
      categories:        s.categories,
      agents:            [...s.agents],
      avg_confidence:    s.confidences.length ? Math.round(s.confidences.reduce((a,b)=>a+b,0)/s.confidences.length*1000)/1000 : null,
      dominant_category: Object.entries(s.categories).sort((a,b)=>b[1]-a[1])[0]?.[0],
    };
  }
  return result;
}

// ── Injection de contexte dans un prompt ──────────────────────────────────────
function getContextFor(tcId) {
  const hist = getTcHistory(tcId);
  if (!hist.length) return `Aucun historique pour ${tcId}.`;

  const categories = {}; const confidences = [];
  for (const h of hist) {
    const cat = h.category || h.verdict || 'unknown';
    categories[cat] = (categories[cat] || 0) + 1;
    if (h.confidence != null) confidences.push(h.confidence);
  }
  const catStr  = Object.entries(categories).sort((a,b)=>b[1]-a[1]).map(([c,n])=>`${c}×${n}`).join(', ');
  const avgConf = confidences.length ? Math.round(confidences.reduce((a,b)=>a+b,0)/confidences.length*100)/100 : null;
  const last    = hist[hist.length-1];
  let trend = '';
  if (confidences.length >= 3) {
    const r = confidences.slice(-3);
    trend = r[2] > r[0] ? '↑ hausse' : r[2] < r[0] ? '↓ baisse' : '→ stable';
  }
  const lines = [`Historique ${tcId} (${hist.length} runs) : ${catStr}`];
  if (avgConf !== null) lines.push(`Confiance moyenne : ${avgConf}${trend ? ` | Tendance : ${trend}` : ''}`);
  lines.push(`Dernier run (${last.ts.slice(0,10)}) : ${last.category||last.verdict||'?'} via ${last.agent}`);
  return lines.join('\n');
}

function getAgentSummary(agent, lastN = 5) {
  const eps = loadAllEpisodes(agent, lastN);
  if (!eps.length) return `Aucun historique pour ${agent}.`;
  return [`Derniers ${eps.length} runs de ${agent} :`,
    ...[...eps].reverse().map(ep => `  ${ep.ts.slice(0,10)} — ${ep.summary || `${(ep.results||[]).length} résultats`}`)
  ].join('\n');
}

module.exports = { recordEpisode, loadAllEpisodes, getTcHistory, getRecurringFailures, getContextFor, getAgentSummary, EPISODES_FILE };
