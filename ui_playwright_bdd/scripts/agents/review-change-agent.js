'use strict';
const path = require('path');
const proposals = require('./shared/change-proposals');
try {
  const [command, id, reviewer, digest] = process.argv.slice(2);
  if (command !== 'apply') throw new Error('Usage: review-change-agent.js apply <proposal-id> <reviewer> <reviewed-sha256>');
  const proposal = proposals.applyReviewed(path.join(__dirname, '..', '..'), id, reviewer, digest);
  console.log(`Applied reviewed proposal ${proposal.id}; rerun tests before final review.`);
} catch (e) { console.error(e.message); process.exitCode = 1; }
