import { Given, When, Then } from '@cucumber/cucumber';
import { CustomWorld } from '../core/world';
import { ProfilePage } from '../pages/ProfilePage';
import { randomUser } from '../support/testData';

Given('I navigate to the profile page', async function (this: CustomWorld) {
  const profile = new ProfilePage(this.page);
  await profile.open();
});

When('I update my password with a valid new password', async function (this: CustomWorld) {
  const profile = new ProfilePage(this.page);
  const currentPassword = this.user?.password;

  if (!currentPassword) {
    throw new Error('No user password in World context — ensure fixture user is loaded');
  }

  const newPassword = randomUser().password;
  this.newPassword = newPassword;
  await profile.updatePassword(currentPassword, newPassword);
});

When('I update my password with an incorrect current password', async function (this: CustomWorld) {
  const profile = new ProfilePage(this.page);
  await profile.updatePasswordWithWrongCurrent('WrongCurrent!99', 'NewValid!Pass1');
});

Then('a success message should be displayed', async function (this: CustomWorld) {
  const profile = new ProfilePage(this.page);
  await profile.assertPasswordUpdated();
});

Then('a password error message should be displayed', async function (this: CustomWorld) {
  const profile = new ProfilePage(this.page);
  await profile.assertPasswordUpdateFailed();
});
