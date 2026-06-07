// ============================================
// MCP Agent — Ollama (local LLM) + Playwright MCP
// ============================================
// Starts the Playwright MCP server locally, connects via stdio,
// and uses the local LLM to explore the app with real browser tools.
// 100% local — no cloud API key required.
//
// Usage:    npm run agent:mcp
// Requires: Ollama running + model pulled + @playwright/mcp installed
// Output:   docs/MCP_EXPLORATION.md
// ============================================

require('dotenv').config();
const llm  = require('./llm');
const path = require('path');
const fs   = require('fs');

const projectRoot = path.resolve(__dirname, '../../');
const BASE_URL    = process.env.BASE_URL || 'https://qacart-todo.herokuapp.com';
const mcpCliPath  = path.join(projectRoot, 'node_modules/@playwright/mcp/cli.js');
const outputPath  = path.join(projectRoot, 'docs/MCP_EXPLORATION.md');

function getMcpSDK() {
  const { Client }              = require('@modelcontextprotocol/sdk/client');
  const { StdioClientTransport } = require('@modelcontextprotocol/sdk/client/stdio.js');
  return { Client, StdioClientTransport };
}

async function run() {
  await llm.assertRunning();
  console.log(`=== MCP AGENT  [${llm.MODEL}] ===`);
  console.log(`App: ${BASE_URL}\n`);

  if (!fs.existsSync(mcpCliPath)) {
    console.error('Playwright MCP not found. Run: npm install @playwright/mcp');
    process.exit(1);
  }

  const { Client, StdioClientTransport } = getMcpSDK();

  const transport = new StdioClientTransport({
    command: 'node',
    args: [mcpCliPath, '--browser', 'chromium', '--headless', '--viewport-size', '1280,720', '--isolated'],
    env: Object.assign({}, process.env)
  });

  const mcpClient = new Client({ name: 'qa-mcp-agent', version: '1.0.0' }, { capabilities: {} });

  console.log('Starting Playwright MCP server...');
  await mcpClient.connect(transport);

  const { tools: mcpTools } = await mcpClient.listTools();
  console.log(`Connected — ${mcpTools.length} tools available.\n`);

  // Convert MCP tools → agent tool format (same as Anthropic-style, llm.js converts internally)
  const agentTools = mcpTools.map(t => ({
    name: t.name,
    description: t.description || t.name,
    input_schema: t.inputSchema || { type: 'object', properties: {} }
  }));

  // ── Agentic loop ────────────────────────────────────────────────────────────
  const messages = [
    {
      role: 'system',
      content: 'You are a QA automation engineer performing exploratory browser testing. Use the browser tools to navigate and inspect the app. Be systematic.'
    },
    {
      role: 'user',
      content: `Explore this Todo web application: ${BASE_URL}

Tasks:
1. Navigate to the root URL — take a snapshot
2. Go to the signup page — verify form fields (firstName, lastName, email, password, submit)
3. Go to the login page — verify form fields (email, password, login button)
4. Try accessing the todo list page while unauthenticated — document what happens
5. Write a findings report: what works, what looks broken, any UI issues

Use browser_navigate, browser_snapshot, browser_take_screenshot as needed.`
    }
  ];

  let iterations = 0;
  const MAX_ITER = 30;

  while (iterations < MAX_ITER) {
    iterations++;
    const resp = await llm.chat(messages, { tools: agentTools });
    const msg  = resp.message;
    const toolCalls = msg.tool_calls || [];

    const text = msg.content?.trim();
    if (text) process.stdout.write(text + '\n');

    if (!toolCalls.length || resp.done) break;

    messages.push(msg);

    for (const tc of toolCalls) {
      const name = tc.function.name;
      const args = llm.parseArgs(tc.function.arguments);
      const argStr = JSON.stringify(args);
      console.log(`  🔧 ${name}  ${argStr.length > 90 ? argStr.slice(0, 90) + '…' : argStr}`);

      let resultContent;
      try {
        const mcpResult = await mcpClient.callTool({ name, arguments: args });
        resultContent = (mcpResult.content || []).map(c => {
          if (c.type === 'text')  return c.text;
          if (c.type === 'image') return `[screenshot — ${Math.round((c.data?.length || 0) * 0.75 / 1024)}KB]`;
          return JSON.stringify(c);
        }).join('\n');
        console.log(mcpResult.isError ? `     ⚠️  ${resultContent.slice(0, 100)}` : '     ✅');
      } catch (err) {
        resultContent = `Tool error: ${err.message}`;
        console.error(`     ❌ ${err.message}`);
      }

      messages.push({ role: 'tool', content: resultContent });
    }
  }

  try { await mcpClient.close(); } catch { /* already closed */ }
  console.log('\nPlaywright MCP server stopped.');

  // Collect all assistant text blocks
  const sessionText = messages
    .filter(m => m.role === 'assistant')
    .map(m => (typeof m.content === 'string' ? m.content : m.content?.filter?.(c => c.type === 'text')?.map(c => c.text)?.join('') || ''))
    .filter(t => t.trim())
    .join('\n\n');

  const ts = new Date().toISOString();
  const report = `# MCP Exploratory Test Report\n\n_${ts} — ${llm.MODEL} + @playwright/mcp_\n_App: ${BASE_URL}_\n\n${sessionText || '_(no findings text)_'}\n`;

  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, report, 'utf-8');
  console.log(`\n📄 docs/MCP_EXPLORATION.md`);
}

run().catch(err => { console.error('MCP agent error:', err.message || err); process.exit(1); });
