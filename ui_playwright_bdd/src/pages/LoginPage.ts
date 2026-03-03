import { expect, type Locator, type Page } from '@playwright/test';
import { BasePage } from './BasePage';
import { byTestIdOr } from '../support/selectors';

export class LoginPage extends BasePage {
  readonly emailInput: Locator;
  readonly passwordInput: Locator;
  readonly loginBtn: Locator;

  constructor(page: Page) {
    super(page);

    this.emailInput = byTestIdOr(page, 'email', () => page.getByLabel(/email/i));
    this.passwordInput = byTestIdOr(page, 'password', () => page.getByLabel(/password/i));
    this.loginBtn = byTestIdOr(page, 'submit', () => page.getByRole('button', { name: /login/i }));
  }

  async open(): Promise<void> {
    await this.goto('/login');
  }

  async login(email: string, password: string): Promise<void> {
    await this.safeFill(this.emailInput, email);
    await this.safeFill(this.passwordInput, password);
    await this.safeClick(this.loginBtn);
  }

  async assertLoggedIn(): Promise<void> {
    await expect(this.page.getByRole('link', { name: /logout/i }).or(this.page.getByText(/logout/i))).toBeVisible();
  }
}