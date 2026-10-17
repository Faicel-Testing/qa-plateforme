'use strict';
const store=require('./agents/shared/prompt-store');
const content=`Tu es un expert QA BDD. Génère un fichier .feature à partir des exigences documentées de la story Plane.
Clé Plane : {us_key}
Titre : {us_title}
Description : {us_description}
Statut : {us_status}
Génère uniquement les comportements justifiés par ces exigences. Les propositions et décisions ouvertes ne sont pas des exigences approuvées. Ne force pas un minimum de scénarios et n'invente ni limites ni messages d'erreur.
Utilise EXCLUSIVEMENT les mots-clés Gherkin ANGLAIS (Feature, Background, Scenario, Given, When, Then, And) avec des titres et descriptions en français.
Les tags @{us_key_lower} @regression précèdent Feature:. Background ne peut avoir AUCUN tag.
Réponds uniquement avec le fichier .feature brut, sans Markdown ni JSON.`;
if(store.get('tc_generate_ui')!==content)console.log('Prompt version '+store.saveVersion('tc_generate_ui',content,'Fix dialecte Gherkin anglais, tags Feature et interdiction des tags Background ; source Plane et absence de quota artificiel de scénarios.','minor'));
else console.log('Prompt already current');
