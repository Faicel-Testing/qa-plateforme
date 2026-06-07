import { Given, When, Then } from '@cucumber/cucumber';
import { CustomWorld } from '../core/world';
import { SignupPage } from '../pages/Id01_SignupPage';
import { randomUser } from '../support/testData';
import { saveUser } from '../support/fixtureStore';

Given('I open the signup page', async function (this: CustomWorld) {
  const signup = new SignupPage(this.page);
  await signup.open();
});

When('I signup with a new random user', async function (this: CustomWorld) {
  const signup = new SignupPage(this.page);
  const user = randomUser();

  this.user = user;

  await signup.signup(
    user.firstName,
    user.lastName,
    user.email,
    user.password
  );
});

Then('I should be logged in after signup', async function (this: CustomWorld) {
  const signup = new SignupPage(this.page);
  await signup.assertSignedUp();
});

Then('I save the created user in fixture', async function (this: CustomWorld) {
  const user = this.user;

  if (!user) {
    throw new Error('No user generated');
  }

  saveUser(user as import('../support/testData').TestUser);
});