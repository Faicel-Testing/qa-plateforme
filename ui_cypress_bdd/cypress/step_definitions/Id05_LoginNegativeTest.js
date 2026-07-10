const { When, Then } = require('@badeball/cypress-cucumber-preprocessor');
const { LoginPage } = require('../support/pages/LoginPage');
const { QACartApiClient } = require('../support/api/QACartApiClient');
const { randomUser } = require('../support/testData');

// Créé via API (pas de cache disque partagé) — isolé par scénario, parallel-safe
function ensureValidUser(ctx) {
  if (ctx.user) return;
  const user = randomUser();
  const api = new QACartApiClient();
  api.register(user).then((token) => {
    ctx.apiToken = token;
    ctx.user = user;
    // cy.request() partage le cookie jar : on nettoie pour retomber sur le vrai formulaire de login
    cy.clearCookies();
    cy.clearLocalStorage();
  });
}

When('I login with invalid credentials', function () {
  new LoginPage().login('invalid-user@mail.com', 'WrongPassword123');
});

When('I login with invalid email format', function () {
  new LoginPage().login('invalid-email', 'Password123!');
});

When('I login with correct email and wrong password', function () {
  const ctx = this;
  ensureValidUser(ctx);
  cy.then(() => {
    const user = ctx.user;
    if (!user) {
      throw new Error('No fixture user available for login');
    }
    new LoginPage().login(user.email, 'WrongPassword!');
  });
});

When('I login with non-existent email', function () {
  const email = `missing-${Date.now()}@mail.com`;
  new LoginPage().login(email, 'Password123!');
});

When('I login with empty email', function () {
  new LoginPage().login('', 'Password123!');
});

When('I login with empty password', function () {
  new LoginPage().login('user@example.com', '');
});

When('I login with both fields empty', function () {
  new LoginPage().login('', '');
});

Then('I should see a login error message', function () {
  new LoginPage().assertLoginError();
});

Then('I should see an authentication error message', function () {
  new LoginPage().assertLoginError();
});

Then('I should see a user not found error', function () {
  new LoginPage().assertLoginError();
});
