const { Given, When, Then } = require('@badeball/cypress-cucumber-preprocessor');
const { QACartApiClient } = require('../support/api/QACartApiClient');
const { TodoPage } = require('../support/pages/TodoPage');
const { randomUser } = require('../support/testData');

Given('I have a user created via API', function () {
  const ctx = this;
  const user = randomUser();
  const api = new QACartApiClient();

  api.register(user).then((token) => {
    ctx.user = user;
    ctx.apiToken = token;

    // Proof of REST call visible in CI logs and Allure report
    cy.log(`[API Setup] User created: ${user.email}`);
    cy.log(`[API Setup] Token: ${token.substring(0, 30)}...`);

    // cy.request() partage le cookie jar : on nettoie pour retomber sur le vrai formulaire de login
    // (et pour que le scénario "unauthenticated" soit réellement non authentifié, pas juste vide par hasard)
    cy.clearCookies();
    cy.clearLocalStorage();
  });
});

When('I navigate directly to the todo page', function () {
  cy.visit('/todo');
});

Then('I should see an empty todo list', function () {
  new TodoPage().assertEmptyList();
});
