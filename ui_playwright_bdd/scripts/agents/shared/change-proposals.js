'use strict';
const fs = require('fs');
const path = require('path');
const { randomUUID } = require('crypto');
const { hash, sourceHash } = require('./review-context');
function target(root, file) {
  const absolute = path.resolve(root, file), relative = path.relative(root, absolute).replace(/\\/g, '/');
  if (!/^src\/(features|steps|pages)\/[^:]+\.(feature|ts)$/.test(relative)) throw new Error('Proposal target outside allowed test sources');
  let cursor = absolute;
  while (cursor !== path.resolve(root)) {
    // lstat also detects broken symlinks, which existsSync would miss.
    try {
      if (fs.lstatSync(cursor).isSymbolicLink()) throw new Error('Symlink target forbidden');
    } catch (error) { if (error.code !== 'ENOENT') throw error; }
    cursor = path.dirname(cursor);
  }
  return absolute;
}
function propose(root, file, content, actor) {
  const absolute = target(root, file);
  const proposal = { id: randomUUID(), actor, status: 'pending', file: path.relative(root, absolute),
    before: fs.existsSync(absolute) ? hash(fs.readFileSync(absolute)) : null,
    source: sourceHash(root), content, digest: hash(content), createdAt: new Date().toISOString() };
  const dir = path.join(root, 'logs', 'change-proposals');
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, proposal.id + '.json'), JSON.stringify(proposal, null, 2));
  console.log(`REVIEW REQUIRED: ${proposal.id} (${proposal.file}); source unchanged`);
  return proposal;
}
// The reviewer must supply the digest of the exact candidate they inspected.
function applyReviewed(root, id, reviewer, digest) {
  if (!/^[a-f0-9-]{36}$/.test(id) || !reviewer?.trim()) throw new Error('Proposal ID and explicit reviewer required');
  const record = path.join(root, 'logs', 'change-proposals', id + '.json');
  const p = JSON.parse(fs.readFileSync(record, 'utf8')), file = target(root, p.file);
  if (p.status !== 'pending' || hash(p.content) !== p.digest || digest !== p.digest) throw new Error('Candidate differs from reviewed digest');
  if (p.source !== sourceHash(root) || p.before !== (fs.existsSync(file) ? hash(fs.readFileSync(file)) : null)) throw new Error('Source changed since proposal; regenerate and review');
  require('./generated-code').validateGenerated(p.content, file.endsWith('.feature') ? 'gherkin' : 'typescript');
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, p.content, 'utf8');
  Object.assign(p, { status: 'applied', reviewer, reviewedAt: new Date().toISOString() });
  fs.writeFileSync(record, JSON.stringify(p, null, 2));
  return p;
}
module.exports = { target, propose, applyReviewed };
