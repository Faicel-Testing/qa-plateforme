// Groq-only LLM transport. No local provider or cross-provider fallback.
require('dotenv').config({ quiet: true });
const gateway = require('./shared/ai-gateway');
const cb = require('./shared/circuit-breaker');
const GROQ_MODEL = process.env.GROQ_MODEL || 'openai/gpt-oss-120b';
const MODEL = GROQ_MODEL;
const PROVIDER = 'groq';
function requireGroq() {
  if (process.env.AI_LOCAL_ONLY === 'true') throw new Error('AI_LOCAL_ONLY blocks Groq; no local provider is configured');
  if (!process.env.GROQ_API_KEY) throw new Error('GROQ_API_KEY missing; Groq is the only configured provider');
}
function getGroq() {
  requireGroq();
  const Groq = require('groq-sdk');
  return new Groq({ apiKey: process.env.GROQ_API_KEY, maxRetries: 0, timeout: 90000,
    fetch: gateway.gatewayFetch('groq', require('./shared/task-metrics').meteredFetch('groq')) });
}
async function assertRunning() {
  requireGroq();
  console.log(`Provider : Groq | Modele : ${MODEL}`);
}

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

// ── Appels bruts (sans résilience) ─────────────────────────────────────────────
async function _rawGroqChat(messages, tools, temperature) {
  const groq = getGroq();
  const req = { model: GROQ_MODEL, messages, stream: false };
  if (tools) req.tools = tools;
  if (temperature != null) req.temperature = temperature;
  const resp = await groq.chat.completions.create(req);
  // Conserve le format commun attendu par les agents
  const choice = resp.choices[0];
  return {
    message: {
      role: 'assistant',
      content: choice.message.content || '',
      tool_calls: choice.message.tool_calls?.map(tc => ({
        id: tc.id,
        type: tc.type,
        function: {
          name: tc.function.name,
          arguments: tc.function.arguments
        }
      }))
    },
    done: choice.finish_reason === 'stop' || choice.finish_reason === 'tool_calls'
  };
}

function providerError(provider, error) {
  // Ne pas journaliser le corps HTTP : il peut contenir le prompt ou des secrets.
  const status = error?.status || error?.status_code;
  const code = error?.code || error?.cause?.code || error?.error?.type;
  const details = [];
  if (Number.isInteger(status)) details.push(`HTTP ${status}`);
  if (typeof code === 'string' && /^[a-zA-Z0-9_.-]{1,80}$/.test(code)) details.push(code);
  return `${provider} : ${details.join(' / ') || 'échec de la requête'}`;
}

// Chat through the existing circuit breaker/cache, without provider fallback.
async function chat(messages, opts = {}) {
  requireGroq();
  messages = gateway.preflight(messages);
  if (process.env.RAG_ENABLED !== 'false' && opts.rag !== false) {
    const path = require('node:path');
    messages = await require('./shared/hybrid-rag').augmentMessages(messages, {
      root: path.join(__dirname, '..', '..'),
      agent: path.basename(process.argv[1] || '', '.js'),
      env: process.env,
    });
  }
  let tools       = opts.tools ? toOpenAITools(opts.tools) : undefined;
  ({ messages, tools } = gateway.preflight({ messages, tools }));
  const fnName      = opts._fnName || 'chat';
  const temperature = opts.temperature;


  // Évite de réutiliser les anciennes réponses sans id, ou celles d'autres outils.
  const cacheVariant = tools?.length
    ? { protocol: 'tool-calls-v2', model: GROQ_MODEL, tools, temperature }
    : temperature;
  let groqFailure;
  try {
    const { value, fallback } = await cb.execute(
      async () => gateway.preflight(await _rawGroqChat(messages, tools, temperature)), messages, fnName, cacheVariant
    );
    if (!fallback) return gateway.preflight(JSON.parse(value));
    groqFailure = 'Groq : circuit ouvert';
  } catch (err) {
    if (gateway.isGatewayError(err)) throw err;
    groqFailure = providerError('Groq', err);
  }

  const error = new Error(`Appel Groq impossible (${groqFailure}). Aucune reponse IA disponible.`);
  error.code = tools?.length ? 'LLM_TOOL_CALL_FAILED' : 'LLM_UNAVAILABLE';
  throw error;
}

// ── Chat (streaming) ──────────────────────────────────────────────────────────
async function chatStream(messages) {
  requireGroq();
  messages = gateway.preflight(messages);
  const stream = await getGroq().chat.completions.create({ model: GROQ_MODEL, messages, stream: true });
  return (async function* () {
    for await (const chunk of stream) {
      yield { message: { content: chunk.choices[0]?.delta?.content || '' },
        done: chunk.choices[0]?.finish_reason === 'stop' };
    }
  })();
}

// ── chatCot — Chain of Thought (deux étapes) ──────────────────────────────────
// Étape 1 : raisonnement libre, étape 2 : extraction structurée
async function chatCot(messages, structuredPrompt = null) {
  const cotMessages = [
    ...messages,
    { role: 'user', content: 'Raisonne étape par étape avant de conclure. Préfixe ta réponse par ÉTAPE 1, ÉTAPE 2, ... CONCLUSION.' }
  ];
  const step1 = await chat(cotMessages, { _fnName: 'chatCot' });
  const reasoning = step1.message.content || '';

  if (!structuredPrompt) return reasoning;

  const step2Messages = [
    ...messages,
    { role: 'assistant', content: reasoning },
    { role: 'user', content: structuredPrompt }
  ];
  const step2 = await chat(step2Messages, { _fnName: 'chatCot' });
  return { reasoning, structured: step2.message.content || '' };
}

// ── chatStructured — Structured Output (JSON schema enforcement) ───────────────
async function chatStructured(messages, schema, maxRetries = 3, temperature = null) {
  const schemaStr = JSON.stringify(schema, null, 2);
  const systemMsg = {
    role: 'user',
    content: `Réponds UNIQUEMENT en JSON valide respectant ce schéma:\n${schemaStr}\n\nPas de markdown, pas d'explication, juste le JSON brut.`
  };
  const augmented = [...messages, systemMsg];

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    const resp = await chat(augmented, { _fnName: 'chatStructured', temperature });
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
      const data = await chatStructured(messages, schema, 3, temps[i]);
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
