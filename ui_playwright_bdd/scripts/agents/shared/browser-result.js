'use strict';
const { createHash } = require('node:crypto');
function browserResult(result, browser) {
  const original = result.historyId || result.testCaseId || result.fullName || result.name || result.uuid;
  return { ...result,
    historyId: createHash('sha256').update(JSON.stringify([browser, original])).digest('hex'),
    parameters: [...(result.parameters || []).filter(p => p.name !== 'browser'), { name: 'browser', value: browser }],
    labels: [...(result.labels || []).filter(p => p.name !== 'browser'), { name: 'browser', value: browser }],
  };
}
module.exports = { browserResult };
