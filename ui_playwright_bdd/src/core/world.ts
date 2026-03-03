import { IWorldOptions, setWorldConstructor, World } from '@cucumber/cucumber';
import { Browser, BrowserContext, Page, chromium, firefox, webkit } from 'playwright';
import { env } from '../config/env';
import { UserCreds } from '../support/fixtureStore';

export class CustomWorld extends World {
  browser!: Browser;
  context!: BrowserContext;
  page!: Page;
  user?: UserCreds;

  constructor(options: IWorldOptions) {
    super(options);
  }

  async init(): Promise<void> {
    const browserType =
      env.browser === 'firefox' ? firefox : env.browser === 'webkit' ? webkit : chromium;

    this.browser = await browserType.launch({ headless: env.headless });
    this.context = await this.browser.newContext();
    this.page = await this.context.newPage();
  }

  async dispose(): Promise<void> {
    await this.context?.close().catch(() => {});
    await this.browser?.close().catch(() => {});
  }
}

setWorldConstructor(CustomWorld);