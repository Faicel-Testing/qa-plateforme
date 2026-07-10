const { Given, When, Then } = require('@badeball/cypress-cucumber-preprocessor');
const { SignupPage } = require('../support/pages/SignupPage');
const { randomUser } = require('../support/testData');

Given('I open the signup page', function () {
  new SignupPage().open();
});

When('I signup with a new random user', function () {
  const user = randomUser();
  this.user = user;
  new SignupPage().signup(user.firstName, user.lastName, user.email, user.password);
});

Then('I should be logged in after signup', function () {
  new SignupPage().assertSignedUp();
});

Then('I save the created user in fixture', function () {
  // Utilisateur déjà scopé au contexte Mocha (this.user) — pas de cache disque partagé (parallel-safe)
  if (!this.user) {
    throw new Error('No user generated');
  }
});
