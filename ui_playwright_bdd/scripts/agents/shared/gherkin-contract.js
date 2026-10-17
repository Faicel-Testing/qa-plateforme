'use strict';
// Keep grammar independent of the natural language used in titles and steps.
const CONTRACT = `CONTRAT DE SORTIE GHERKIN (obligatoire) :
- Un seul fichier, une seule Feature. Texte brut, sans JSON, Markdown ni commentaire explicatif hors du fichier.
- Dialecte anglais uniquement : Feature:, Background:, Scenario:, Scenario Outline:, Examples:, Given, When, Then, And, But.
- Les titres et le texte APRÈS les mots-clés peuvent être français. Ne pas employer Fonctionnalité, Scénario, Soit, Étant donné, Quand, Alors ou Et comme mots-clés. Ne pas ajouter # language: fr.
- Placer les tags communs @{us_key_lower} @regression AVANT Feature:.
- Background: est optionnel et ne porte JAMAIS de tags. Aucun bloc @tag ne doit le précéder après Feature:.
- Les autres tags sont autorisés uniquement avant Scenario: ou Scenario Outline: (ou Examples:).
- Chaque scénario contient des étapes ; un Scenario Outline utilise des Examples cohérents.
- Ne pas inventer de règle ou multiplier les scénarios pour atteindre un quota arbitraire. Une proposition reste soumise à validation humaine.
Exemple de structure uniquement (remplacer le besoin fictif par les exigences fournies) :
@{us_key_lower} @regression
Feature: Comportement documenté
  Background:
    Given une précondition documentée
  Scenario: Résultat attendu documenté
    When une action documentée est effectuée
    Then le résultat documenté est observé`;
function contract(key) { return CONTRACT.replaceAll('{us_key_lower}', String(key).toLowerCase()); }
module.exports = { contract };
