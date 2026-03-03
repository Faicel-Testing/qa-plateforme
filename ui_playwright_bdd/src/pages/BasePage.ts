import { Page, Locator } from 'playwright';
import { env } from '../config/env';

export class BasePage {
  constructor(protected page: Page) {}

  async goto(path = '/'): Promise<void> {
    await this.page.goto(`${env.baseUrl}${path}`);
  }

  // “safe action” : si data-testid n’existe pas, le Locator.or(fallback) prend le relais.
  async safeFill(locator: Locator, value: string): Promise<void> {
    await locator.first().fill(value);
  }

  async safeClick(locator: Locator): Promise<void> {
    await locator.first().click();
  }
}