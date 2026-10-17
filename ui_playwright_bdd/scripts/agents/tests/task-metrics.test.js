'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const metrics = require('../shared/task-metrics');
const report = require('../shared/metrics-report');
const runtime = require('../shared/pipeline-runtime');
const catalog = { checkedAt: 'test', models: { 'groq/test-model': { input: 2, output: 4, cachedInput: 0.5 } } };
function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'task-metrics-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 }));
  return { root, env: { ...process.env, QA_METRICS_FILE: path.join(root, 'events.jsonl') } };
}
test('prices measured tokens by model and cached input without double counting', () => {
  const tokens = metrics.usage({ usage: { prompt_tokens: 1000, completion_tokens: 100, prompt_tokens_details: { cached_tokens: 200 } } }, 'groq');
  assert.equal(metrics.cost({ provider: 'groq', model: 'test-model' }, tokens, catalog).usd, 0.0021);
  assert.equal(metrics.cost({ provider: 'groq', model: 'missing' }, tokens, catalog).usd, null);
  assert.equal(metrics.cost({ provider: 'groq', model: 'test-model', serviceTier: 'flex' }, tokens, catalog).usd, null);
  assert.equal(metrics.cost({ provider: 'groq', model: 'test-model' }, { inputTokens: null, outputTokens: 0 }, catalog).usd, null);
});
test('Ollama local API zero is distinct from infrastructure cost and remote service', () => {
  assert.equal(metrics.cost({ provider: 'ollama', model: 'local', local: true }, {}).status, 'LOCAL_API_ONLY');
  assert.equal(metrics.cost({ provider: 'ollama', model: 'remote', local: false }, {}).usd, null);
  assert.equal(metrics.cost({ provider: 'ollama', model: 'model:cloud', local: true }, {}).usd, null);
  assert.deepEqual(metrics.usage({ prompt_eval_count: 33 }, 'ollama', 'embedding'), { inputTokens: 33, outputTokens: 0, cachedInputTokens: null });
  assert.equal(metrics.usage({ usage: { prompt_tokens: -1 } }, 'groq').inputTokens, null);
});
test('HTTP attempts record SDK retries, unknown failed usage and successful counts without content', async () => {
  const events = []; let attempt = 0;
  const fetcher = metrics.meteredFetch('groq', async () => ++attempt === 1
    ? Response.json({ error: { message: 'SECRET' } }, { status: 429 })
    : Response.json({ model: 'test-model', usage: { prompt_tokens: 50, completion_tokens: 10 }, choices: [{ message: { content: 'SECRET' } }] }),
  { emit: e => events.push(e), catalog });
  const request = { body: JSON.stringify({ model: 'test-model', messages: [{ content: 'SECRET' }], stream: false }) };
  assert.equal((await fetcher('https://example.test/chat/completions', request)).status, 429);
  assert.equal((await (await fetcher('https://example.test/chat/completions', request)).json()).usage.prompt_tokens, 50);
  const summary = report.aggregate(events);
  assert.equal(summary.totals.calls, 2);
  assert.equal(summary.totals.unknownCostCalls, 1);
  assert.equal(summary.totals.inputTokens, 50);
  assert.equal(summary.totals.failedCalls, 1);
  assert.doesNotMatch(JSON.stringify(events), /SECRET/);
});
for (const provider of ['groq', 'ollama']) test(`${provider} streaming forwards bytes and captures final usage once`, async () => {
  const events = [];
  const tail = provider === 'groq' ? { x_groq: { usage: { prompt_tokens: 20, completion_tokens: 8 } } }
    : { done: true, prompt_eval_count: 20, eval_count: 8 };
  const text = (provider === 'groq' ? 'data: ' : '') + JSON.stringify(tail); // deliberately no terminal newline
  const bytes = new TextEncoder().encode(text);
  let offset = 0;
  const source = new ReadableStream({ pull(c) { if (offset >= bytes.length) c.close(); else { c.enqueue(bytes.slice(offset, offset + 7)); offset += 7; } } });
  const fetcher = metrics.meteredFetch(provider, async () => new Response(source), { emit: e => events.push(e), catalog });
  const response = await fetcher('http://127.0.0.1:11434/api/chat', { body: JSON.stringify({ model: 'test-model', stream: true }) });
  assert.equal(await response.text(), text);
  const ends = events.filter(e => e.type === 'call_end');
  assert.equal(ends.length, 1);
  assert.equal(ends[0].inputTokens, 20);
  assert.equal(ends[0].outputTokens, 8);
});
test('network failures and interrupted streams stay unknown, not free Groq calls', async () => {
  const events = [];
  const failing = metrics.meteredFetch('groq', async () => { throw Error('SECRET'); }, { emit: e => events.push(e), catalog });
  await assert.rejects(failing('https://example.test/chat', { body: '{"model":"test-model"}' }));
  assert.equal(events.at(-1).cost.usd, null);
  assert.doesNotMatch(JSON.stringify(events), /SECRET/);
  const fetcher = metrics.meteredFetch('groq', async () => new Response(new ReadableStream({})), { emit: e => events.push(e), catalog });
  const response = await fetcher('https://example.test/chat', { body: '{"model":"test-model","stream":true}' });
  await response.body.cancel();
  assert.equal(events.at(-1).success, false);
  assert.equal(events.at(-1).cost.usd, null);
});
test('task aggregation does not double count nested calls or treat pending calls as free', () => {
  const events = [
    { type: 'task_start', taskId: 'root' }, { type: 'task_start', taskId: 'child', parentTaskId: 'root' },
    { type: 'call_start', callId: '1', taskId: 'child' },
    { type: 'call_end', callId: '1', taskId: 'child', success: true, inputTokens: 10, outputTokens: 5, cost: { usd: 0.01 } },
    { type: 'task_end', taskId: 'child', durationMs: 80, success: true },
    { type: 'task_end', taskId: 'root', durationMs: 100, success: true },
  ];
  const result = report.aggregate(events);
  assert.equal(result.totals.knownApiCostUsd, 0.01);
  assert.equal(result.tasks[0].knownApiCostUsd, 0.01);
  assert.equal(result.meanCompletedTaskMs, 100);
  assert.equal(result.meanCompletedTaskApiCostUsd, 0.01);
  events.push({ type: 'call_start', callId: '2', taskId: 'child' });
  const incomplete = report.aggregate(events);
  assert.equal(incomplete.meanCompletedTaskApiCostUsd, null);
  assert.equal(incomplete.totals.unknownCostCalls, 1);
});
test('real child execution propagates task IDs, records elapsed time, failures and timeouts', async t => {
  const { env } = fixture(t);
  const child = await runtime.execute(process.execPath, ['-e', 'if(process.env.QA_GATEWAY_BUDGET_ID !== process.env.QA_METRICS_TASK_ID) process.exit(9); console.log(process.env.QA_METRICS_TASK_ID)'], { env, timeout: 30000 });
  assert.equal(child.stdout.trim(), child.metricsTaskId);
  assert.equal(child.success, true);
  const failed = await runtime.execute(process.execPath, ['-e', 'process.exit(process.env.QA_GATEWAY_BUDGET_ID === "parent-budget" ? 3 : 9)'], { env: { ...env, QA_GATEWAY_BUDGET_ID: 'parent-budget' }, timeout: 30000 });
  assert.equal(failed.exitCode, 3);
  const hung = await runtime.execute(process.execPath, ['-e', 'setInterval(()=>{},1000)'], { env, timeout: 300 });
  assert.equal(hung.timedOut, true);
  const data = report.aggregate(report.readEvents(env.QA_METRICS_FILE).events);
  assert.deepEqual(data.tasks.map(t => t.status), ['PROCESS_OK', 'FAILED', 'TIMEOUT']);
  assert.ok(data.tasks.every(t => t.durationMs > 0));
});
test('malformed ledger lines are reported and labels are escaped in HTML', t => {
  const { root, env } = fixture(t);
  fs.writeFileSync(env.QA_METRICS_FILE, '{bad\n' + JSON.stringify({ version: 1, type: 'task_start', taskId: 'x', label: '<script>bad</script>' }) + '\n');
  const data = report.generate(root, env.QA_METRICS_FILE);
  assert.equal(data.invalidLines, 1);
  assert.equal(data.totals.apiCostComplete, false);
  assert.equal(data.tasks[0].apiCostComplete, false);
  const text = fs.readFileSync(path.join(root, 'logs/metrics/report.html'), 'utf8');
  assert.match(text, /&lt;script&gt;bad/);
  assert.doesNotMatch(text, /<script>bad/);
});
