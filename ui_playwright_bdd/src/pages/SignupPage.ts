import { expect, type Locator, type Page } from '@playwright/test';
import { BasePage } from './BasePage';
import { byTestIdOr } from '../support/selectors';

export class SignupPage extends BasePage {
  readonly nameInput: Locator;
  readonly emailInput: Locator;
  readonly passwordInput: Locator;
  readonly signupBtn: Locator;

  constructor(page: Page) {
    super(page);

    // data-testid (si dispo) + fallback label/role
    this.nameInput = byTestIdOr(page, 'name', () => page.getByLabel(/name/i));
    this.emailInput = byTestIdOr(page, 'email', () => page.getByLabel(/email/i));
    this.passwordInput = byTestIdOr(page, 'password', () => page.getByLabel(/password/i));
    this.signupBtn = byTestIdOr(page, 'submit', () => page.getByRole('button', { name: /sign up|register/i }));
  }

  async open(): Promise<void> {
    await this.goto('/signup');
  }

  async signup(name: string, email: string, password: string): Promise<void> {
    await this.safeFill(this.nameInput, name);
    await this.safeFill(this.emailInput, email);
    await this.safeFill(this.passwordInput, password);
    await this.safeClick(this.signupBtn);
  }

  async assertSignedUp(): Promise<void> {
    // selon l’app, adapte l’assertion (ex: “Logout” visible, ou page todos)
    await expect(this.page.getByRole('link', { name: /logout/i }).or(this.page.getByText(/logout/i))).toBeVisible();
  }
}