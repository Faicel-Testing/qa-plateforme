import { Locator, Page, expect } from '@playwright/test';

export class BasePage {
  constructor(protected page: Page) {}

  async goto(path: string): Promise<void> {
    const baseUrl = process.env.BASE_URL || 'https://qacart-todo.herokuapp.com';
    const url = `${baseUrl}${path}`;

    await this.page.goto(url, {
      waitUntil: 'domcontentloaded',
      timeout: 30000
    });
  }

  async safeFill(locator: Locator, value: string): Promise<void> {
    await locator.waitFor({ state: 'visible', timeout: 10000 });
    await locator.fill(value);
  }

  async safeClick(locator: Locator): Promise<void> {
    await locator.waitFor({ state: 'visible', timeout: 10000 });
    await locator.click();
  }

  async refresh(): Promise<void> {
    await this.page.reload({ waitUntil: 'domcontentloaded' });
  }

  async logout(): Promise<void> {
    const logoutButton = this.page.getByRole('button', { name: /logout|sign out/i }).first();
    if ((await logoutButton.count()) > 0) {
      await logoutButton.click();
      return;
    }

    const logoutLink = this.page.getByRole('link', { name: /logout|sign out/i }).first();
    if ((await logoutLink.count()) > 0) {
      await logoutLink.click();
      return;
    }

    await this.goto('/logout');
  }

  async assertOnLoginPage(): Promise<void> {
    await expect(this.page).toHaveURL(/\/login|\/signin|\/auth/i, { timeout: 10000 });
  }

  async assertErrorMessage(expectedText?: RegExp | string): Promise<void> {
    const muiError = this.page.locator('.MuiFormHelperText-root.Mui-error, .MuiAlert-message');

    // waitFor (pas isVisible) : attend vraiment que l'élément apparaisse
    const hasMuiError = await muiError.first()
      .waitFor({ state: 'visible', timeout: 5000 })
      .then(() => true)
      .catch(() => false);
    if (hasMuiError) return;

    const errorLocator = expectedText
      ? this.page.getByText(expectedText as any)
      : this.page.getByText(/invalid|required|missing|weak|mismatch|already registered|not found|unable|cannot delete|error|duplicate|limit|character|please insert/i);

    // Timeout étendu à 15s pour couvrir les cold starts Heroku
    await expect(errorLocator.first()).toBeVisible({ timeout: 15000 });
  }
}