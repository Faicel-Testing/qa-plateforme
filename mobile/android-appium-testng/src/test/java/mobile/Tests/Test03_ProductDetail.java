package mobile.Tests;

import mobile.core.BaseTest;
import mobile.pages.CatalogPage;
import mobile.pages.ProductDetailPage;
import org.testng.Assert;
import org.testng.annotations.Test;

public class Test03_ProductDetail extends BaseTest {

    private ProductDetailPage loginAndOpenFirstProduct() {
        // App opens on catalog directly — no login needed to browse products
        new CatalogPage(getDriver()).waitForScreen().tapFirstProduct();
        return new ProductDetailPage(getDriver()).waitForScreen();
    }

    @Test(groups = {"smoke", "regression"}, description = "Product detail shows name, price and description")
    public void productDetailShowsInfo() {
        ProductDetailPage detail = loginAndOpenFirstProduct();
        Assert.assertFalse(detail.getProductName().isEmpty(),
            "Product name should not be empty");
        Assert.assertFalse(detail.getProductPrice().isEmpty(),
            "Product price should not be empty");
    }

    @Test(groups = {"regression"}, description = "Default quantity is 1")
    public void defaultQuantityIsOne() {
        ProductDetailPage detail = loginAndOpenFirstProduct();
        Assert.assertEquals(detail.getQuantity(), "1",
            "Default quantity should be 1");
    }

    @Test(groups = {"regression"}, description = "Increase quantity increments the counter")
    public void increaseQuantity() {
        ProductDetailPage detail = loginAndOpenFirstProduct();
        detail.increaseQuantity();
        Assert.assertEquals(detail.getQuantity(), "2",
            "Quantity should be 2 after one increment");
    }

    @Test(groups = {"regression"}, description = "Add to cart from detail screen updates badge")
    public void addToCartFromDetail() {
        ProductDetailPage detail = loginAndOpenFirstProduct();
        detail.tapAddToCart();
        // Navigate back to catalog and read the cart badge from toolbar
        getDriver().navigate().back();
        CatalogPage catalog = new CatalogPage(getDriver()).waitForScreen();
        String badge = catalog.getCartBadgeCount();
        Assert.assertTrue(Integer.parseInt(badge) >= 1,
            "Cart badge should show at least 1 item after adding to cart");
    }
}
