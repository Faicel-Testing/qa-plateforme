'use strict';
const fs = require('fs');
const path = require('path');

function readSource(root, args) {
  const file = path.resolve(root, String(args.file_path || ''));
  const relative = path.relative(root, file);
  if (relative.startsWith('..') || path.isAbsolute(relative) || !/\.(ts|js|feature|json|md)$/.test(file) || /(?:^|[\\/])(?:node_modules|fixtures|\.git)(?:[\\/]|$)/.test(relative)) {
    return 'ERROR: Only project source/configuration files may be read';
  }
  if (!fs.existsSync(file)) return `ERROR: File not found: ${relative}`;
  const real = path.relative(fs.realpathSync(root), fs.realpathSync(file));
  if (real.startsWith('..') || path.isAbsolute(real) || /(?:^|[\\/])(?:fixtures|credentials|sessions|\.auth|logs|memory)(?:[\\/]|$)/i.test(real) || /(?:storageState|credentials|cookies)\.json$/i.test(real)) return 'ERROR: File outside allowed sources';
  const lines = fs.readFileSync(file, 'utf8').split(/\r?\n/);
  const start = args.line_start === undefined ? 1 : Number(args.line_start);
  const requestedEnd = args.line_end === undefined ? start + 399 : Number(args.line_end);
  if (!Number.isInteger(start) || start < 1 || !Number.isInteger(requestedEnd) || requestedEnd < start) return 'ERROR: Invalid line range';
  const end = Math.min(requestedEnd, start + 399, lines.length);
  if (start > lines.length) return `${relative}: EOF; total_lines=${lines.length}. No further content.`;
  return `${relative}: lines ${start}-${end}/${lines.length}; ${end === lines.length ? 'EOF (complete through end of file)' : `next_line=${end + 1}`}\n` +
    lines.slice(start - 1, end).map((line, i) => `${start + i}: ${line}`).join('\n');
}

function rcaVariables(key, group) {
  const failList = group.map(f => `Test: ${f.name}\nStatus: ${f.status}\nComplete error:\n${f.message}\nComplete trace:\n${f.trace}`).join('\n\n');
  return { count: group.length, fail_list: failList, test_name: group.map(f => f.name).join(', '),
    tc: group.map(f => f.name).join(', '), tc_id: key, us: 'N/A', us_id: 'N/A',
    error_message: group.map(f => f.message).join('\n\n'), stack_trace: group.map(f => f.trace).join('\n\n'),
    suite: 'playwright', method: 'N/A', endpoint: 'N/A' };
}
function sourceBundle(root, failure, execution = {}) {
  const listed = [];
  for (const folder of ['features', 'steps', 'pages', 'api', 'config', 'core']) {
    const dir = path.join(root, 'src', folder);
    if (fs.existsSync(dir)) for (const name of fs.readdirSync(dir)) {
      if (/\.(ts|feature)$/.test(name)) listed.push(`src/${folder}/${name}`);
    }
  }
  const trace = String(failure.trace || failure.statusDetails?.trace || '').replace(/\\/g, '/');
  const cited = listed.filter(file => trace.includes(file));
  const candidates = [...new Set([...cited, 'src/api/QACartApiClient.ts', 'src/core/world.ts', 'src/hooks/hooks.ts'])];
  const reads = [];
  let budget = 40000;
  for (const file of candidates.slice(0, 8)) {
    if (budget < 1000) break;
    const content = readSource(root, { file_path: file });
    if (content.startsWith('ERROR:')) continue;
    const bounded = content.length > budget ? content.slice(0, budget) + '\nTRUNCATED: read_source required for remaining lines.' : content;
    reads.push([file, bounded]); budget -= bounded.length;
  }
  return { inventory: 'Existing source paths (use these exact names):\n' + listed.join('\n') +
      '\nPreloaded sources are the CURRENT WORKING COPY, not proof of configuration during an older run. ' +
      'Never treat a precondition failure as evidence that the Todo assertion ran. ' +
      'Runtime evidence is scoped to the selected test and run; no current .env values are imported.',
    reads, recorded_api: recordedApi(root, failure, execution) };
}
function recordedApi(root, failure, { directory, runId } = {}) {
  const missing = { status: 'NOT_RECORDED', events: [], note: 'No API telemetry recorded for this test; current source code cannot establish old server availability.' };
  if (!directory || !runId || !failure.uuid) return missing;
  const artifact = (name, max = 2097152) => {
    if (typeof name !== 'string' || path.basename(name) !== name) return null;
    try {
      const file = path.join(directory, name), stat = fs.lstatSync(file);
      if (!stat.isFile() || stat.isSymbolicLink() || stat.size > max) return null;
      return fs.readFileSync(file, 'utf8');
    } catch { return null; }
  };
  try {
    const relative = path.relative(fs.realpathSync(root), fs.realpathSync(directory));
    if (relative.startsWith('..') || path.isAbsolute(relative)) return missing;
    const manifest = JSON.parse(artifact('run-manifest.json'));
    if (manifest.runId !== runId) return missing;
    const names = fs.readdirSync(directory).filter(n => /-(?:result|container)\.json$/.test(n)).slice(0, 10000);
    const documents = names.flatMap(name => { try { return [JSON.parse(artifact(name))]; } catch { return []; } });
    const selected = documents.filter(d => d && (d.uuid === failure.uuid || d.children?.includes(failure.uuid)));
    const events = [], targets = new Set();
    const visit = node => {
      if (!node || typeof node !== 'object' || events.length >= 20) return;
      for (const attachment of node.attachments || []) {
        if (attachment.type === 'text/plain') {
          const match = artifact(attachment.source, 4096)?.match(/^Base URL:\s*(https?:\/\/\S+)\s*$/);
          if (match) { try { targets.add(new URL(match[1]).origin); } catch { /* No usable recorded target. */ } }
        }
        if (attachment.type !== 'application/json') continue;
        try {
          const value = JSON.parse(artifact(attachment.source, 8192));
          if (value?.kind !== 'qa-api-diagnostic' || value.schemaVersion !== 1) continue;
          const url = new URL(value.target);
          if (!['http:', 'https:'].includes(url.protocol)) continue;
          events.push({ kind: value.kind, schemaVersion: 1, timestamp: value.timestamp,
            target: url.origin, method: value.method === 'POST' ? 'POST' : 'UNKNOWN',
            path: /^\/api\/v1\/users\/(register|login)$/.test(value.path) ? value.path : 'UNKNOWN',
            status: Number.isInteger(value.status) ? value.status : null,
            durationMs: Number.isFinite(value.durationMs) ? value.durationMs : null,
            timeoutMs: Number.isFinite(value.timeoutMs) ? value.timeoutMs : null,
            maxRetries: Number.isInteger(value.maxRetries) ? value.maxRetries : null,
            mode: value.mode === 'real-http' ? 'real-http' : 'UNKNOWN',
            errorCode: /^[A-Z_0-9]{1,60}$/.test(value.errorCode || '') ? value.errorCode : null });
        } catch { /* Corrupt, oversized or unrelated attachments are not evidence. */ }
      }
      for (const child of [...(node.steps || []), ...(node.befores || []), ...(node.afters || [])]) visit(child);
    };
    selected.forEach(visit);
    return events.length ? { status: 'RECORDED', events, targets: [...targets] } : { ...missing, targets: [...targets] };
  } catch { return missing; }
}
function sourceContext(root, failure) {
  const bundle = sourceBundle(root, failure);
  return bundle.inventory + '\nCURRENT WORKING COPY SOURCE READS:\n' + bundle.reads.map(([, content]) => content).join('\n\n');
}
module.exports = { readSource, rcaVariables, sourceContext, sourceBundle, recordedApi };
