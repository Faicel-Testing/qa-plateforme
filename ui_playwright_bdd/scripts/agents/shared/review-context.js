'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const runtime = require('./pipeline-runtime');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
function tree(root, relative) {
  const dir = path.join(root, relative);
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir).sort().flatMap(name => {
    // Python bytecode is regenerated on import; only maintained agent sources bind review.
    if (relative.replace(/\\/g, '/').startsWith('qa_agents') && (name === '__pycache__' || name.endsWith('.pyc'))) return [];
    const rel = path.join(relative, name), file = path.join(root, rel);
    const stat = fs.lstatSync(file);
    if (stat.isSymbolicLink()) throw new Error('Review context cannot contain symlinks');
    if (rel.replace(/\\/g, '/') === 'src/fixtures/user.json') return [];
    if (stat.isDirectory()) return tree(root, rel);
    const normalized = rel.replace(/\\/g, '/');
    let content = fs.readFileSync(file);
    // Usage counters change during analysis; prompt text and versions remain bound.
    if (normalized.startsWith('prompts/') && normalized.endsWith('.json')) {
      const prompt = JSON.parse(content.toString('utf8'));
      delete prompt.metrics;
      content = JSON.stringify(prompt);
    }
    return [[normalized, hash(content)]];
  });
}
function sourceHash(root) {
  const entries = ['src', 'scripts', 'config', 'prompts', 'qa_agents'].flatMap(dir => tree(root, dir));
  for (const name of ['package.json', 'package-lock.json', 'cucumber.js', 'tsconfig.json', 'eslint.config.cjs', '.nvmrc']) {
    if (fs.existsSync(path.join(root, name))) entries.push([name, hash(fs.readFileSync(path.join(root, name)))]);
  }
  return hash(JSON.stringify(entries));
}
function snapshot(root, env = process.env) {
  const dir = runtime.resultDirectory(root, env);
  const entries = fs.existsSync(dir) ? fs.readdirSync(dir).sort().filter(n => n.endsWith('.json'))
    .map(n => [n, hash(fs.readFileSync(path.join(dir, n)))]) : [];
  return { source: sourceHash(root), evidence: hash(JSON.stringify(entries)), resultsDir: path.resolve(dir) };
}
module.exports = { hash, sourceHash, snapshot };
