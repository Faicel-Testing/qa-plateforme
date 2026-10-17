'use strict';
require('dotenv').config({quiet:true});
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
(async()=>{
 const result=await require('./agents/shared/hybrid-rag').search(root,'RG-TODO-001 limite cible tâche 200 caractères après suppression espaces',{strict:true,env:{...process.env,RAG_RERANK_ENABLED:'false'}});
 const sources=result.hits.filter(h=>h.kind==='confluence-unapproved');
 if(!sources.some(h=>h.provenance.pageId==='262382'&&h.text.includes('200')))throw Error('Expected Confluence rule not retrieved');
 const report={mode:result.mode,reranking:result.reranking.status,hits:sources.map(h=>({path:h.path,provenance:h.provenance})),verified:true};
 fs.writeFileSync(path.join(root,'logs/confluence/rag-check.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
})().catch(e=>{console.error(e.message);process.exitCode=1;});
