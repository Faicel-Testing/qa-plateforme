import { expect, type Locator, type Page } from '@playwright/test';
import { BasePage } from './BasePage';

export class ProfilePage extends BasePage {
  readonly currentPasswordInput: Locator;
  readonly newPasswordInput: Locator;
  readonly confirmPasswordInput: Locator;
  readonly updatePasswordBtn: Locator;

  readonly newEmailInput: Locator;
  readonly updateEmailBtn: Locator;

  readonly deleteAccountBtn: Locator;
  readonly confirmDeleteBtn: Locator;
  readonly cancelDeleteBtn: Locator;

  constructor(page: Page) {
    super(page);

    this.currentPasswordInput = page
      .getByTestId('current-password')
      .or(page.locator('input[name="currentPassword"]'))
      .or(page.getByLabel(/current password/i))
      .first();

    this.newPasswordInput = page
      .getByTestId('new-password')
      .or(page.locator('input[name="newPassword"]'))
      .or(page.getByLabel(/new password/i))
      .first();

    this.confirmPasswordInput = page
      .getByTestId('confirm-password')
      .or(page.locator('input[name="confirmPassword"]'))
      .or(page.getByLabel(/confirm.*password/i))
      .first();

    this.updatePasswordBtn = page
      .getByTestId('update-password')
      .or(page.getByRole('button', { name: /update password|change password/i }))
      .first();

    this.newEmailInput = page
      .getByTestId('new-email')
      .or(page.locator('input[name="newEmail"]'))
      .or(page.getByLabel(/new email/i))
      .first();

    this.updateEmailBtn = page
      .getByTestId('update-email')
      .or(page.getByRole('button', { name: /update email|save email/i }))
      .first();

    this.deleteAccountBtn = page
      .getByTestId('delete-account')
      .or(page.getByRole('button', { name: /delete account|remove account/i }))
      .first();

    this.confirmDeleteBtn = page
      .getByTestId('confirm-delete')
      .or(page.getByRole('button', { name: /^(confirm|yes|delete)$/i }))
      .first();

    this.cancelDeleteBtn = page
      .getByTestId('cancel-delete')
      .or(page.getByRole('button', { name: /^(cancel|no)$/i }))
      .first();
  }

  async open(): Promise<void> {
    await this.goto('/profile');
    await this.page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
  }

  async updatePassword(currentPassword: string, newPassword: string): Promise<void> {
    await this.safeFill(this.currentPasswordInput, currentPassword);
    await this.safeFill(this.newPasswordInput, newPassword);
    await this.safeFill(this.confirmPasswordInput, newPassword);
    await this.safeClick(this.updatePasswordBtn);
    await this.page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
  }

  async updatePasswordWithWrongCurrent(wrongCurrent: string, newPassword: string): Promise<void> {
    await this.safeFill(this.currentPasswordInput, wrongCurrent);
    await this.safeFill(this.newPasswordInput, newPassword);
    await this.safeFill(this.confirmPasswordInput, newPassword);
    await this.safeClick(this.updatePasswordBtn);
    await this.page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
  }

  async updateEmail(newEmail: string): Promise<void> {
    await this.safeFill(this.newEmailInput, newEmail);
    await this.safeClick(this.updateEmailBtn);
    await this.page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
  }

  async deleteAccount(): Promise<void> {
    await this.safeClick(this.deleteAccountBtn);
    const hasConfirm = await this.confirmDeleteBtn
      .waitFor({ state: 'visible', timeout: 5_000 })
      .then(() => true)
      .catch(() => false);
    if (hasConfirm) {
      await this.safeClick(this.confirmDeleteBtn);
    }
    await this.page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
  }

  async cancelDeletion(): Promise<void> {
    await this.safeClick(this.deleteAccountBtn);
    const hasCancel = await this.cancelDeleteBtn
      .waitFor({ state: 'visible', timeout: 5_000 })
      .then(() => true)
      .catch(() => false);
    if (hasCancel) {
      await this.safeClick(this.cancelDeleteBtn);
    }
  }

  async assertPasswordUpdated(): Promise<void> {
    const success = this.page.getByText(
      /password.*updated|updated.*success|password.*changed|success/i
    );
    await expect(success.first()).toBeVisible({ timeout: 10_000 });
  }

  async assertPasswordUpdateFailed(): Promise<void> {
    await this.assertErrorMessage(/incorrect|wrong|invalid|current.*password|mismatch|error/i);
  }

  async assertEmailUpdated(): Promise<void> {
    const success = this.page.getByText(
      /email.*updated|updated.*success|email.*changed|success/i
    );
    await expect(success.first()).toBeVisible({ timeout: 10_000 });
  }

  async assertEmailUpdateFailed(): Promise<void> {
    await this.assertErrorMessage(/already.*used|taken|duplicate|invalid|error/i);
  }

  async assertAccountDeleted(): Promise<void> {
    await expect(this.page).toHaveURL(
      /login|home|\/$|signup/i,
      { timeout: 15_000 }
    );
  }

  async assertDeletionCancelled(): Promise<void> {
    await expect(this.page).toHaveURL(/profile/i, { timeout: 5_000 });
  }
}
