package mobile.Tests;

import mobile.core.BaseTest;
import mobile.pages.CartPage;
import mobile.pages.CatalogPage;
import mobile.pages.CheckoutAddressPage;
import mobile.pages.CheckoutCompletePage;
import mobile.pages.CheckoutPaymentPage;
import mobile.pages.CheckoutReviewPage;
import mobile.pages.LoginPage;
import mobile.pages.ProductDetailPage;
import mobile.config.ConfigLoader;
import org.testng.Assert;
import org.testng.annotations.Test;

public class Test05_Checkout extends BaseTest {

    private CartPage loginAddProductAndOpenCart() {
        new LoginPage(getDriver()).openFromMenu().loginAs(
            ConfigLoader.get("login.email"),
            ConfigLoader.get("login.password")
        );
        CatalogPage catalog = new CatalogPage(getDriver()).waitForScreen();
        // Add to cart via product detail (no per-product button on catalog screen)
        catalog.tapFirstProduct();
        new ProductDetailPage(getDriver()).waitForScreen().tapAddToCart();
        getDriver().navigate().back();
        catalog.waitForScreen().tapCartIcon();
        return new CartPage(getDriver()).waitForScreen();
    }

    @Test(groups = {"smoke", "regression"}, description = "Full checkout flow completes successfully")
    public void fullCheckoutFlow() {
        CartPage cart = loginAddProductAndOpenCart();
        Assert.assertFalse(cart.isEmpty(), "Cart must not be empty before checkout");
        cart.tapProceedToCheckout();

        CheckoutAddressPage address = new CheckoutAddressPage(getDriver()).waitForScreen();
        Assert.assertTrue(address.isDisplayed(), "Address screen should appear");
        address.fillValidAddress().tapToPayment();

        CheckoutPaymentPage payment = new CheckoutPaymentPage(getDriver()).waitForScreen();
        Assert.assertTrue(payment.isDisplayed(), "Payment screen should appear");
        payment.fillValidPayment().tapReviewOrder();

        CheckoutReviewPage review = new CheckoutReviewPage(getDriver()).waitForScreen();
        Assert.assertTrue(review.isDisplayed(), "Review screen should appear");
        review.tapPlaceOrder();

        CheckoutCompletePage complete = new CheckoutCompletePage(getDriver()).waitForScreen();
        Assert.assertTrue(complete.isOrderConfirmed(),
            "Order confirmation message should be displayed");
    }

    @Test(groups = {"regression"}, description = "Address screen requires all fields")
    public void checkoutAddressRequiresFields() {
        CartPage cart = loginAddProductAndOpenCart();
        cart.tapProceedToCheckout();

        CheckoutAddressPage address = new CheckoutAddressPage(getDriver()).waitForScreen();
        address.tapToPayment();
        Assert.assertTrue(address.isDisplayed(),
            "Address screen should remain when fields are empty");
    }

    @Test(groups = {"regression"}, description = "Checkout complete shows continue shopping button")
    public void checkoutCompleteHasContinueShopping() {
        CartPage cart = loginAddProductAndOpenCart();
        cart.tapProceedToCheckout();

        new CheckoutAddressPage(getDriver()).waitForScreen().fillValidAddress().tapToPayment();
        new CheckoutPaymentPage(getDriver()).waitForScreen().fillValidPayment().tapReviewOrder();
        new CheckoutReviewPage(getDriver()).waitForScreen().tapPlaceOrder();

        CheckoutCompletePage complete = new CheckoutCompletePage(getDriver()).waitForScreen();
        Assert.assertTrue(complete.isDisplayed(), "Complete screen should be displayed");
        complete.tapContinueShopping();

        CatalogPage catalog = new CatalogPage(getDriver());
        Assert.assertTrue(catalog.isDisplayed(),
            "Catalog should be shown after tapping Continue Shopping");
    }
}
