import { IWorldOptions, setWorldConstructor, World } from '@cucumber/cucumber';
import {
  Browser,
  BrowserContext,
  Page,
  chromium,
  firefox,
  webkit
} from 'playwright';
import { TestUser } from '../support/testData';
import { TestDataService } from '../data/TestDataService';

export class CustomWorld extends World {
  browser!: Browser;
  context!: BrowserContext;
  page!: Page;
  user?: TestUser;
  dataService?: TestDataService;
  dataOutcome = 'unknown';

  async newTestUser(): Promise<TestUser> {
    if (!this.dataService) throw new Error('Test data service not initialized by scenario hooks');
    return this.dataService.createUser();
  }
  baseUrl!: string;
  browserName!: string;

  scenarioName?: string;
  traceName?: string;
  tracingEnabled: boolean = false;
  lastTodo?: string;
  todoCountBeforeAttempt?: number;
  deleteAttemptFoundItem?: boolean;
  apiToken?: string;
  newPassword?: string;
  newEmail?: string;
  consoleLogs: string[] = [];
  pageErrors: string[] = [];
  failedRequests: string[] = [];

  constructor(options: IWorldOptions) {
    super(options);
  }

  async init(): Promise<void> {
    this.baseUrl = process.env.BASE_URL || 'https://qacart-todo.herokuapp.com';

    this.browserName = (
      process.env.TEST_BROWSER ||
      process.env.BROWSER ||
      'chromium'
    ).toLowerCase();

    const headless =
      (process.env.TEST_HEADLESS || 'false').toLowerCase() === 'true';

    // Debug one-liner — visible une seule fois au démarrage si DEBUG=true
    if (process.env.DEBUG === 'true') {
      console.log(`[world] browser=${this.browserName} headless=${headless} url=${this.baseUrl}`);
    }

    switch (this.browserName) {
      case 'firefox':
        this.browser = await firefox.launch({ headless });
        break;

      case 'webkit':
        this.browser = await webkit.launch({ headless });
        break;

      case 'chromium':
      case 'chrome':
      default:
        this.browser = await chromium.launch({ headless });
        break;
    }

    this.context = await this.browser.newContext({
      viewport: { width: 1280, height: 800 },
      ignoreHTTPSErrors: true
    });

    this.page = await this.context.newPage();

    this.page.setDefaultTimeout(10000);
    this.page.setDefaultNavigationTimeout(30000);

    this.consoleLogs = [];
    this.pageErrors = [];
    this.failedRequests = [];
  }

  async dispose(): Promise<void> {
    try {
      if (this.browser) {
        await this.browser.close();
      }
    } catch (error) {
      console.warn('⚠️ Browser close failed:', error);
    } finally {
      try { await this.dataService?.dispose(this.dataOutcome); }
      catch { throw new Error('Test data reservation release failed; inspect the dedicated database'); }
    }
  }
}

setWorldConstructor(CustomWorld);
