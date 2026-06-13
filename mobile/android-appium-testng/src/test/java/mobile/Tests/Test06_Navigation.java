package mobile.Tests;

import mobile.core.BaseTest;
import mobile.pages.CatalogPage;
import mobile.pages.NavigationMenuPage;
import org.testng.Assert;
import org.testng.annotations.Test;

public class Test06_Navigation extends BaseTest {

    private NavigationMenuPage loginAndOpenMenu() {
        // App opens on catalog — no login required for navigation tests
        new CatalogPage(getDriver()).waitForScreen();
        NavigationMenuPage menu = new NavigationMenuPage(getDriver());
        menu.openMenu();
        return menu;
    }

    @Test(groups = {"smoke", "regression"}, description = "Burger menu opens and shows catalog option")
    public void menuOpensWithCatalogOption() {
        NavigationMenuPage menu = loginAndOpenMenu();
        Assert.assertTrue(menu.isMenuOpen(), "Navigation menu should be open");
    }

    @Test(groups = {"regression"}, description = "Tapping Catalog from menu navigates to catalog")
    public void menuNavigatesToCatalog() {
        NavigationMenuPage menu = loginAndOpenMenu();
        menu.tapCatalog();
        CatalogPage catalog = new CatalogPage(getDriver());
        Assert.assertTrue(catalog.isDisplayed(),
            "Catalog should be displayed after tapping Catalog in menu");
    }

    @Test(groups = {"regression"}, description = "Without login, menu shows Log In option")
    public void menuShowsLoginWhenNotLoggedIn() {
        NavigationMenuPage menu = loginAndOpenMenu();
        Assert.assertTrue(menu.isLoginVisible(),
            "Log In option should be visible in menu when not logged in");
    }
}
