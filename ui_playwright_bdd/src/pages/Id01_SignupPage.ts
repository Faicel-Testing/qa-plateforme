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

    this.firstNameInput = page.getByTestId('first-name');
    this.lastNameInput = page.getByTestId('last-name');
    this.emailInput = page.getByTestId('email');
    this.passwordInput = page.getByTestId('password');
    this.confirmPasswordInput = page.getByTestId('confirm-password');
    this.signupBtn = page.getByTestId('submit');
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
    await this.signupBtn.click();
    // waitForNavigation peut se résoudre prématurément sur SPA React (changement de route hash)
    // avant que les messages de validation n'apparaissent → remplacé par networkidle
    await this.page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
  }

  async assertSignupError(expectedText?: RegExp | string): Promise<void> {
    const errorLocator = expectedText
      ? this.page.getByText(expectedText)
      : this.page.getByText(/invalid|required|missing|weak|mismatch|already registered|email/i);

    await expect(errorLocator.first()).toBeVisible({ timeout: 15000 });
  }

  async assertSignedUp(): Promise<void> {
    await expect(this.page).toHaveURL(/dashboard|home|todo|tasks/i, {
      timeout: 10000
    });
  }
}
