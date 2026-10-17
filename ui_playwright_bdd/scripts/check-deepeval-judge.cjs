'use strict';
// Synthetic connectivity probe: no project content is sent to the provider.
require('dotenv').config({ quiet: true });
const path = require('node:path');
const { spawnSync } = require('node:child_process');
if (process.env.NODE_EXTRA_CA_CERTS) process.env.NODE_EXTRA_CA_CERTS = path.resolve(process.env.NODE_EXTRA_CA_CERTS);
const child = spawnSync(process.execPath, ['-e', `
  require('./scripts/deepeval-judge').generate({prompt:'Return only JSON with ok set to true.',schema:{type:'object',properties:{ok:{type:'boolean'}},required:['ok'],additionalProperties:false}})
  .then(r=>console.log(JSON.stringify({ok:true,provider:r.provider,model:r.model})))
  .catch(e=>{const chain=[];for(let c=e;c&&chain.length<6;c=c.cause)chain.push({name:c.name,code:c.code||null,status:c.status||null,reason:c.reason||null});console.log(JSON.stringify({ok:false,chain}));process.exitCode=1;});
`], { cwd: path.resolve(__dirname, '..'), env: process.env, encoding: 'utf8', timeout: 100000 });
console.log(child.stdout);
if (child.error) console.log(child.error.code);
process.exitCode = child.status || (child.error ? 1 : 0);
