import { Given, When, Then } from '@cucumber/cucumber';
import { expect } from '@playwright/test';
import { PlaywrightWorld } from '../support/world';
import { ProductsPage } from '../pages/ProductsPage';

Given('je suis sur la page des produits', async function (this: PlaywrightWorld) {
  const page = new ProductsPage(this.page);
  await page.goto();
});

When('je clique sur {string} du premier produit', async function (this: PlaywrightWorld, _label: string) {
  await this.page.locator('a:has-text("View Product")').first().click();
  await this.page.waitForLoadState('domcontentloaded');
});

When('je recherche le produit {string}', async function (this: PlaywrightWorld, query: string) {
  const page = new ProductsPage(this.page);
  await page.searchProduct(query);
});

When('j\'ajoute le premier produit au panier', async function (this: PlaywrightWorld) {
  const page = new ProductsPage(this.page);
  await page.addFirstProductToCart();
});

When('je clique sur {string} dans la modale', async function (this: PlaywrightWorld, label: string) {
  if (label === 'Continue Shopping') {
    await this.page.locator('button:has-text("Continue Shopping")').click();
  } else if (label === 'View Cart') {
    await this.page.locator('a:has-text("View Cart")').click();
  }
  await this.page.waitForLoadState('domcontentloaded');
});

When('je change la quantité à {int}', async function (this: PlaywrightWorld, qty: number) {
  await this.page.fill('#quantity', String(qty));
});

When('j\'ajoute au panier depuis la page détail', async function (this: PlaywrightWorld) {
  await this.page.locator('button:has-text("Add to cart")').click();
  await this.page.waitForSelector('.modal-content', { timeout: 5000 }).catch(() => {});
});

Then('la liste des produits est affichée', async function (this: PlaywrightWorld) {
  await expect(this.page.locator('.product-image-wrapper').first()).toBeVisible();
});

Then('le nombre de produits est supérieur à 0', async function (this: PlaywrightWorld) {
  const count = await this.page.locator('.product-image-wrapper').count();
  expect(count).toBeGreaterThan(0);
});

Then('je suis sur la page de détail du produit', async function (this: PlaywrightWorld) {
  expect(this.page.url()).toContain('/product_details/');
});

Then('le nom du produit est affiché', async function (this: PlaywrightWorld) {
  await expect(this.page.locator('.product-information h2')).toBeVisible();
});

Then('le prix du produit est affiché', async function (this: PlaywrightWorld) {
  await expect(this.page.locator('.product-information span span')).toBeVisible();
});

Then('les résultats de recherche sont affichés', async function (this: PlaywrightWorld) {
  await expect(this.page.locator('.features_items')).toBeVisible();
});

Then('le titre {string} est visible', async function (this: PlaywrightWorld, title: string) {
  await expect(this.page.locator('h2.title').filter({ hasText: title })).toBeVisible();
});

Then('au moins 1 produit est trouvé', async function (this: PlaywrightWorld) {
  const count = await this.page.locator('.product-image-wrapper').count();
  expect(count).toBeGreaterThanOrEqual(1);
});

Then('aucun produit n\'est trouvé dans les résultats', async function (this: PlaywrightWorld) {
  const count = await this.page.locator('.product-image-wrapper').count();
  expect(count).toBe(0);
});

Then('la modale de confirmation apparaît', async function (this: PlaywrightWorld) {
  await expect(this.page.locator('.modal-content')).toBeVisible({ timeout: 5000 });
});

Then('je reste sur la page des produits', async function (this: PlaywrightWorld) {
  expect(this.page.url()).toContain('/products');
});
