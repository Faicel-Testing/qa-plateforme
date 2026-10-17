'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const bridge=require('../shared/confluence-rag'),rag=require('../shared/rag');
function setup(t){const root=fs.mkdtempSync(path.join(os.tmpdir(),'confluence-rag-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));fs.mkdirSync(path.join(root,'config'));fs.writeFileSync(path.join(root,'config/confluence-rag.json'),JSON.stringify({baseUrl:'https://example.atlassian.net/wiki',spaceId:'1',rootPageId:'2',pageIds:['3'],refreshMinutes:15,maxAgeHours:24}));return root;}
function page(version=1,html='<h2>Validation Todo</h2><p>Limite cible : 200 caractères. Non approuvé.</p>'){return {id:'3',spaceId:'1',parentId:'2',status:'current',title:'Règles Todo',version:{number:version},body:{storage:{value:html}}};}
const fetcher=p=>async id=>id==='2'?{id:'2',spaceId:'1',status:'current'}:p;
test('Confluence passages preserve provenance and unapproved status in actual agent context',async t=>{
 const root=setup(t);await bridge.sync(root,{fetchPage:fetcher(page()),env:{}});
 const hits=rag.search(root,'limite cible caractères').hits;assert.equal(hits.length,1);assert.equal(hits[0].provenance.pageId,'3');assert.equal(hits[0].provenance.version,1);assert.equal(hits[0].provenance.documentaryStatus,'UNAPPROVED_REFERENCE');
 const messages=rag.augmentMessages([{role:'user',content:'limite cible caractères'}],{root,agent:'planning-agent'});assert.ok(messages.some(m=>m.content.includes('UNAPPROVED_REFERENCE')));assert.ok(messages.some(m=>m.content.startsWith(rag.MARKER)));
 const before=hits[0].id;await bridge.sync(root,{fetchPage:fetcher(page(2)),env:{}});assert.notEqual(rag.search(root,'limite cible caractères').hits[0].id,before);
});
test('revoked/deleted/inaccessible source invalidates previous corpus without partial publication',async t=>{
 const root=setup(t);await bridge.sync(root,{fetchPage:fetcher(page()),env:{}});
 await assert.rejects(bridge.sync(root,{fetchPage:async()=>{throw Error('Confluence HTTP 403');},env:{}}));assert.equal(rag.search(root,'limite cible caractères').hits.length,0);assert.equal(bridge.snapshot(root).status,'UNAVAILABLE_OR_STALE');
});
test('changed allowlist, expired snapshots and moved pages are excluded',async t=>{
 const root=setup(t);await bridge.sync(root,{fetchPage:fetcher(page()),env:{},now:Date.now()-25*3600000});assert.equal(rag.search(root,'limite cible caractères').hits.length,0);
 await assert.rejects(bridge.sync(root,{fetchPage:fetcher({...page(),parentId:'99'}),env:{}}));
 await bridge.sync(root,{fetchPage:fetcher(page()),env:{}});const f=path.join(root,'config/confluence-rag.json'),c=JSON.parse(fs.readFileSync(f));c.pageIds=['4'];fs.writeFileSync(f,JSON.stringify(c));assert.equal(bridge.snapshot(root).pages.length,0);
});
test('HTML conversion keeps table and preformatted text; secrets and private URLs removed before caching',async t=>{
 const root=setup(t),secret='private-long-test-secret';await bridge.sync(root,{env:{CONFLUENCE_API_TOKEN:secret},fetchPage:fetcher(page(1,'<script>evil()</script><table><tr><td>200</td><td>acceptés</td></tr></table><pre>Given user\nThen reject</pre><p>'+secret+' https://internal.invalid/path?q=secret person@example.com</p><p>'+('long '.repeat(700))+'</p>'))});
 const raw=fs.readFileSync(bridge.location(root),'utf8');assert.ok(!raw.includes(secret));assert.ok(!raw.includes('internal.invalid'));assert.ok(!raw.includes('person@example.com'));assert.ok(!raw.includes('evil()'));assert.match(raw,/200 \| acceptés/);assert.equal(rag.currentIndex(root).omittedLines.length,0);
});
test('TLS enforced, no redirects followed, no credential/error body leakage',async t=>{
 const {EventEmitter}=require('node:events'),root=setup(t),c=bridge.config(root);let calls=0;
 const get=bridge.client(c,{CONFLUENCE_EMAIL:'user',CONFLUENCE_API_TOKEN:'secret'},(opts,cb)=>{calls++;assert.equal(opts.rejectUnauthorized,true);assert.equal(opts.hostname,'example.atlassian.net');assert.equal(opts.method,'GET');const req=new EventEmitter();req.destroy=()=>req.emit('close');req.end=()=>{const res=new EventEmitter();res.statusCode=302;res.setEncoding=()=>{};cb(res);res.emit('data','secret response');res.emit('end');req.emit('close');};return req;});
 await assert.rejects(get('3'),/^Error: Confluence HTTP 302$/);await assert.rejects(get('999'),/allowlist/);assert.equal(calls,1);
});

test('page 404 with account 403 identifies product access denial and excludes old content',async t=>{
 const root=setup(t);await bridge.sync(root,{fetchPage:fetcher(page()),env:{}});
 const read=async()=>{throw Object.assign(Error('Confluence HTTP 404'),{statusCode:404,pageId:'2'});};
 read.checkAccess=async()=>{throw Object.assign(Error('private provider response SECRET'),{statusCode:403});};
 await assert.rejects(bridge.sync(root,{fetchPage:read,env:{}}),error=>error.code==='CONFLUENCE_ACCESS_DENIED'&&!error.message.includes('SECRET'));
 assert.equal(bridge.snapshot(root).pages.length,0);
 const stored=fs.readFileSync(bridge.location(root),'utf8');assert.ok(!stored.includes('SECRET'));
 assert.equal(JSON.parse(stored).diagnostic.code,'CONFLUENCE_ACCESS_DENIED');
});

test('accessible account preserves page 404; invalid credentials are distinguished',async t=>{
 const root=setup(t);
 const read=async()=>{throw Object.assign(Error('Confluence HTTP 404'),{statusCode:404,pageId:'3'});};
 read.checkAccess=async()=>({});
 await assert.rejects(bridge.sync(root,{fetchPage:read,env:{}}),/Confluence HTTP 404/);
 assert.equal(JSON.parse(fs.readFileSync(bridge.location(root),'utf8')).diagnostic.pageId,'3');
 read.checkAccess=async()=>{throw Object.assign(Error('Confluence HTTP 401'),{statusCode:401});};
 await assert.rejects(bridge.sync(root,{fetchPage:read,env:{}}),error=>error.code==='CONFLUENCE_AUTHENTICATION_FAILED');
});
