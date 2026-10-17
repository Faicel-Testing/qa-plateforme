'use strict';
require('dotenv').config({quiet:true});
const path=require('node:path'),bridge=require('./agents/shared/confluence-rag');
const root=path.resolve(__dirname,'..');
(async()=>{
 if(process.argv[2]==='sync')console.log(JSON.stringify(await bridge.sync(root),null,2));
 else if(process.argv[2]==='status'){const s=bridge.snapshot(root);console.log(JSON.stringify({status:s.status,syncedAt:s.syncedAt,pages:s.pages.map(({id,title,version,status,url})=>({id,title,version,status,url}))},null,2));}
 else throw Error('Usage: confluence-rag.cjs sync | status');
})().catch(e=>{console.error(e.message);process.exitCode=1;});
