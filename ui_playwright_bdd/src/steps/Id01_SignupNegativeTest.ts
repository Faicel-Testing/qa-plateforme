import { When, Then } from '@cucumber/cucumber';
import { CustomWorld } from '../core/world';
import { SignupPage } from '../pages/Id01_SignupPage';
import { randomUser } from '../support/testData';

When('I enter a valid email and mismatched passwords', async function (this: CustomWorld) {
  const signup = new SignupPage(this.page);
  const user = randomUser();

  await signup.signup(user.firstName, user.lastName, user.email, user.password, `${user.password}x`);
});

When('I enter an invalid email format', async function (this: CustomWorld) {
  const signup = new SignupPage(this.page);
  const user = randomUser();

  await signup.signup(user.firstName, user.lastName, 'invalid-email', user.password);
});

When('I signup without first name', async function (this: CustomWorld) {
  const signup = new SignupPage(this.page);
  const user = randomUser();

  await signup.signup('', user.lastName, user.email, user.password);
});

When('I signup without last name', async function (this: CustomWorld) {
  const signup = new SignupPage(this.page);
  const user = randomUser();

  await signup.signup(user.firstName, '', user.email, user.password);
});

When('I signup without email', async function (this: CustomWorld) {
  const signup = new SignupPage(this.page);
  const user = randomUser();

  await signup.signup(user.firstName, user.lastName, '', user.password);
});

When('I signup without password', async function (this: CustomWorld) {
  const signup = new SignupPage(this.page);
  const user = randomUser();

  await signup.signup(user.firstName, user.lastName, user.email, '', '');
});

When('I enter a weak password', async function (this: CustomWorld) {
  const signup = new SignupPage(this.page);
  const user = randomUser();

  await signup.signup(user.firstName, user.lastName, user.email, '123', '123');
});

Then('I should see a password mismatch error', async function (this: CustomWorld) {
  const signup = new SignupPage(this.page);
  await signup.assertSignupError(/mismatch|confirm/i);
});

Then('I should see a required field error for first name', async function (this: CustomWorld) {
  const signup = new SignupPage(this.page);
  await signup.assertSignupError(/first name|required/i);
});

Then('I should see a required field error for last name', async function (this: CustomWorld) {
  const signup = new SignupPage(this.page);
  await signup.assertSignupError(/last name|required/i);
});

Then('I should see a password strength error', async function (this: CustomWorld) {
  const signup = new SignupPage(this.page);
  await signup.assertSignupError(/weak|strength|too short|minimum/i);
});
