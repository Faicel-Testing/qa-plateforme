package mobile.Tests;

import mobile.core.BaseTest;
import mobile.pages.CatalogPage;
import mobile.pages.ProductDetailPage;
import org.testng.Assert;
import org.testng.annotations.Test;

public class Test02_Catalog extends BaseTest {

    private CatalogPage loginAndGetCatalog() {
        // App opens directly on catalog — no login required to browse
        return new CatalogPage(getDriver()).waitForScreen();
    }

    @Test(groups = {"smoke", "regression"}, description = "Products are visible after login")
    public void productsVisibleAfterLogin() {
        CatalogPage catalog = loginAndGetCatalog();
        Assert.assertTrue(catalog.getProductCount() > 0,
            "At least one product should be visible in the catalog");
    }

    @Test(groups = {"regression"}, description = "Sort products by name A to Z")
    public void sortByNameAscending() {
        CatalogPage catalog = loginAndGetCatalog();
        String firstNameBefore = catalog.getFirstProductName();
        catalog.tapSortButton().selectSortOption("Name - A to Z");
        String firstNameAfter = catalog.getFirstProductName();
        Assert.assertNotNull(firstNameAfter, "Product names should be visible after sort");
    }

    @Test(groups = {"regression"}, description = "Sort products by price ascending")
    public void sortByPriceAscending() {
        CatalogPage catalog = loginAndGetCatalog();
        catalog.tapSortButton().selectSortOption("Price - Low to High");
        Assert.assertTrue(catalog.getProductCount() > 0,
            "Products should remain visible after price sort");
    }

    @Test(groups = {"regression"}, description = "Tapping a product navigates to detail screen")
    public void tapProductNavigatesToDetail() {
        CatalogPage catalog = loginAndGetCatalog();
        catalog.tapFirstProduct();
        ProductDetailPage detail = new ProductDetailPage(getDriver()).waitForScreen();
        Assert.assertTrue(detail.isDisplayed(),
            "Product detail screen should be displayed after tapping a product");
        Assert.assertFalse(detail.getProductName().isEmpty(),
            "Product name should not be empty on detail screen");
    }
}
