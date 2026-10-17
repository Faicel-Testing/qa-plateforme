'use strict';
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const { scenarios } = require('./agents/shared/plane-testcases');
const root = path.resolve(__dirname, '..');
const escape = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const features = fs.readdirSync(path.join(root,'src/features')).filter(f=>f.endsWith('.feature')).sort().map(f=>'src/features/'+f);
const documents = ['docs/SPEC_REPORT.md','docs/JIRA_TRACEABILITY.md','docs/todo-validation.md'];
const sources = [...documents,...features].map(file=>({file,text:fs.readFileSync(path.join(root,file),'utf8')}));
for (const s of sources) if (/(?:ATATT|gsk_|plane_api_)[A-Za-z0-9_-]{12,}|-----BEGIN .*PRIVATE KEY-----/i.test(s.text)) throw Error('Potential secret detected; export stopped');
const count = features.flatMap(f=>scenarios(f,root)).length;
let html = '<h1>UI Playwright BDD — QACart Todo</h1><h2>1. Objet et périmètre</h2><p>Spécification documentaire importée du framework ui_playwright_bdd : inscription, connexion, création et suppression de tâches, validations négatives et préparation API.</p>';
html += `<p>Couverture source : ${features.length} fichiers Gherkin, ${count} scénarios. Cette publication ne lance aucun test et ne constitue pas une validation métier ou un résultat PASS.</p>`;
html += '<h2>2. Lecture des exigences</h2><ul><li>Les scénarios Gherkin ci-dessous décrivent les comportements attendus et leurs préconditions.</li><li>La règle cible Todo est de 1 à 200 caractères après suppression des espaces aux extrémités. Elle ne prouve pas la conformité actuelle de QACart.</li><li>Le rapport historique SPEC_REPORT décrit les évolutions mot de passe, email et suppression de compte ; aucune feature correspondante ne figure dans les neuf fichiers actuels.</li><li>Les références Jira et leurs états sont des informations historiques conservées depuis les documents locaux. SCRUM-9 et SCRUM-6 recouvrent la connexion ; SCRUM-2 reste à clarifier.</li></ul>';
html += '<h2>3. Documents de spécification originaux</h2><p>Les documents sont conservés intégralement ci-dessous, au format Markdown source, avec leurs dates et réserves.</p>';
const markers=[];
for (const s of sources) {
 if (s.file===features[0]) html += '<h2>4. Spécification exécutable — Features Gherkin</h2><p>Ordre des fichiers du framework ; Background, tags et étapes conservés intégralement.</p>';
 markers.push(s.file);
 html += `<h3>${escape(s.file)}</h3><pre>${escape(s.text)}</pre>`;
}
html += '<h2>5. Provenance de la publication</h2><p>Copie ponctuelle des sources locales ; aucune synchronisation automatique Confluence activée.</p><ul>';
for (const s of sources) html += `<li>${escape(s.file)} — SHA-256 : ${crypto.createHash('sha256').update(s.text).digest('hex')}</li>`;
html += '</ul>';
const dir=path.join(root,'logs/confluence');fs.mkdirSync(dir,{recursive:true});
fs.writeFileSync(path.join(dir,'spec-payload.json'),JSON.stringify({title:'UI Playwright BDD — Spécification du projet QACart Todo',html,markers},null,2));
fs.writeFileSync(path.join(dir,'spec-preview.html'),'<!doctype html><meta charset="utf-8">'+html);
console.log(JSON.stringify({documents:documents.length,features:features.length,scenarios:count,characters:html.length}));
