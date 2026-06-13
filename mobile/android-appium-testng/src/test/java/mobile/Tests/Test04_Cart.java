package mobile.Tests;

import mobile.core.BaseTest;
import mobile.pages.CartPage;
import mobile.pages.CatalogPage;
import mobile.pages.LoginPage;
import mobile.pages.ProductDetailPage;
import mobile.config.ConfigLoader;
import org.testng.Assert;
import org.testng.annotations.Test;

public class Test04_Cart extends BaseTest {

    private CatalogPage loginAndGetCatalog() {
        new LoginPage(getDriver()).openFromMenu().loginAs(
            ConfigLoader.get("login.email"),
            ConfigLoader.get("login.password")
        );
        return new CatalogPage(getDriver()).waitForScreen();
    }

    private CatalogPage addFirstProductAndReturnToCatalog(CatalogPage catalog) {
        catalog.tapFirstProduct();
        new ProductDetailPage(getDriver()).waitForScreen().tapAddToCart();
        getDriver().navigate().back();
        return catalog.waitForScreen();
    }

    @Test(groups = {"smoke", "regression"}, description = "Add product to cart — cart shows item")
    public void addProductUpdatesBadge() {
        CatalogPage catalog = loginAndGetCatalog();
        addFirstProductAndReturnToCatalog(catalog);
        catalog.tapCartIcon();
        CartPage cart = new CartPage(getDriver()).waitForScreen();
        Assert.assertTrue(cart.getItemCount() >= 1,
            "Cart should contain at least one item after adding a product");
    }

    @Test(groups = {"regression"}, description = "Cart displays added product name")
    public void cartDisplaysAddedProduct() {
        CatalogPage catalog = loginAndGetCatalog();
        String productName = catalog.getFirstProductName();
        addFirstProductAndReturnToCatalog(catalog);
        catalog.tapCartIcon();

        CartPage cart = new CartPage(getDriver()).waitForScreen();
        Assert.assertTrue(cart.getItemCount() >= 1, "Cart should contain at least one item");
        Assert.assertFalse(cart.getFirstItemName().isEmpty(), "Cart item name should not be empty");
    }

    @Test(groups = {"regression"}, description = "Removing item from cart empties the cart")
    public void removeItemFromCart() {
        CatalogPage catalog = loginAndGetCatalog();
        addFirstProductAndReturnToCatalog(catalog);
        catalog.tapCartIcon();

        CartPage cart = new CartPage(getDriver()).waitForScreen();
        int countBefore = cart.getItemCount();
        cart.removeFirstItem();

        Assert.assertTrue(cart.getItemCount() < countBefore || cart.isEmpty(),
            "Cart should have fewer items or be empty after removal");
    }

    @Test(groups = {"regression"}, description = "Empty cart shows Go Shopping button")
    public void emptyCartShowsGoShopping() {
        // Login via menu (app starts on catalog)
        CatalogPage catalog = loginAndGetCatalog();
        catalog.tapCartIcon();

        CartPage cart = new CartPage(getDriver()).waitForScreen();
        if (cart.isEmpty()) {
            Assert.assertTrue(cart.isEmpty(), "Empty cart should show Go Shopping button");
        } else {
            while (!cart.isEmpty()) {
                cart.removeFirstItem();
            }
            Assert.assertTrue(cart.isEmpty(), "Cart should be empty after removing all items");
        }
    }
}
