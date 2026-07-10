const { When, Then } = require('@badeball/cypress-cucumber-preprocessor');
const { SignupPage } = require('../support/pages/SignupPage');
const { randomUser } = require('../support/testData');

When('I enter a valid email and mismatched passwords', function () {
  const user = randomUser();
  new SignupPage().signup(user.firstName, user.lastName, user.email, user.password, `${user.password}x`);
});

When('I enter an invalid email format', function () {
  const user = randomUser();
  new SignupPage().signup(user.firstName, user.lastName, 'invalid-email', user.password);
});

When('I signup without first name', function () {
  const user = randomUser();
  new SignupPage().signup('', user.lastName, user.email, user.password);
});

When('I signup without last name', function () {
  const user = randomUser();
  new SignupPage().signup(user.firstName, '', user.email, user.password);
});

When('I signup without email', function () {
  const user = randomUser();
  new SignupPage().signup(user.firstName, user.lastName, '', user.password);
});

When('I signup without password', function () {
  const user = randomUser();
  new SignupPage().signup(user.firstName, user.lastName, user.email, '', '');
});

When('I enter a weak password', function () {
  const user = randomUser();
  new SignupPage().signup(user.firstName, user.lastName, user.email, '123', '123');
});

Then('I should see a password mismatch error', function () {
  new SignupPage().assertSignupError(/mismatch|confirm/i);
});

Then('I should see a required field error for first name', function () {
  new SignupPage().assertSignupError(/first name|required/i);
});

Then('I should see a required field error for last name', function () {
  new SignupPage().assertSignupError(/last name|required/i);
});

Then('I should see a password strength error', function () {
  new SignupPage().assertSignupError(/weak|strength|too short|minimum/i);
});
