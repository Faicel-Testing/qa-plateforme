const { Given, When, Then } = require('@badeball/cypress-cucumber-preprocessor');
const { LoginPage } = require('../support/pages/LoginPage');
const { QACartApiClient } = require('../support/api/QACartApiClient');
const { randomUser } = require('../support/testData');

// Créé via API (pas de cache disque partagé) — isolé par scénario, parallel-safe
function ensureValidFixtureUser(ctx) {
  if (ctx.user) return;
  const newUser = randomUser();
  const api = new QACartApiClient();
  api.register(newUser).then((token) => {
    ctx.apiToken = token;
    ctx.user = newUser;
    // cy.request() partage le cookie jar du navigateur : l'API register peut poser un
    // cookie de session qui ferait sauter l'écran de login (redirection auto vers /todo).
    // On le nettoie pour tester le vrai formulaire de login.
    cy.clearCookies();
    cy.clearLocalStorage();
  });
}

Given('I have a user in fixture', function () {
  ensureValidFixtureUser(this);
});

Given('I open the login page', function () {
  new LoginPage().open();
});

When('I login using fixture user', function () {
  const ctx = this;
  cy.then(() => {
    const user = ctx.user;
    if (!user) {
      throw new Error('User not found in scenario context');
    }
    const login = new LoginPage();
    login.login(user.email, user.password);
    login.assertLoggedIn();
  });
});

Then('I should be logged in', function () {
  new LoginPage().assertLoggedIn();
});
