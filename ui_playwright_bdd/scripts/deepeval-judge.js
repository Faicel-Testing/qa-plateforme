'use strict';
// JSON stdin/stdout bridge. No prompts or credentials are printed in errors.
require('dotenv').config({ quiet: true });
const { meteredFetch } = require('./agents/shared/task-metrics');
const { gatewayFetch } = require('./agents/shared/ai-gateway');
function responseFormat(model, schema) {
  return ['openai/gpt-oss-120b', 'openai/gpt-oss-20b'].includes(model)
    ? { type: 'json_schema', json_schema: { name: 'deepeval_metric', strict: false, schema } }
    : { type: 'json_object' };
}
async function generate(request) {
  if (!request || typeof request.prompt !== 'string' || request.prompt.length > 150000) throw Error('Invalid judge request');
  const provider = process.env.DEEPEVAL_JUDGE_PROVIDER || 'groq';
  const model = process.env.DEEPEVAL_JUDGE_MODEL || 'openai/gpt-oss-120b';
  const prompt = request.schema ? `${request.prompt}\nReturn ONLY valid JSON matching this JSON schema. No markdown fences:\n${JSON.stringify(request.schema)}` : request.prompt;
  const messages = [{ role: 'user', content: prompt }];
  let output;
  if (provider === 'groq') {
    if (!process.env.GROQ_API_KEY) throw Error('GROQ_API_KEY missing');
    const Groq = require('groq-sdk');
    const client = new Groq({ apiKey: process.env.GROQ_API_KEY, maxRetries: 0, timeout: 90000,
      fetch: gatewayFetch('groq', meteredFetch('groq', globalThis.fetch, { kind: 'evaluation' })) });
    const result = await client.chat.completions.create({ model, messages, temperature: 0, max_completion_tokens: 4096,
      ...(request.schema ? { response_format: responseFormat(model, request.schema) } : {}) });
    if (result.choices[0]?.finish_reason === 'length') throw Error('Judge output truncated');
    output = result.choices[0]?.message?.content;
  } else throw Error('Unsupported judge provider');
  if (typeof output !== 'string' || !output.trim()) throw Error('Empty judge response');
  return { output, provider, model };
}
if (require.main === module) {
  let input = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', chunk => { input += chunk; if (input.length > 200000) process.exit(2); });
  process.stdin.on('end', async () => {
    try { process.stdout.write(JSON.stringify(await generate(JSON.parse(input)))); }
    catch (error) {
      // Persist protocol diagnostics locally, never response bodies, prompts or credentials.
      const code = error.code || error.error?.code;
      const diagnostic = { at: new Date().toISOString(), status: error.status || null,
        code: typeof code === 'string' && /^[a-zA-Z0-9_.-]{1,100}$/.test(code) ? code : null,
        message: error.status === 400 ? String(error.error?.error?.message || error.error?.message || '').slice(0, 500) : undefined };
      const fs = require('node:fs'), path = require('node:path');
      const dir = path.join(__dirname, '../logs/deepeval');
      fs.mkdirSync(dir, { recursive: true });
      fs.appendFileSync(path.join(dir, 'judge-errors.jsonl'), JSON.stringify(diagnostic) + '\n');
      process.stderr.write(`Judge unavailable or invalid response${Number.isInteger(error.status) ? ' (HTTP ' + error.status + ')' : ''}\n`); process.exitCode = 2;
    }
  });
}
module.exports = { generate, responseFormat };
