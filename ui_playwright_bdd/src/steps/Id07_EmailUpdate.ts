import { When, Then } from '@cucumber/cucumber';
import { CustomWorld } from '../core/world';
import { ProfilePage } from '../pages/ProfilePage';

When('I update my email with a valid new address', async function (this: CustomWorld) {
  const profile = new ProfilePage(this.page);
  const newEmail = `updated_${Date.now()}@mail.com`;
  this.newEmail = newEmail;
  await profile.updateEmail(newEmail);
});

When('I update my email with an already registered address', async function (this: CustomWorld) {
  const profile = new ProfilePage(this.page);
  // Re-use the same email (current user email) — guaranteed duplicate
  const currentEmail = this.user?.email;

  if (!currentEmail) {
    throw new Error('No user email in World context — ensure fixture user is loaded');
  }

  await profile.updateEmail(currentEmail);
});

Then('an email error message should be displayed', async function (this: CustomWorld) {
  const profile = new ProfilePage(this.page);
  await profile.assertEmailUpdateFailed();
});
