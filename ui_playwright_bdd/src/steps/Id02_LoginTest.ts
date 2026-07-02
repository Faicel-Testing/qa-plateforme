import { Given, When, Then } from '@cucumber/cucumber';
import { CustomWorld } from '../core/world';
import { LoginPage } from '../pages/Id02_LoginPage';
import { QACartApiClient } from '../api/QACartApiClient';
import { randomUser } from '../support/testData';

// Créé via API (pas de cache disque partagé) — isolé par scénario, parallel-safe
async function ensureValidFixtureUser(world: CustomWorld): Promise<void> {
  if (world.user) {
    return;
  }

  const newUser = randomUser();
  const api = new QACartApiClient();
  world.apiToken = await api.register(newUser);
  world.user = newUser;
}

Given('I have a user in fixture', async function (this: CustomWorld) {
  await ensureValidFixtureUser(this);
});

Given('I open the login page', async function (this: CustomWorld) {
  const login = new LoginPage(this.page);
  await login.open();
});

When('I login using fixture user', async function (this: CustomWorld) {
  const user = this.user;

  if (!user) {
    throw new Error('User not found in World context');
  }

  const login = new LoginPage(this.page);
  await login.login(user.email, user.password);
  await login.assertLoggedIn();
});

Then('I should be logged in', async function (this: CustomWorld) {
  const login = new LoginPage(this.page);
  await login.assertLoggedIn();
});