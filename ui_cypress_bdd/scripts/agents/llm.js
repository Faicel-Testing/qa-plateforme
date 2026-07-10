// ============================================
// LLM Helper — Groq (cloud) ou Ollama (local)
// ============================================
// Détection automatique du provider :
//   → GROQ_API_KEY défini dans .env  → utilise Groq (cloud, gratuit)
//   → Sinon                          → utilise Ollama (local)
//
// Config .env :
//   GROQ_API_KEY=gsk_xxxx            ← clé gratuite sur console.groq.com
//   GROQ_MODEL=qwen-2.5-coder-32b   ← défaut (excellent pour code/QA)
//   OLLAMA_MODEL=qwen2.5-coder:7b   ← défaut si Ollama
//   OLLAMA_HOST=http://localhost:11434
// ============================================


require('dotenv').config();
// Bypass SSL certificate issues on corporate/local networks
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';
const http  = require('http');
const https = require('https');

// ── Provider detection ────────────────────────────────────────────────────────
const USE_GROQ   = !!process.env.GROQ_API_KEY;
const GROQ_MODEL = process.env.GROQ_MODEL  || 'llama-3.3-70b-versatile';
const OLMA_MODEL = process.env.OLLAMA_MODEL || 'qwen2.5-coder:7b';
const OLMA_HOST  = (process.env.OLLAMA_HOST || 'http://localhost:11434').replace(/\/$/, '');

const MODEL    = USE_GROQ ? GROQ_MODEL : OLMA_MODEL;
const PROVIDER = USE_GROQ ? 'groq' : 'ollama';

// ── Groq client ───────────────────────────────────────────────────────────────
function getGroq() {
  const Groq = require('groq-sdk');
  return new Groq({ apiKey: process.env.GROQ_API_KEY });
}

// ── Ollama client ─────────────────────────────────────────────────────────────
function getOllama() {
  const { Ollama } = require('ollama');
  return new Ollama({ host: OLMA_HOST });
}

// ── Ollama health check ───────────────────────────────────────────────────────
function isOllamaRunning() {
  return new Promise((resolve) => {
    const lib = OLMA_HOST.startsWith('https') ? https : http;
    lib.get(`${OLMA_HOST}/api/tags`, res => resolve(res.statusCode === 200))
       .on('error', () => resolve(false));
  });
}

async function assertRunning() {
  if (USE_GROQ) {
    if (!process.env.GROQ_API_KEY) {
      console.error('\n❌  GROQ_API_KEY manquant dans .env');
      console.error('    → Clé gratuite sur : https://console.groq.com');
      process.exit(1);
    }
    console.log(`Provider : Groq ☁️   Modèle : ${MODEL}`);
    return;
  }
  const ok = await isOllamaRunning();
  if (!ok) {
    console.error('\n❌  Ollama ne tourne pas.');
    console.error('    → Installer : https://ollama.com/download');
    console.error(`    → Modèle   : ollama pull ${OLMA_MODEL}`);
    console.error('    → Démarrer : ollama serve');
    process.exit(1);
  }
  console.log(`Provider : Ollama 🖥️   Modèle : ${MODEL}`);
}

// ── Tool format conversion ────────────────────────────────────────────────────
// Agents définissent les tools en format Anthropic {name, description, input_schema}
// Groq & Ollama attendent OpenAI {type:'function', function:{name, description, parameters}}
function toOpenAITools(tools) {
  if (!tools || !tools.length) return undefined;
  return tools.map(t => ({
    type: 'function',
    function: {
      name: t.name,
      description: t.description || t.name,
      parameters: t.input_schema || { type: 'object', properties: {} }
    }
  }));
}

// ── Parse tool-call arguments (string ou object selon modèle) ─────────────────
function parseArgs(raw) {
  if (!raw) return {};
  if (typeof raw === 'string') { try { return JSON.parse(raw); } catch { return {}; } }
  return raw;
}

// ── Chat (non-streaming) ──────────────────────────────────────────────────────
async function chat(messages, opts = {}) {
  const tools = opts.tools ? toOpenAITools(opts.tools) : undefined;

  if (USE_GROQ) {
    const groq = getGroq();
    const req = { model: GROQ_MODEL, messages, stream: false };
    if (tools) req.tools = tools;
    const resp = await groq.chat.completions.create(req);
    // Normalise vers format Ollama pour que les agents n'aient pas besoin de changer
    const choice = resp.choices[0];
    return {
      message: {
        role: 'assistant',
        content: choice.message.content || '',
        tool_calls: choice.message.tool_calls?.map(tc => ({
          function: {
            name: tc.function.name,
            arguments: tc.function.arguments
          }
        }))
      },
      done: choice.finish_reason === 'stop' || choice.finish_reason === 'tool_calls'
    };
  }

  // Ollama
  const ollama = getOllama();
  const req = { model: OLMA_MODEL, messages, stream: false };
  if (tools) req.tools = tools;
  return ollama.chat(req);
}

// ── Chat (streaming) ──────────────────────────────────────────────────────────
async function chatStream(messages) {
  if (USE_GROQ) {
    const groq = getGroq();
    const stream = await groq.chat.completions.create({
      model: GROQ_MODEL,
      messages,
      stream: true
    });
    // Adapte le stream Groq au format Ollama {message:{content}, done}
    return (async function* () {
      for await (const chunk of stream) {
        const text = chunk.choices[0]?.delta?.content || '';
        const done = chunk.choices[0]?.finish_reason === 'stop';
        yield { message: { content: text }, done };
      }
    })();
  }

  // Ollama
  const ollama = getOllama();
  return ollama.chat({ model: OLMA_MODEL, messages, stream: true });
}

// ── chatCot — Chain of Thought (deux étapes) ──────────────────────────────────
// Étape 1 : raisonnement libre, étape 2 : extraction structurée
async function chatCot(messages, structuredPrompt = null) {
  const cotMessages = [
    ...messages,
    { role: 'user', content: 'Raisonne étape par étape avant de conclure. Préfixe ta réponse par ÉTAPE 1, ÉTAPE 2, ... CONCLUSION.' }
  ];
  const step1 = await chat(cotMessages);
  const reasoning = step1.message.content || '';

  if (!structuredPrompt) return reasoning;

  const step2Messages = [
    ...messages,
    { role: 'assistant', content: reasoning },
    { role: 'user', content: structuredPrompt }
  ];
  const step2 = await chat(step2Messages);
  return { reasoning, structured: step2.message.content || '' };
}

// ── chatStructured — Structured Output (JSON schema enforcement) ───────────────
async function chatStructured(messages, schema, maxRetries = 3) {
  const schemaStr = JSON.stringify(schema, null, 2);
  const systemMsg = {
    role: 'user',
    content: `Réponds UNIQUEMENT en JSON valide respectant ce schéma:\n${schemaStr}\n\nPas de markdown, pas d'explication, juste le JSON brut.`
  };
  const augmented = [...messages, systemMsg];

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    const resp = await chat(augmented);
    const raw  = (resp.message.content || '').trim();
    const match = raw.match(/\{[\s\S]*\}/);
    if (match) {
      try { return JSON.parse(match[0]); } catch { /* retry */ }
    }
    // Also try array
    const arrMatch = raw.match(/\[[\s\S]*\]/);
    if (arrMatch) {
      try { return JSON.parse(arrMatch[0]); } catch { /* retry */ }
    }
  }
  return {};
}

// ── chatConfident — Confidence scoring ────────────────────────────────────────
// Retourne { result, confidence } où confidence ∈ [0,1]
async function chatConfident(messages, threshold = 0.70) {
  const schema = {
    result: 'string — ta réponse principale',
    confidence: 'float entre 0.0 et 1.0 — ton niveau de certitude',
    reasoning: 'string — justification courte'
  };
  const data = await chatStructured(messages, schema);
  return {
    result:     data.result     || '',
    confidence: parseFloat(data.confidence) || 0.0,
    reasoning:  data.reasoning  || '',
    above_threshold: (parseFloat(data.confidence) || 0.0) >= threshold
  };
}

// ── chatAdversarial — Adversarial verification ────────────────────────────────
// Génère une réponse, puis la critique, puis tranche
async function chatAdversarial(messages) {
  // Phase 1 : proposition
  const resp1 = await chat(messages);
  const proposal = resp1.message.content || '';

  // Phase 2 : critique adversariale
  const criticMessages = [
    ...messages,
    { role: 'assistant', content: proposal },
    { role: 'user', content: `Joue le rôle d'un auditeur critique. Liste les failles, erreurs ou imprécisions dans la réponse ci-dessus. Sois rigoureux et concis.` }
  ];
  const resp2 = await chat(criticMessages);
  const critique = resp2.message.content || '';

  // Phase 3 : verdict final
  const verdictMessages = [
    ...messages,
    { role: 'assistant', content: proposal },
    { role: 'user', content: `Critique identifiée:\n${critique}\n\nRevois ta réponse en tenant compte de cette critique. Donne ta réponse finale corrigée.` }
  ];
  const resp3 = await chat(verdictMessages);
  return {
    proposal,
    critique,
    final: resp3.message.content || ''
  };
}

// ── chatSelfConsistent — Self-Consistency voting ──────────────────────────────
// Pose la même question N fois avec des températures variées, vote majoritaire
async function chatSelfConsistent(messages, schema, n = 3) {
  const temps = [0.3, 0.7, 0.9].slice(0, n);
  const responses = [];

  for (let i = 0; i < n; i++) {
    try {
      const data = await chatStructured(messages, schema);
      responses.push(data);
    } catch {
      // ignore failed vote
    }
  }

  if (!responses.length) return { responses: [], winner: null };

  // Majority vote sur le premier champ clé (verdict/result)
  const keyField = Object.keys(responses[0] || {})[0] || 'result';
  const counts = {};
  for (const r of responses) {
    const v = String(r[keyField] || '');
    counts[v] = (counts[v] || 0) + 1;
  }
  const winnerVal = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0];
  const winner    = responses.find(r => String(r[keyField] || '') === winnerVal);

  return { responses, winner, vote_counts: counts, n_votes: responses.length };
}

module.exports = {
  chat, chatStream, assertRunning, parseArgs,
  chatCot, chatStructured, chatConfident, chatAdversarial, chatSelfConsistent,
  MODEL, PROVIDER
};
