'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { createHash } = require('node:crypto');
const ROOT = path.resolve(__dirname, '../../../skills');
const ALLOWED = Object.freeze(['analyse-echec', 'audit-sources', 'triage-rca', 'generation-steps', 'generation-pages', 'generation-gherkin', 'proposition-correction', 'recommandation-release']);
function fail() { const e = new Error('Required agent skill is missing or invalid'); e.code = 'AGENT_SKILL_INVALID'; throw e; }
function load(name) {
  if (!ALLOWED.includes(name)) fail();
  try {
    const file = path.join(ROOT, name, 'SKILL.md');
    const real = fs.realpathSync(file);
    const relative = path.relative(fs.realpathSync(ROOT), real);
    if (relative.startsWith('..') || path.isAbsolute(relative) || fs.statSync(real).size > 16000) fail();
    const raw = fs.readFileSync(real, 'utf8').replace(/^\uFEFF/, '').replace(/\r\n/g, '\n');
    const match = raw.match(/^---\nname: ([a-z0-9-]+)\ndescription: ([^\n]+)\n---\n([\s\S]+)$/);
    if (!match || match[1] !== name || !match[2].trim() || !match[3].trim()) fail();
    return { name, description: match[2], body: match[3].trim(), sha256: createHash('sha256').update(raw).digest('hex') };
  } catch { fail(); }
}
function instructions(name) {
  const skill = load(name);
  return `[Skill ${skill.name} sha256=${skill.sha256}]\n${skill.body}`;
}
function messages(name, task) {
  return [{ role: 'system', content: instructions(name) }, { role: 'user', content: task }];
}
module.exports = { load, instructions, messages, ALLOWED };
