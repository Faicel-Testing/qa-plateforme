'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
function load(t,fail=false){
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'planning-plane-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));const calls=[],output=[];
 const client={request:async()=>{calls.push('connect');if(fail)throw Error('Plane HTTP 401');return {name:'Application_Test',identifier:'APPLICATIO'};},fetchStories:async()=>{calls.push('stories');return [];},list:async route=>{calls.push(route);return route==='work-items/'?[{external_source:'ui_playwright_bdd_testcase',sequence_id:2,name:'Test',parent:'story'},{external_source:'ui_playwright_bdd',name:'Story'}]:[];}};
 const deps={dotenv:{config(){}},'./llm':{},'./shared/tracer':{},'./plane-fetcher':{client:()=>client},'./shared/agent-verifier':{createVerifier:()=>({})},'./shared/plane-testcases':{SOURCE:'ui_playwright_bdd_testcase'}};
 const module={exports:{}};vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../planning-agent.js'),'utf8'),{module,__dirname:path.join(root,'scripts/agents'),process:{env:{STORY_PROVIDER:'jira'},argv:['node','planning-agent.js']},console:{log:x=>output.push(x)},require:n=>{assert.ok(!n.includes('jira'));return deps[n]||require(n);}});
 return {api:module.exports,calls,output};
}
test('Planning exclusively uses Plane even with a stale Jira provider setting',async t=>{const {api,calls,output}=load(t);await api.cmdStories();await api.cmdTestCases();await api.cmdCycles('list');assert.deepEqual(calls,['connect','stories','connect','work-items/','connect','cycles/']);assert.ok(output.some(x=>x.includes('Application_Test')));assert.ok(output.some(x=>x.includes('"Test"')&&!x.includes('"Story"')));});
test('Plane connection failure propagates without fallback or false success',async t=>{const {api,calls}=load(t,true);await assert.rejects(api.cmdStories(),/401/);assert.deepEqual(calls,['connect']);});
test('unsupported legacy sprint mutations never access a remote API',async t=>{const {api,calls}=load(t);await assert.rejects(api.cmdCycles('start'),/cycles list/);assert.equal(calls.length,0);});
for(const dry of [false,true])test('Reporting sync uses Plane and preserves dry-run='+dry,async t=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'report-plane-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));let call;
 const client={};const deps={dotenv:{config(){}},'./llm':{},'./shared/tracer':{},'./shared/prompt-store':{},'./shared/agent-verifier':{createVerifier:()=>({})},'./shared/pipeline-runtime':{resultDirectory:()=>path.join(root,'results')},'./plane-fetcher':{client:()=>client},'./shared/plane-results':{syncResults:async(...args)=>{call=args;return {verified:true};}}};
 const module={exports:{}};vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../reporting-agent.js'),'utf8'),{module,__dirname:path.join(root,'scripts/agents'),process:{env:{},argv:['node','reporting-agent.js',...(dry?['--dry-run']:[])]},console:{log(){}},require:n=>deps[n]||require(n)});
 await module.exports.cmdSync();assert.equal(call[0],client);assert.equal(call[1],path.join(root,'results'));assert.equal(call[2].apply,!dry);
 deps['./shared/plane-results'].syncResults=async()=>{throw Error('Plane unavailable');};await assert.rejects(module.exports.cmdSync(),/Plane unavailable/);
});
