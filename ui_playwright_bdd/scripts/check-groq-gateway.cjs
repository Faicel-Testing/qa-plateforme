'use strict';
require('dotenv').config({quiet:true});
(async()=>{
 const call=require('./agents/shared/ai-gateway').gatewayFetch('groq');
 const response=await call('https://api.groq.com/openai/v1/chat/completions',{method:'POST',headers:{Authorization:'Bearer '+process.env.GROQ_API_KEY,'Content-Type':'application/json'},body:JSON.stringify({model:process.env.GROQ_MODEL||'openai/gpt-oss-120b',messages:[{role:'user',content:'Reply only with OK. This is a synthetic connectivity check.'}],max_completion_tokens:128})});
 if(!response.ok)throw Error('Groq HTTP '+response.status);
 const data=await response.json();if(!Array.isArray(data.choices)||!data.choices.length)throw Error('No model response');
 console.log(JSON.stringify({status:response.status,gateway:'PASS',model:data.model,synthetic:true,projectDataSent:false,tlsVerification:process.env.NODE_TLS_REJECT_UNAUTHORIZED!=='0'}));
})().catch(e=>{console.error(e.code==='AI_GATEWAY_BLOCKED'?e.message:'Synthetic gateway check failed: '+(e.cause?.code||e.name));process.exitCode=1;});
