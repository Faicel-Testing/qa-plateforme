import { When, Then } from '@cucumber/cucumber';
import { CustomWorld } from '../core/world';
import { BasePage } from '../pages/BasePage';

When('I logout from the application', async function (this: CustomWorld) {
  const basePage = new BasePage(this.page);
  await basePage.logout();
});

When('I refresh the page', async function (this: CustomWorld) {
  const basePage = new BasePage(this.page);
  await basePage.refresh();
});

Then('I should be redirected to the login page', async function (this: CustomWorld) {
  const basePage = new BasePage(this.page);
  await basePage.assertOnLoginPage();
});

Then('I should see an invalid email error', async function (this: CustomWorld) {
  const basePage = new BasePage(this.page);
  await basePage.assertErrorMessage(/invalid email|email.*invalid|adresse.*mail|email/i);
});

Then('I should see a required field error for email', async function (this: CustomWorld) {
  const basePage = new BasePage(this.page);
  await basePage.assertErrorMessage(/please insert.*email|email.*format|email.*required|required.*email|email is required/i);
});

Then('I should see a required field error for password', async function (this: CustomWorld) {
  const basePage = new BasePage(this.page);
  await basePage.assertErrorMessage(/password.*minimum|minimum.*character|password must be|password.*required|required.*password|password is required/i);
});

Then('I should see required field errors', async function (this: CustomWorld) {
  const basePage = new BasePage(this.page);
  await basePage.assertErrorMessage(/required|please enter|requis|please insert|minimum.*character|password must be/i);
});
