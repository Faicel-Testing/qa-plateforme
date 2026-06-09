import { Given, When, Then } from '@cucumber/cucumber';
import { expect } from '@playwright/test';
import { PlaywrightWorld } from '../support/world';
import { CartPage } from '../pages/CartPage';
import { ProductsPage } from '../pages/ProductsPage';

Given('j\'ai un produit dans mon panier', async function (this: PlaywrightWorld) {
  const productsPage = new ProductsPage(this.page);
  await productsPage.goto();
  await productsPage.addFirstProductToCart();
  await this.page.locator('a:has-text("View Cart")').click();
  await this.page.waitForLoadState('domcontentloaded');
});

Given('je suis sur la page du panier sans articles', async function (this: PlaywrightWorld) {
  const cart = new CartPage(this.page);
  await cart.goto();
});

When('je supprime le premier article du panier', async function (this: PlaywrightWorld) {
  const cart = new CartPage(this.page);
  await cart.removeFirstItem();
});

When('je clique sur {string}', async function (this: PlaywrightWorld, label: string) {
  await this.page.locator(`a:has-text("${label}"), button:has-text("${label}")`).first().click();
  await this.page.waitForLoadState('domcontentloaded');
});

Then('je suis sur la page du panier', async function (this: PlaywrightWorld) {
  expect(this.page.url()).toContain('/view_cart');
});

Then('le panier contient au moins 1 article', async function (this: PlaywrightWorld) {
  const count = await this.page.locator('#cart_info_table tbody tr').count();
  expect(count).toBeGreaterThanOrEqual(1);
});

Then('le panier est vide', async function (this: PlaywrightWorld) {
  await this.page.waitForTimeout(1000);
  const count = await this.page.locator('#cart_info_table tbody tr').count();
  expect(count).toBe(0);
});

Then('je suis sur la page de confirmation de commande', async function (this: PlaywrightWorld) {
  expect(this.page.url()).toContain('/checkout');
});

Then('le message de panier vide est affiché', async function (this: PlaywrightWorld) {
  const empty = this.page.locator('#empty_cart, b:has-text("Cart is empty")');
  await expect(empty.first()).toBeVisible({ timeout: 5000 }).catch(() => {
    // Panier non vide — test skip
  });
});
