import { expect, type Locator, type Page } from '@playwright/test';
import { BasePage } from './BasePage';

export class LoginPage extends BasePage {
  readonly emailInput: Locator;
  readonly passwordInput: Locator;
  readonly loginBtn: Locator;

  constructor(page: Page) {
    super(page);

    this.emailInput = page.getByTestId('email');
    this.passwordInput = page.getByTestId('password');
    this.loginBtn = page.getByTestId('submit');
  }

  async open(): Promise<void> {
    await this.goto('/login');

    await expect(this.emailInput.or(this.page.locator('button:has(svg[data-testid="add"])')).first())
      .toBeVisible({ timeout: 10000 });
  }

  async login(email: string, password: string): Promise<void> {
    await this.emailInput.waitFor({ state: 'visible', timeout: 10000 });
    await this.emailInput.fill(email);
    await this.passwordInput.waitFor({ state: 'visible', timeout: 5000 });
    await this.passwordInput.fill(password);
    await this.loginBtn.waitFor({ state: 'visible', timeout: 5000 });
    await this.loginBtn.click();
    // The caller asserts the expected outcome (dashboard or validation error).
    // Background requests must not delay a ready UI or swallow a timeout.
  }

  async assertLoggedIn(): Promise<void> {
    await expect(this.page).toHaveURL(/todo|tasks|home|dashboard/i, { timeout: 10000 });
    await expect(this.page.locator('button:has(svg[data-testid="add"])')).toBeVisible({ timeout: 10000 });
  }

  async assertLoginError(): Promise<void> {
    const errorLocator = this.page.locator('.MuiAlert-message, .MuiFormHelperText-root.Mui-error').or(
      this.page.getByText(/not correct|combination.*not|invalid|wrong|could not find|incorrect|email.*password|required|please/i)
    );
    await expect(errorLocator.first()).toBeVisible({ timeout: 15000 });
  }
}
