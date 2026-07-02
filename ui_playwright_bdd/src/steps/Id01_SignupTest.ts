import { Given, When, Then } from '@cucumber/cucumber';
import { CustomWorld } from '../core/world';
import { SignupPage } from '../pages/Id01_SignupPage';
import { randomUser } from '../support/testData';

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
  // Utilisateur déjà scopé au World (this.user) — plus de cache disque partagé (parallel-safe)
  if (!this.user) {
    throw new Error('No user generated');
  }
});