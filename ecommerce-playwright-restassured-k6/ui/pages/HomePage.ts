import { Page } from 'playwright';
import { BasePage } from './BasePage';

export class HomePage extends BasePage {
  private readonly selectors = {
    navbar:          '.navbar-nav',
    loginLink:       'a[href="/login"]',
    logoutLink:      'a[href="/logout"]',
    productsLink:    'a[href="/products"]',
    cartLink:        'a[href="/view_cart"]',
    searchInput:     '#search_product',
    searchButton:    '#submit_search',
    productItems:    '.product-image-wrapper',
    featuredItems:   '.features_items .product-image-wrapper',
    slider:          '#slider',
    footer:          '#footer',
    loggedInAs:      'li:has-text("Logged in as") b',
  };

  async goto(): Promise<void> {
    await this.navigate('/');
  }

  async clickLogin(): Promise<void> {
    await this.page.click(this.selectors.loginLink);
    await this.page.waitForLoadState('domcontentloaded');
  }

  async clickLogout(): Promise<void> {
    await this.page.click(this.selectors.logoutLink);
    await this.page.waitForLoadState('domcontentloaded');
  }

  async clickProducts(): Promise<void> {
    await this.page.click(this.selectors.productsLink);
    await this.page.waitForLoadState('domcontentloaded');
  }

  async clickCart(): Promise<void> {
    await this.page.click(this.selectors.cartLink);
    await this.page.waitForLoadState('domcontentloaded');
  }

  async searchProduct(query: string): Promise<void> {
    await this.page.fill(this.selectors.searchInput, query);
    await this.page.click(this.selectors.searchButton);
    await this.page.waitForLoadState('domcontentloaded');
  }

  async getLoggedInUsername(): Promise<string> {
    return this.page.locator(this.selectors.loggedInAs).innerText();
  }

  async getFeaturedProductsCount(): Promise<number> {
    return this.page.locator(this.selectors.featuredItems).count();
  }

  async isHomePageLoaded(): Promise<boolean> {
    return this.page.locator(this.selectors.slider).isVisible();
  }
}
