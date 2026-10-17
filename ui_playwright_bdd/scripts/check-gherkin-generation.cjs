'use strict';
require('dotenv').config({quiet:true});
(async()=>{
 const call=require('./agents/shared/ai-gateway').gatewayFetch('groq');
 const prompt='Test synthétique indépendant du projet : une lampe fictive passe de éteinte à allumée après pression du bouton. Générer un seul scénario sur ce comportement et aucune autre règle.\n'+require('./agents/shared/gherkin-contract').contract('DEMO-1');
 const response=await call('https://api.groq.com/openai/v1/chat/completions',{method:'POST',headers:{Authorization:'Bearer '+process.env.GROQ_API_KEY,'Content-Type':'application/json'},body:JSON.stringify({model:process.env.GROQ_MODEL||'openai/gpt-oss-120b',messages:[{role:'user',content:prompt}],max_completion_tokens:1024})});
 if(!response.ok)throw Error('Groq HTTP '+response.status);
 const result=await response.json();const content=result.choices?.[0]?.message?.content;
 require('./agents/shared/generated-code').validateGenerated(content,'gherkin');
 console.log(JSON.stringify({synthetic:true,projectDataSent:false,gherkinSyntax:'PASS',finishReason:result.choices[0].finish_reason}));
})().catch(e=>{console.error(e.message);process.exitCode=1;});
