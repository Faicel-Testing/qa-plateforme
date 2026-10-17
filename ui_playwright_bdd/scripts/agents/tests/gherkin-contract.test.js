'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {validateGenerated}=require('../shared/generated-code');
const {contract}=require('../shared/gherkin-contract');
test('mixed dialect and tags on Background are rejected with parser locations',()=>{
 assert.throws(()=>validateGenerated('Feature: Connexion\n @applicatio-1\n Background:\n  Given un utilisateur\n Scenario: Connexion\n  When une action\n  Then un résultat','gherkin'),/line \d+, column/);
 // Without a language directive French keywords can be parsed as description,
 // so the absence of executable scenarios must also be rejected.
 assert.throws(()=>validateGenerated('Feature: Connexion\n Background:\n  Étant donné un utilisateur\n Scénario: Connexion\n  Quand une action\n  Alors un résultat','gherkin'),/no executable scenarios/);
});
test('contract example parses with English keywords and French step text',()=>{
 const text=contract('APPLICATIO-1').split('Exemple de structure uniquement (remplacer le besoin fictif par les exigences fournies) :\n')[1];assert.doesNotThrow(()=>validateGenerated(text,'gherkin'));assert.ok(text.startsWith('@applicatio-1 @regression\nFeature:'));
});
test('empty scenarios and explanations are not accepted as executable code',()=>{
 assert.throws(()=>validateGenerated('Feature: F\n Scenario: Sans étapes','gherkin'),/without steps/);
 assert.throws(()=>validateGenerated('Il manque des exigences','gherkin'));
});
