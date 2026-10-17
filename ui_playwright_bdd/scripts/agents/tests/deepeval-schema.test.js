'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { responseFormat } = require('../../deepeval-judge');
test('judge schema preserves optional fields and references required by DeepEval', () => {
  const original = { type: 'object', properties: { verdicts: { type: 'array', items: { $ref: '#/$defs/Verdict' } } },
    $defs: { Verdict: { type: 'object', properties: { reason: { anyOf: [{ type: 'string' }, { type: 'null' }], default: null } } } } };
  const result = responseFormat('openai/gpt-oss-120b', original);
  assert.equal(result.type, 'json_schema');
  assert.equal(result.json_schema.strict, false);
  assert.deepEqual(result.json_schema.schema, original);
  assert.equal(result.json_schema.schema.$defs.Verdict.required, undefined);
  assert.deepEqual(responseFormat('other-model', original), { type: 'json_object' });
});
