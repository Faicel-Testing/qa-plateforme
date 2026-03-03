import { Given, When, Then } from '@cucumber/cucumber';
import { CustomWorld } from '../hooks/world';
import { SignupPage } from '../pages/SignupPage';
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

  await signup.signup(user.name, user.email, user.password);
});

Then('I should be logged in after signup', async function (this: CustomWorld) {
  const signup = new SignupPage(this.page);
  await signup.assertSignedUp();
});

Then('I save the created user in fixture', async function (this: CustomWorld) {
  if (!this.user) throw new Error('No user generated in this scenario');
  saveUser(this.user);
});