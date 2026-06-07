import { Given, When, Then } from '@cucumber/cucumber';
import { CustomWorld } from '../core/world';
import { loadUser, saveUser } from '../support/fixtureStore';
import { LoginPage } from '../pages/Id02_LoginPage';
import { SignupPage } from '../pages/Id01_SignupPage';
import { randomUser } from '../support/testData';

async function ensureValidFixtureUser(world: CustomWorld): Promise<void> {
  let user = loadUser();

  if (user) {
    world.user = user;
    return;
  }

  const newUser = randomUser();
  world.user = newUser;
  const signup = new SignupPage(world.page);

  await signup.open();
  await signup.signup(newUser.firstName, newUser.lastName, newUser.email, newUser.password);
  await signup.assertSignedUp();
  saveUser(newUser);
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