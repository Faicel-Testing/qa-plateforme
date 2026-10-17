'use strict';
const test=require('node:test'), assert=require('node:assert/strict');
const fs=require('node:fs'), path=require('node:path'), os=require('node:os');
const {snapshot,statusFor,syncResults}=require('../shared/plane-results');
const {plan,SOURCE}=require('../shared/plane-testcases');
function fixture(t){
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'plane-results-')); t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
 const source=path.resolve(__dirname,'../../..');
 for(const dir of ['docs','src/features','results']) fs.mkdirSync(path.join(root,dir),{recursive:true});
 for(const name of ['JIRA_TRACEABILITY.md','SPEC_REPORT.md']) fs.copyFileSync(path.join(source,'docs',name),path.join(root,'docs',name));
 for(const name of fs.readdirSync(path.join(source,'src/features'))) if(name.endsWith('.feature')) fs.copyFileSync(path.join(source,'src/features',name),path.join(root,'src/features',name));
 const dir=path.join(root,'results'); const manifest={runId:'test-run',startedAt:10000,finishedAt:20000,completed:true,resultCount:1,tags:'@smoke'};
 fs.writeFileSync(path.join(dir,'run-manifest.json'),JSON.stringify(manifest));
 fs.writeFileSync(path.join(dir,'one-result.json'),JSON.stringify({fullName:'src/features/Id01_SignupTest.feature#Id01_SignupTest - user can signup successfully',status:'passed',start:11000,stop:19000}));
 return {root,dir,manifest};
}
test('absent, skipped, broken and retries never become false passes',()=>{
 assert.equal(statusFor([]),'NOT_RUN'); assert.equal(statusFor(['passed']),'PASS');
 assert.equal(statusFor(['failed','passed']),'FAILED'); assert.equal(statusFor(['passed','broken']),'ERROR');
 assert.equal(statusFor(['unknown']),'ERROR'); assert.equal(statusFor(['skipped']),'SKIPPED');
});
test('incomplete, stale and mismatched results are refused',t=>{
 const {dir,manifest}=fixture(t); assert.equal(snapshot(dir).groups.size,1);
 for(const patch of [{completed:false},{resultCount:2},{startedAt:30000}]){
 fs.writeFileSync(path.join(dir,'run-manifest.json'),JSON.stringify({...manifest,...patch})); assert.throws(()=>snapshot(dir)); }
});
test('sync preserves work states and manual labels/content; replay is idempotent and old runs blocked',async t=>{
 const {root,dir}=fixture(t); const rows=plan(root), labels=[{id:'manual',name:'Manual'}];
 const items=rows.map((r,i)=>({id:'case-'+i,external_source:SOURCE,external_id:r.externalId,state:'in-progress',labels:['manual'],description_html:'<p>Manual notes</p>'}));
 let patches=0;
 const plane={list:async route=>structuredClone(route==='labels/'?labels:items), request:async(route,method,body)=>{
  if(route==='labels/'){const label={...body,id:'label-'+labels.length};labels.push(label);return label;}
  const item=items.find(i=>route===`work-items/${i.id}/`);assert.ok(item);
  if(!method)return structuredClone(item);
  assert.equal(method,'PATCH');assert.equal(body.state,undefined);patches++;Object.assign(item,body);return structuredClone(item);
 }};
 const report=await syncResults(plane,dir,{apply:true,root});assert.equal(report.counts.PASS,1);assert.equal(report.counts.NOT_RUN,37);
 assert.ok(items.every(i=>i.state==='in-progress'&&i.labels.includes('manual')&&i.description_html.includes('Manual notes')));
 const before=patches;await syncResults(plane,dir,{apply:true,root});assert.equal(patches,before);
 items[0].description_html='<p>QA_RUN_TIMESTAMP:999999</p>';
 await assert.rejects(syncResults(plane,dir,{apply:true,root}),/older run/);
});
