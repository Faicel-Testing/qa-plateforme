import { Given, When, Then } from '@cucumber/cucumber';
import { CustomWorld } from '../core/world';
import { loadUser, saveUser } from '../support/fixtureStore';
import { randomUser } from '../support/testData';
import { SignupPage } from '../pages/SignupPage';
import { LoginPage } from '../pages/LoginPage';

Given('I have a user in fixture (create one if missing)', async function (this: CustomWorld) {
  const user = loadUser();
  if (user) {
    this.user = user;
    return;
  }

  // Pas de fixture => on crée un user via signup (robuste, même si Id02 est exécuté seul)
  const newUser = randomUser();
  const signup = new SignupPage(this.page);

  await signup.open();
  await signup.signup(newUser.name, newUser.email, newUser.password);
  await signup.assertSignedUp();

  saveUser(newUser);
  this.user = newUser;
});

Given('I open the login page', async function (this: CustomWorld) {
  const login = new LoginPage(this.page);
  await login.open();
});

When('I login using fixture user', async function (this: CustomWorld) {
  if (!this.user) throw new Error('Fixture user not loaded');
  const login = new LoginPage(this.page);
  await login.login(this.user.email, this.user.password);
});

Then('I should be logged in', async function (this: CustomWorld) {
  const login = new LoginPage(this.page);
  await login.assertLoggedIn();
});