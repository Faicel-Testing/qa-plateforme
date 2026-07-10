require('allure-cypress');

// Ignore les erreurs applicatives non gérées (SPA React) pour ne pas faire
// échouer les tests sur des erreurs tierces sans rapport avec le scénario.
Cypress.on('uncaught:exception', () => false);
