const { When, Then } = require('@badeball/cypress-cucumber-preprocessor');
const { BasePage } = require('../support/pages/BasePage');

When('I logout from the application', function () {
  new BasePage().logout();
});

When('I refresh the page', function () {
  new BasePage().refresh();
});

Then('I should be redirected to the login page', function () {
  new BasePage().assertOnLoginPage();
});

Then('I should see an invalid email error', function () {
  new BasePage().assertErrorMessage(/invalid email|email.*invalid|adresse.*mail|email/i);
});

Then('I should see a required field error for email', function () {
  new BasePage().assertErrorMessage(/please insert.*email|email.*format|email.*required|required.*email|email is required/i);
});

Then('I should see a required field error for password', function () {
  new BasePage().assertErrorMessage(/password.*minimum|minimum.*character|password must be|password.*required|required.*password|password is required/i);
});

Then('I should see required field errors', function () {
  new BasePage().assertErrorMessage(/required|please enter|requis|please insert|minimum.*character|password must be/i);
});
