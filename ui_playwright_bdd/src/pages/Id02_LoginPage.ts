import { expect, type Locator, type Page } from '@playwright/test';
import { BasePage } from './BasePage';

export class LoginPage extends BasePage {
  readonly emailInput: Locator;
  readonly passwordInput: Locator;
  readonly loginBtn: Locator;

  constructor(page: Page) {
    super(page);

    this.emailInput = page
      .getByTestId('email')
      .or(page.locator('input[name="email"]'))
      .or(page.getByPlaceholder(/email/i))
      .or(page.getByLabel(/email/i))
      .first();

    this.passwordInput = page
      .getByTestId('password')
      .or(page.locator('input[name="password"]'))
      .or(page.getByPlaceholder(/password/i))
      .or(page.getByLabel(/^password$/i))
      .first();

    this.loginBtn = page
      .getByTestId('submit')
      .or(page.getByRole('button', { name: /login|sign in/i }))
      .first();
  }

  async open(): Promise<void> {
    await this.goto('/login');

    await Promise.race([
      this.emailInput.waitFor({ state: 'visible', timeout: 10000 }),
      this.page.waitForURL(/todo|tasks|home|dashboard/i, { timeout: 10000 })
    ]);
  }

  async login(email: string, password: string): Promise<void> {
    await this.emailInput.waitFor({ state: 'visible', timeout: 10000 });
    await this.emailInput.fill(email);
    await this.passwordInput.waitFor({ state: 'visible', timeout: 5000 });
    await this.passwordInput.fill(password);
    await this.loginBtn.waitFor({ state: 'visible', timeout: 5000 });
    await Promise.all([
      this.loginBtn.click(),
      this.page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: 10000 }).catch(() => {})
    ]);
  }

  async assertLoggedIn(): Promise<void> {
    await expect(this.page).toHaveURL(/todo|tasks|home|dashboard/i, { timeout: 10000 });
    await expect(this.page.locator('button:has(svg[data-testid="add"])')).toBeVisible({ timeout: 10000 });
  }

  async assertLoginError(): Promise<void> {
    const errorLocator = this.page.locator('.MuiAlert-message, .MuiFormHelperText-root.Mui-error').or(
      this.page.getByText(/not correct|combination.*not|invalid|wrong|could not find|incorrect|email.*password/i)
    );
    await expect(errorLocator.first()).toBeVisible({ timeout: 10000 });
  }
}
