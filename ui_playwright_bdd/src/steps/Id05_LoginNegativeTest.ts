import { When, Then } from '@cucumber/cucumber';
import { CustomWorld } from '../core/world';
import { LoginPage } from '../pages/Id02_LoginPage';
import { QACartApiClient } from '../api/QACartApiClient';
import { randomUser } from '../support/testData';

// Créé via API (pas de cache disque partagé) — isolé par scénario, parallel-safe
async function ensureValidUser(world: CustomWorld): Promise<void> {
  if (world.user) {
    return;
  }

  const user = randomUser();
  const api = new QACartApiClient();
  world.apiToken = await api.register(user);
  world.user = user;
}

When('I login with invalid credentials', async function (this: CustomWorld) {
  const login = new LoginPage(this.page);
  await login.login('invalid-user@mail.com', 'WrongPassword123');
});

When('I login with invalid email format', async function (this: CustomWorld) {
  const login = new LoginPage(this.page);
  await login.login('invalid-email', 'Password123!');
});

When('I login with correct email and wrong password', async function (this: CustomWorld) {
  await ensureValidUser(this);
  const login = new LoginPage(this.page);
  const user = this.user;

  if (!user) {
    throw new Error('No fixture user available for login');
  }

  await login.login(user.email, 'WrongPassword!');
});

When('I login with non-existent email', async function (this: CustomWorld) {
  const login = new LoginPage(this.page);
  const email = `missing-${Date.now()}@mail.com`;
  await login.login(email, 'Password123!');
});

When('I login with empty email', async function (this: CustomWorld) {
  const login = new LoginPage(this.page);
  await login.login('', 'Password123!');
});

When('I login with empty password', async function (this: CustomWorld) {
  const login = new LoginPage(this.page);
  await login.login('user@example.com', '');
});

When('I login with both fields empty', async function (this: CustomWorld) {
  const login = new LoginPage(this.page);
  await login.login('', '');
});

Then('I should see a login error message', async function (this: CustomWorld) {
  const login = new LoginPage(this.page);
  await login.assertLoginError();
});

Then('I should see an authentication error message', async function (this: CustomWorld) {
  const login = new LoginPage(this.page);
  await login.assertLoginError();
});

Then('I should see a user not found error', async function (this: CustomWorld) {
  const login = new LoginPage(this.page);
  await login.assertLoginError();
});
