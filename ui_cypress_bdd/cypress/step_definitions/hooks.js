const { Before } = require('@badeball/cypress-cucumber-preprocessor');

// Réinitialise l'état partagé (Mocha `this`) avant chaque scénario.
// Équivalent Cypress du World.init() de ui_playwright_bdd (pas de lifecycle
// browser à gérer ici — Cypress gère son propre navigateur).
Before(function () {
  this.user = undefined;
  this.apiToken = undefined;
  this.lastTodo = undefined;
});
