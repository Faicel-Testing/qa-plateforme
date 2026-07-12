'use strict';
// ============================================================
// Tracer — Instrumentation des appels LLM
// Écrit chaque appel dans logs/traces.jsonl (lu par observability-agent)
// ============================================================
const fs   = require('fs');
const path = require('path');

const FRAMEWORK  = path.join(__dirname, '..', '..', '..');
const LOGS_DIR   = path.join(FRAMEWORK, 'logs');
const TRACE_FILE = path.join(LOGS_DIR, 'traces.jsonl');

fs.mkdirSync(LOGS_DIR, { recursive: true });

function detectAgent() {
  const stack    = new Error().stack.split('\n');
  const agentsDir = path.normalize(path.join(__dirname, '..'));
  for (const line of stack) {
    const m = line.match(/\((.+\.js):\d+:\d+\)/);
    if (!m) continue;
    const fp = path.normalize(m[1]);
    if (fp.startsWith(agentsDir) && !fp.includes('llm.js') && !fp.includes('tracer.js')) {
      return path.basename(fp, '.js');
    }
  }
  return 'unknown';
}

function record({ fn, durationMs, promptLen, responseLen, success, model = '', confidence = null, error = null, retries = 0 }) {
  const entry = {
    ts:           new Date().toISOString(),
    agent:        detectAgent(),
    fn,
    model,
    duration_ms:  Math.round(durationMs * 10) / 10,
    prompt_len:   promptLen  || 0,
    response_len: responseLen || 0,
    success,
    retries,
  };
  if (confidence !== null) entry.confidence = Math.round(confidence * 1000) / 1000;
  if (error)               entry.error = String(error).slice(0, 200);
  try { fs.appendFileSync(TRACE_FILE, JSON.stringify(entry) + '\n', 'utf8'); } catch {}
}

// Span — mesure un bloc d'appel LLM
class Span {
  constructor(fn, prompt = '', model = '') {
    this.fn         = fn;
    this.promptLen  = typeof prompt === 'string' ? prompt.length : JSON.stringify(prompt).length;
    this.model      = model;
    this.response   = '';
    this.confidence = null;
    this.retries    = 0;
    this.error      = null;
    this._start     = null;
  }
  begin() { this._start = Date.now(); return this; }
  end(success = true) {
    record({
      fn:          this.fn,
      durationMs:  Date.now() - this._start,
      promptLen:   this.promptLen,
      responseLen: typeof this.response === 'string' ? this.response.length : JSON.stringify(this.response).length,
      success,
      model:       this.model,
      confidence:  this.confidence,
      error:       this.error,
      retries:     this.retries,
    });
  }
}

function loadTraces() {
  if (!fs.existsSync(TRACE_FILE)) return [];
  return fs.readFileSync(TRACE_FILE, 'utf8')
    .split('\n').filter(Boolean)
    .map(l => { try { return JSON.parse(l); } catch { return null; } })
    .filter(Boolean);
}

function clearTraces() {
  if (fs.existsSync(TRACE_FILE)) fs.unlinkSync(TRACE_FILE);
}

module.exports = { record, Span, loadTraces, clearTraces, TRACE_FILE };
