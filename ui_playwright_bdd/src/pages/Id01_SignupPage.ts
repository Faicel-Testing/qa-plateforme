import { expect, type Locator, type Page } from '@playwright/test';
import { BasePage } from './BasePage';

export class SignupPage extends BasePage {
  readonly firstNameInput: Locator;
  readonly lastNameInput: Locator;
  readonly emailInput: Locator;
  readonly passwordInput: Locator;
  readonly confirmPasswordInput: Locator;
  readonly signupBtn: Locator;

  constructor(page: Page) {
    super(page);

    this.firstNameInput = page
      .getByTestId('first-name')
      .or(page.locator('input[name="firstName"]'))
      .or(page.getByPlaceholder(/first name/i))
      .or(page.getByLabel(/first name/i))
      .first();

    this.lastNameInput = page
      .getByTestId('last-name')
      .or(page.locator('input[name="lastName"]'))
      .or(page.getByPlaceholder(/last name/i))
      .or(page.getByLabel(/last name/i))
      .first();

    this.emailInput = page
      .getByTestId('email')
      .or(page.locator('input[name="email"]'))
      .or(page.getByPlaceholder(/email/i))
      .or(page.getByLabel(/email/i))
      .first();

    this.passwordInput = page
      .getByTestId('password')
      .or(page.locator('input[name="password"]'))
      .or(page.getByPlaceholder(/^password$/i))
      .or(page.getByLabel(/^password$/i))
      .first();

    this.confirmPasswordInput = page
      .getByTestId('confirm-password')
      .or(page.locator('input[name="confirmPassword"]'))
      .or(page.getByPlaceholder(/confirm password/i))
      .or(page.getByLabel(/confirm password/i))
      .first();

    this.signupBtn = page
      .getByTestId('submit')
      .or(page.getByRole('button', { name: /sign up|signup|register|create account/i }))
      .first();
  }

  async open(): Promise<void> {
    await this.goto('/signup');
    await this.page.waitForLoadState('domcontentloaded');
  }

  async fillSignupForm(
    firstName: string,
    lastName: string,
    email: string,
    password: string,
    confirmPassword?: string
  ): Promise<void> {
    await this.firstNameInput.waitFor({ state: 'visible', timeout: 10000 });
    await this.firstNameInput.fill(firstName);
    await this.lastNameInput.waitFor({ state: 'visible', timeout: 5000 });
    await this.lastNameInput.fill(lastName);
    await this.emailInput.waitFor({ state: 'visible', timeout: 5000 });
    await this.emailInput.fill(email);
    await this.passwordInput.waitFor({ state: 'visible', timeout: 5000 });
    await this.passwordInput.fill(password);
    await this.confirmPasswordInput.waitFor({ state: 'visible', timeout: 5000 });
    await this.confirmPasswordInput.fill(confirmPassword ?? password);
  }

  async signup(
    firstName: string,
    lastName: string,
    email: string,
    password: string,
    confirmPassword?: string
  ): Promise<void> {
    await this.fillSignupForm(firstName, lastName, email, password, confirmPassword);

    await Promise.all([
      this.signupBtn.click(),
      this.page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: 10000 }).catch(() => {})
    ]);
  }

  async assertSignupError(expectedText?: RegExp | string): Promise<void> {
    const errorLocator = expectedText
      ? this.page.getByText(expectedText as any)
      : this.page.getByText(/invalid|required|missing|weak|mismatch|already registered|email/i);

    await expect(errorLocator.first()).toBeVisible({ timeout: 10000 });
  }

  async assertSignedUp(): Promise<void> {
    await expect(this.page).toHaveURL(/dashboard|home|todo|tasks/i, {
      timeout: 10000
    });
  }
}
