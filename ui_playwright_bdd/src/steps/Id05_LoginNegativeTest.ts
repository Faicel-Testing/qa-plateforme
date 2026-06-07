import { When, Then } from '@cucumber/cucumber';
import { CustomWorld } from '../core/world';
import { LoginPage } from '../pages/Id02_LoginPage';
import { SignupPage } from '../pages/Id01_SignupPage';
import { loadUser, saveUser } from '../support/fixtureStore';
import { randomUser } from '../support/testData';

async function ensureValidUser(world: CustomWorld): Promise<void> {
  let user = loadUser();

  if (!user) {
    user = randomUser();
    const signup = new SignupPage(world.page);
    await signup.open();
    await signup.signup(user.firstName, user.lastName, user.email, user.password);
    await signup.assertSignedUp();
    saveUser(user);
  }

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
