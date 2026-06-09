import { Page } from 'playwright';

export class BasePage {
  constructor(protected page: Page) {}

  async navigate(path = ''): Promise<void> {
    await this.page.goto(path || '/');
    await this.page.waitForLoadState('domcontentloaded');
  }

  async getTitle(): Promise<string> {
    return this.page.title();
  }

  async isVisible(selector: string): Promise<boolean> {
    return this.page.locator(selector).isVisible();
  }

  async getText(selector: string): Promise<string> {
    return this.page.locator(selector).innerText();
  }
}
