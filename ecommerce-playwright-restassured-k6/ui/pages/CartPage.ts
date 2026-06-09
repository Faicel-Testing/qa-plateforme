import { Page } from 'playwright';
import { BasePage } from './BasePage';

export class CartPage extends BasePage {
  private readonly selectors = {
    cartItems:       '#cart_info_table tbody tr',
    productName:     '.cart_description h4 a',
    productPrice:    '.cart_price p',
    productQty:      '.cart_quantity button',
    productTotal:    '.cart_total p',
    deleteBtn:       '.cart_quantity_delete',
    checkoutBtn:     'a:has-text("Proceed To Checkout")',
    emptyCartMsg:    '#empty_cart',
    loginLink:       'a:has-text("Register / Login")',
  };

  async goto(): Promise<void> {
    await this.navigate('/view_cart');
  }

  async getCartItemCount(): Promise<number> {
    return this.page.locator(this.selectors.cartItems).count();
  }

  async getFirstProductName(): Promise<string> {
    return this.page.locator(this.selectors.productName).first().innerText();
  }

  async getFirstProductQuantity(): Promise<string> {
    return this.page.locator(this.selectors.productQty).first().innerText();
  }

  async removeFirstItem(): Promise<void> {
    await this.page.locator(this.selectors.deleteBtn).first().click();
    await this.page.waitForTimeout(1000);
  }

  async isCartEmpty(): Promise<boolean> {
    return this.page.locator(this.selectors.emptyCartMsg).isVisible();
  }

  async proceedToCheckout(): Promise<void> {
    await this.page.click(this.selectors.checkoutBtn);
    await this.page.waitForLoadState('domcontentloaded');
  }
}
