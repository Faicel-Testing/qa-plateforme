import { Given, When, Then } from '@cucumber/cucumber';
import { CustomWorld } from '../core/world';
import { QACartApiClient } from '../api/QACartApiClient';
import { TodoPage } from '../pages/Id03_TodoPage';
import { randomUser } from '../support/testData';
import { saveUser } from '../support/fixtureStore';

Given('I have a user created via API', async function (this: CustomWorld) {
  const user = randomUser();
  const api = new QACartApiClient();
  const token = await api.register(user);

  this.user = user;
  this.apiToken = token;
  saveUser(user);

  // Proof of REST call visible in CI logs and Allure report
  console.log(`[API Setup] User created: ${user.email}`);
  console.log(`[API Setup] Token: ${token.substring(0, 30)}...`);
});

When('I navigate directly to the todo page', async function (this: CustomWorld) {
  const baseUrl = process.env.BASE_URL || 'https://qacart-todo.herokuapp.com';
  await this.page.goto(`${baseUrl}/todo`, { waitUntil: 'domcontentloaded' });
  await this.page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
});

Then('I should see an empty todo list', async function (this: CustomWorld) {
  const todo = new TodoPage(this.page);
  await todo.assertEmptyList();
});
