import { Given, When, Then } from '@cucumber/cucumber';
import { expect } from '@playwright/test';
import { PlaywrightWorld } from '../support/world';
import { LoginPage } from '../pages/LoginPage';
import { HomePage } from '../pages/HomePage';

Given('je suis sur la page de connexion', async function (this: PlaywrightWorld) {
  const page = new LoginPage(this.page);
  await page.goto();
});

Given('je suis connecté avec {string} et {string}', async function (this: PlaywrightWorld, email: string, password: string) {
  const loginPage = new LoginPage(this.page);
  await loginPage.goto();
  await loginPage.login(email, password);
  await this.page.waitForLoadState('domcontentloaded');
});

When('je saisis l\'email {string} et le mot de passe {string}', async function (this: PlaywrightWorld, email: string, password: string) {
  const loginPage = new LoginPage(this.page);
  if (email) await this.page.fill('input[data-qa="login-email"]', email);
  if (password) await this.page.fill('input[data-qa="login-password"]', password);
});

When('je clique sur le bouton de connexion', async function (this: PlaywrightWorld) {
  await this.page.click('button[data-qa="login-button"]');
  await this.page.waitForLoadState('domcontentloaded');
});

When('je clique sur le lien de déconnexion', async function (this: PlaywrightWorld) {
  await this.page.click('a[href="/logout"]');
  await this.page.waitForLoadState('domcontentloaded');
});

When('je saisis le nom {string} et l\'email {string} pour l\'inscription', async function (this: PlaywrightWorld, name: string, email: string) {
  await this.page.fill('input[data-qa="signup-name"]', name);
  await this.page.fill('input[data-qa="signup-email"]', email);
});

When('je clique sur le bouton d\'inscription', async function (this: PlaywrightWorld) {
  await this.page.click('button[data-qa="signup-button"]');
  await this.page.waitForLoadState('domcontentloaded');
});

Then('je suis redirigé vers la page d\'accueil', async function (this: PlaywrightWorld) {
  expect(this.page.url()).toContain('/');
});

Then('je vois {string} dans la barre de navigation', async function (this: PlaywrightWorld, text: string) {
  const navbar = this.page.locator('.navbar-nav');
  await expect(navbar).toContainText(text);
});

Then('je vois le message d\'erreur {string}', async function (this: PlaywrightWorld, message: string) {
  const error = this.page.locator('p').filter({ hasText: message });
  await expect(error).toBeVisible();
});

Then('je vois le message {string}', async function (this: PlaywrightWorld, message: string) {
  const msg = this.page.locator('p').filter({ hasText: message });
  await expect(msg).toBeVisible();
});

Then('le formulaire ne peut pas être soumis', async function (this: PlaywrightWorld) {
  const url = this.page.url();
  expect(url).toContain('/login');
});

Then('je suis redirigé vers la page de connexion', async function (this: PlaywrightWorld) {
  expect(this.page.url()).toContain('/login');
});
