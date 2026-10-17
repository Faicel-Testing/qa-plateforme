'use strict';
const fs=require('node:fs'),path=require('node:path'),https=require('node:https');
const {createHash,randomUUID}=require('node:crypto');
const privacy=require('./payload-privacy');
const pending=new Map();
const sha=x=>createHash('sha256').update(x).digest('hex');
const location=root=>path.join(root,'.qa-rag','confluence.json');
function config(root){
 const file=path.join(root,'config/confluence-rag.json');if(!fs.existsSync(file))return null;
 const c=JSON.parse(fs.readFileSync(file,'utf8')),u=new URL(c.baseUrl);
 if(u.protocol!=='https:'||!u.hostname.endsWith('.atlassian.net')||u.port||u.username||u.password||u.pathname!=='/wiki'||u.search||u.hash||!/^\d+$/.test(c.spaceId)||!/^\d+$/.test(c.rootPageId)||!Array.isArray(c.pageIds)||!c.pageIds.length||c.pageIds.length>30||c.pageIds.some(id=>!/^\d+$/.test(id))||new Set(c.pageIds).size!==c.pageIds.length||!(c.refreshMinutes>=1&&c.refreshMinutes<=60)||!(c.maxAgeHours>=1&&c.maxAgeHours<=24))throw Error('Invalid Confluence RAG configuration');
 return c;
}
function clean(text,env){
 for(const [key,value] of Object.entries(env))if(/KEY|TOKEN|PASSWORD|SECRET|CREDENTIAL/i.test(key)&&typeof value==='string'&&value.length>=8)text=text.split(value).join('[REDACTED]');
 return privacy.cleanText(text.replace(/\b(?:ATATT|plane_api_|gsk_|sk-)[A-Za-z0-9_=.-]{12,}/g,'[REDACTED]'));
}
function textFromHtml(html){
 const entities={amp:'&',lt:'<',gt:'>',quot:'"',apos:"'",nbsp:' '};
 return html.replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi,'').replace(/<\/(?:p|h[1-6]|li|tr|pre|div|ul|ol)>|<br\s*\/?\s*>/gi,'\n').replace(/<\/(?:td|th)>/gi,' | ').replace(/<[^>]+>/g,'')
 .replace(/&(#x[0-9a-f]+|#\d+|amp|lt|gt|quot|apos|nbsp);/gi,(all,x)=>{if(x[0]!=='#')return entities[x.toLowerCase()]||all;const n=x[1].toLowerCase()==='x'?parseInt(x.slice(2),16):Number(x.slice(1));return n>0&&n<=0x10ffff?String.fromCodePoint(n):' ';})
 .split(/\r?\n/).flatMap(line=>{const out=[];while(line.length>1000){let cut=line.lastIndexOf(' ',1000);if(cut<1)cut=1000;out.push(line.slice(0,cut));line=line.slice(cut).trimStart();}out.push(line.trim());return out;}).filter(Boolean).join('\n');
}
function client(c,env=process.env,transport=https.request){
 if(!env.CONFLUENCE_EMAIL||!env.CONFLUENCE_API_TOKEN)throw Error('Confluence credentials missing');
 const host=new URL(c.baseUrl).hostname;
 const ca=env.CONFLUENCE_CA_FILE?[...require('node:tls').rootCertificates,fs.readFileSync(env.CONFLUENCE_CA_FILE,'utf8')]:undefined;
 function request(route,pageId){return new Promise((resolve,reject)=>{
  let size=0,raw='';
  const req=transport({hostname:host,port:443,path:route,method:'GET',rejectUnauthorized:true,...(ca?{ca}:{}),headers:{Accept:'application/json',Authorization:'Basic '+Buffer.from(env.CONFLUENCE_EMAIL+':'+env.CONFLUENCE_API_TOKEN).toString('base64')}},res=>{
   res.setEncoding('utf8');res.on('error',()=>reject(Error('Confluence response interrupted')));
   res.on('data',s=>{size+=Buffer.byteLength(s);if(size>1024*1024)req.destroy(Error('Confluence page too large'));else raw+=s;});
   res.on('end',()=>{if(res.statusCode!==200){const error=Error('Confluence HTTP '+res.statusCode);error.statusCode=res.statusCode;if(pageId)error.pageId=pageId;return reject(error);}try{resolve(JSON.parse(raw));}catch{reject(Error('Invalid Confluence JSON'));}});
  });
  const timer=setTimeout(()=>req.destroy(Error('Confluence deadline exceeded')),15000);
  req.on('close',()=>clearTimeout(timer));req.on('error',()=>reject(Error('Confluence request failed (network/TLS/size/deadline)')));req.end();
 });}
 const read=id=>{
  if(![c.rootPageId,...c.pageIds].includes(id))return Promise.reject(Error('Page outside Confluence allowlist'));
  return request('/wiki/api/v2/pages/'+id+'?body-format=storage',id);
 };
 // A page 404 can conceal product access denial. This fixed read-only probe
 // distinguishes that case without logging account data or response bodies.
 read.checkAccess=()=>request('/wiki/rest/api/user/current');
 return read;
}
function atomic(root,data){const file=location(root);fs.mkdirSync(path.dirname(file),{recursive:true});const temp=file+'.'+randomUUID()+'.tmp';fs.writeFileSync(temp,JSON.stringify(data));fs.renameSync(temp,file);}
async function sync(root,{env=process.env,fetchPage,now=Date.now()}={}){
 const c=config(root);if(!c)throw Error('Confluence configuration missing');
 const key=path.resolve(root);if(pending.has(key))return pending.get(key);
 const operation=(async()=>{
  const lock=location(root)+'.lock';fs.mkdirSync(path.dirname(lock),{recursive:true});let fd;
  try{fd=fs.openSync(lock,'wx');}catch{throw Error('Confluence synchronization already running');}
  let read;
  try{
   read=fetchPage||client(c,env);const parent=await read(c.rootPageId);
   if(String(parent.id)!==c.rootPageId||String(parent.spaceId)!==c.spaceId||parent.status!=='current')throw Error('Confluence root identity/status mismatch');
   const pages=[];
   for(const id of c.pageIds){
    const page=await read(id);
    if(String(page.id)!==id||String(page.spaceId)!==c.spaceId||String(page.parentId)!==c.rootPageId||page.status!=='current'||!Number.isInteger(page.version?.number)||typeof page.body?.storage?.value!=='string')throw Error('Confluence page identity/status/version mismatch');
    const text=clean(textFromHtml(page.body.storage.value),env),title=clean(String(page.title),env);
    if(!text.trim())throw Error('Empty Confluence page');
    pages.push({id,title,version:page.version.number,url:c.baseUrl+'/pages/viewpage.action?pageId='+id,status:'UNAPPROVED_REFERENCE',text,hash:sha(text)});
   }
   const data={schema:1,status:'READY',configHash:sha(JSON.stringify(c)),syncedAt:new Date(now).toISOString(),pages};atomic(root,data);
   return {status:'READY',pages:pages.length,syncedAt:data.syncedAt};
  }catch(error){
   let failure=error;
   if(error.statusCode===404&&typeof read?.checkAccess==='function'){
    try{await read.checkAccess();}catch(accessError){
     if(accessError.statusCode===403){
      const denied=Error('Confluence access denied: the configured account/token cannot access Confluence. Grant product access or configure credentials for an authorized account.');
      denied.code='CONFLUENCE_ACCESS_DENIED';denied.statusCode=403;failure=denied;
     }else if(accessError.statusCode===401){
      const invalid=Error('Confluence authentication failed: check the configured email and API token.');
      invalid.code='CONFLUENCE_AUTHENTICATION_FAILED';invalid.statusCode=401;failure=invalid;
     }
    }
   }
   const diagnostic={code:failure.code==='CONFLUENCE_ACCESS_DENIED'||failure.code==='CONFLUENCE_AUTHENTICATION_FAILED'?failure.code:'CONFLUENCE_SYNC_FAILED',
    httpStatus:Number.isInteger(failure.statusCode)?failure.statusCode:null,...(failure.pageId?{pageId:failure.pageId}:{})};
   atomic(root,{schema:1,status:'UNAVAILABLE',syncedAt:new Date(now).toISOString(),pages:[],diagnostic});throw failure;
  }
  finally{fs.closeSync(fd);fs.unlinkSync(lock);}
 })();pending.set(key,operation);try{return await operation;}finally{pending.delete(key);}
}
function snapshot(root,now=Date.now()){
 const c=config(root);if(!c)return {pages:[],status:'NOT_CONFIGURED'};
 try{const file=location(root),stat=fs.lstatSync(file),relative=path.relative(fs.realpathSync(root),fs.realpathSync(file));
  if(stat.isSymbolicLink()||stat.size>10*1024*1024||relative.startsWith('..')||path.isAbsolute(relative))return {pages:[],status:'UNAVAILABLE_OR_STALE'};
  const s=JSON.parse(fs.readFileSync(file,'utf8'));const age=now-Date.parse(s.syncedAt);
  if(s.schema!==1||s.status!=='READY'||s.configHash!==sha(JSON.stringify(c))||!Number.isFinite(age)||age<0||age>c.maxAgeHours*3600000||!Array.isArray(s.pages)||s.pages.length!==c.pageIds.length||new Set(s.pages.map(p=>p.id)).size!==c.pageIds.length||s.pages.some(p=>!c.pageIds.includes(p.id)||sha(p.text)!==p.hash||p.status!=='UNAPPROVED_REFERENCE'||p.url!==c.baseUrl+'/pages/viewpage.action?pageId='+p.id))return {pages:[],status:'UNAVAILABLE_OR_STALE'};
  return s;
 }catch{return {pages:[],status:'UNAVAILABLE_OR_STALE'};}
}
async function ensureFresh(root,env=process.env){
 if(env.CONFLUENCE_RAG_ENABLED!=='true'||!config(root))return;
 const c=config(root),s=snapshot(root);
 if(s.status==='READY'&&Date.now()-Date.parse(s.syncedAt)<c.refreshMinutes*60000)return;
 // Short cooldown after failed sync, without serving the old pages.
 try{const last=JSON.parse(fs.readFileSync(location(root),'utf8'));if(last.status==='UNAVAILABLE'&&Date.now()-Date.parse(last.syncedAt)<60000)return;}catch{}
 try{await sync(root,{env});}catch(error){
  const status=String(error.message).match(/^Confluence HTTP (\d{3})$/)?.[1];
  const reason=error.code==='CONFLUENCE_ACCESS_DENIED'?'account/token denied access to Confluence; grant product access or configure an authorized account'
   :error.code==='CONFLUENCE_AUTHENTICATION_FAILED'?'authentication failed; check configured email and API token'
    :status?`HTTP ${status}${status==='404'?' (page unavailable or not accessible; check configured page IDs and permissions)':''}`:'network, TLS, credentials or configuration';
  console.warn(`[Confluence RAG] Sync unavailable: ${reason}; Confluence context excluded.`);
 }
}
module.exports={config,client,clean,textFromHtml,sync,snapshot,ensureFresh,location};
