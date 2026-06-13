package mobile.Tests;

import mobile.core.BaseTest;
import mobile.pages.CatalogPage;
import mobile.pages.LoginPage;
import mobile.pages.NavigationMenuPage;
import mobile.config.ConfigLoader;
import org.testng.Assert;
import org.testng.annotations.Test;

public class Test01_Login extends BaseTest {

    @Test(groups = {"smoke", "regression"}, description = "Login with valid credentials navigates to catalog")
    public void loginWithValidCredentials() {
        LoginPage loginPage = new LoginPage(getDriver()).openFromMenu();
        loginPage.loginAs(
            ConfigLoader.get("login.email"),
            ConfigLoader.get("login.password")
        );
        CatalogPage catalog = new CatalogPage(getDriver());
        Assert.assertTrue(catalog.waitForScreen().isDisplayed(),
            "Catalog should be visible after successful login");
    }

    @Test(groups = {"regression"}, description = "Login with wrong password shows error")
    public void loginWithWrongPassword() {
        LoginPage loginPage = new LoginPage(getDriver()).openFromMenu();
        loginPage.loginAs(
            ConfigLoader.get("login.email"),
            ConfigLoader.get("login.wrong.password")
        );
        Assert.assertTrue(loginPage.isErrorDisplayed(),
            "Error message should appear for wrong password");
    }

    @Test(groups = {"regression"}, description = "Login with unregistered email shows error")
    public void loginWithUnregisteredEmail() {
        LoginPage loginPage = new LoginPage(getDriver()).openFromMenu();
        loginPage.loginAs(
            ConfigLoader.get("login.wrong.email"),
            ConfigLoader.get("login.wrong.password")
        );
        Assert.assertTrue(loginPage.isErrorDisplayed(),
            "Error message should appear for unregistered email");
    }

    @Test(groups = {"regression"}, description = "Login with empty credentials shows error")
    public void loginWithEmptyCredentials() {
        LoginPage loginPage = new LoginPage(getDriver()).openFromMenu();
        loginPage.clickLogin();
        Assert.assertTrue(loginPage.isErrorDisplayed(),
            "Error message should appear when credentials are empty");
    }

    @Test(groups = {"regression"}, description = "Logout from navigation menu returns to login screen")
    public void logoutFromMenu() {
        LoginPage loginPage = new LoginPage(getDriver()).waitForScreen();
        loginPage.loginAs(
            ConfigLoader.get("login.email"),
            ConfigLoader.get("login.password")
        );
        new CatalogPage(getDriver()).waitForScreen();

        NavigationMenuPage menu = new NavigationMenuPage(getDriver());
        menu.openMenu();

        Assert.assertTrue(menu.isLogoutVisible(), "Logout should be visible after login");
        menu.tapLogout();

        Assert.assertTrue(loginPage.isLoginScreenDisplayed(),
            "Login screen should be displayed after logout");
    }
}
