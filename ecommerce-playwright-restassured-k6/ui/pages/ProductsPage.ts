import { Page } from 'playwright';
import { BasePage } from './BasePage';

export class ProductsPage extends BasePage {
  private readonly selectors = {
    productList:       '.product-image-wrapper',
    productName:       '.productinfo h2',
    addToCartBtn:      'a[data-product-id]',
    viewProductBtn:    'a:has-text("View Product")',
    continueShopBtn:   'button:has-text("Continue Shopping")',
    viewCartBtn:       'a:has-text("View Cart")',
    searchInput:       '#search_product',
    searchButton:      '#submit_search',
    searchedProducts:  '.features_items .product-image-wrapper',
    searchTitle:       'h2.title',
    categoryMenu:      '.left-sidebar .panel-group',
    brandMenu:         '.brands_products',
    productDetail:     '.product-information',
    productDetailName: '.product-information h2',
    productDetailPrice:'span:has-text("Rs.")',
    quantity:          '#quantity',
    addToCartDetail:   'button:has-text("Add to cart")',
  };

  async goto(): Promise<void> {
    await this.navigate('/products');
  }

  async getProductCount(): Promise<number> {
    await this.page.waitForSelector(this.selectors.productList);
    return this.page.locator(this.selectors.productList).count();
  }

  async addFirstProductToCart(): Promise<void> {
    await this.page.locator(this.selectors.addToCartBtn).first().click();
    await this.page.waitForSelector('.modal-content', { timeout: 5000 }).catch(() => {});
  }

  async clickContinueShopping(): Promise<void> {
    await this.page.locator(this.selectors.continueShopBtn).click();
    await this.page.waitForLoadState('domcontentloaded');
  }

  async clickViewCart(): Promise<void> {
    await this.page.locator(this.selectors.viewCartBtn).click();
    await this.page.waitForLoadState('domcontentloaded');
  }

  async viewFirstProduct(): Promise<void> {
    await this.page.locator(this.selectors.viewProductBtn).first().click();
    await this.page.waitForLoadState('domcontentloaded');
  }

  async getProductDetailName(): Promise<string> {
    return this.page.locator(this.selectors.productDetailName).innerText();
  }

  async searchProduct(query: string): Promise<void> {
    await this.page.fill(this.selectors.searchInput, query);
    await this.page.click(this.selectors.searchButton);
    await this.page.waitForLoadState('domcontentloaded');
  }

  async getSearchResultsCount(): Promise<number> {
    return this.page.locator(this.selectors.searchedProducts).count();
  }

  async setQuantity(qty: number): Promise<void> {
    await this.page.fill(this.selectors.quantity, String(qty));
  }

  async addToCartFromDetail(): Promise<void> {
    await this.page.locator(this.selectors.addToCartDetail).click();
    await this.page.waitForSelector('.modal-content', { timeout: 5000 }).catch(() => {});
  }
}
