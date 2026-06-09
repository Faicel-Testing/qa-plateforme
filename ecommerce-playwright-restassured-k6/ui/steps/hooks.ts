import { Before, After, AfterStep, Status } from '@cucumber/cucumber';
import { PlaywrightWorld } from '../support/world';
import * as allure from 'allure-js-commons';

Before(async function (this: PlaywrightWorld) {
  await this.init();
});

AfterStep(async function (this: PlaywrightWorld, { result }) {
  if (result?.status === Status.FAILED) {
    const screenshot = await this.page.screenshot({ fullPage: true });
    await this.attach(screenshot, 'image/png');
  }
});

After(async function (this: PlaywrightWorld, { result }) {
  if (result?.status === Status.FAILED) {
    const screenshot = await this.page.screenshot({ fullPage: true });
    await this.attach(screenshot, 'image/png');
  }
  await this.teardown();
});
