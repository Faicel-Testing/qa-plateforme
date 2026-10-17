import { Given, When, Then } from '@cucumber/cucumber';
import { CustomWorld } from '../core/world';
import { SignupPage } from '../pages/Id01_SignupPage';

Given('I open the signup page', async function (this: CustomWorld) {
  const signup = new SignupPage(this.page);
  await signup.open();
});

When('I signup with a new random user', async function (this: CustomWorld) {
  const signup = new SignupPage(this.page);
  const user = await this.newTestUser();

  this.user = user;
  await this.dataService?.markAttempted();

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
  await this.dataService?.markCreated();
});

Then('I save the created user in fixture', function (this: CustomWorld) {
  // Utilisateur déjà scopé au World (this.user) — plus de cache disque partagé (parallel-safe)
  if (!this.user) {
    throw new Error('No user generated');
  }
});
