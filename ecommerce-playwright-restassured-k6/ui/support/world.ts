import { setWorldConstructor, World, IWorldOptions } from '@cucumber/cucumber';
import { Browser, BrowserContext, Page, chromium, firefox, webkit } from 'playwright';
import * as dotenv from 'dotenv';

dotenv.config();

export interface CustomWorld extends World {
  browser: Browser;
  context: BrowserContext;
  page: Page;
}

export class PlaywrightWorld extends World implements CustomWorld {
  browser!: Browser;
  context!: BrowserContext;
  page!: Page;

  constructor(options: IWorldOptions) {
    super(options);
  }

  async init(): Promise<void> {
    const browserName = (process.env.BROWSER || 'chromium') as 'chromium' | 'firefox' | 'webkit';
    const headless = process.env.HEADLESS !== 'false';
    const slowMo = parseInt(process.env.SLOW_MO || '0');

    const launcher = { chromium, firefox, webkit }[browserName];
    this.browser = await launcher.launch({ headless, slowMo });
    this.context = await this.browser.newContext({
      baseURL: process.env.BASE_URL || 'https://automationexercise.com',
      viewport: { width: 1280, height: 720 },
      locale: 'fr-FR',
    });
    this.page = await this.context.newPage();
  }

  async teardown(): Promise<void> {
    await this.page?.close();
    await this.context?.close();
    await this.browser?.close();
  }
}

setWorldConstructor(PlaywrightWorld);
