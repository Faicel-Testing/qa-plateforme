import { When, Then } from '@cucumber/cucumber';
import { CustomWorld } from '../core/world';
import { ProfilePage } from '../pages/ProfilePage';

When('I confirm account deletion', async function (this: CustomWorld) {
  const profile = new ProfilePage(this.page);
  await profile.deleteAccount();
});

When('I cancel account deletion', async function (this: CustomWorld) {
  const profile = new ProfilePage(this.page);
  await profile.cancelDeletion();
});

Then('I should be redirected to the home page', async function (this: CustomWorld) {
  const profile = new ProfilePage(this.page);
  await profile.assertAccountDeleted();
});

Then('the deletion should be cancelled and I remain on the profile page', async function (this: CustomWorld) {
  const profile = new ProfilePage(this.page);
  await profile.assertDeletionCancelled();
});
