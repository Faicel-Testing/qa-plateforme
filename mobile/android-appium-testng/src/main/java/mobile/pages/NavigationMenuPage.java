package mobile.pages;

import java.time.Duration;

import io.appium.java_client.AppiumBy;
import io.appium.java_client.android.AndroidDriver;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

public class NavigationMenuPage {

    private final AndroidDriver driver;
    private final WebDriverWait wait;

    private static final String PKG = "com.saucelabs.mydemoapp.android:id/";

    private final AppiumBy menuButton     = (AppiumBy) AppiumBy.id(PKG + "menuIV");
    private final AppiumBy closeMenuBtn   = (AppiumBy) AppiumBy.accessibilityId("Close Menu");
    private final AppiumBy catalogItem    = (AppiumBy) AppiumBy.androidUIAutomator("new UiSelector().text(\"Catalog\")");
    private final AppiumBy cartItem       = (AppiumBy) AppiumBy.androidUIAutomator("new UiSelector().text(\"My Cart\")");
    private final AppiumBy loginItem      = (AppiumBy) AppiumBy.androidUIAutomator("new UiSelector().text(\"Log In\")");
    private final AppiumBy logoutItem     = (AppiumBy) AppiumBy.androidUIAutomator("new UiSelector().text(\"Log Out\")");
    private final AppiumBy aboutItem      = (AppiumBy) AppiumBy.androidUIAutomator("new UiSelector().text(\"About\")");

    public NavigationMenuPage(AndroidDriver driver) {
        this.driver = driver;
        this.wait   = new WebDriverWait(driver, Duration.ofSeconds(60));
    }

    public NavigationMenuPage openMenu() {
        wait.until(ExpectedConditions.elementToBeClickable(menuButton)).click();
        wait.until(ExpectedConditions.elementToBeClickable(catalogItem));
        return this;
    }

    public boolean isMenuOpen() {
        try {
            return driver.findElement(catalogItem).isDisplayed();
        } catch (Exception e) {
            return false;
        }
    }

    public NavigationMenuPage closeMenu() {
        try {
            driver.findElement(closeMenuBtn).click();
        } catch (Exception e) {
            driver.navigate().back();
        }
        return this;
    }

    public NavigationMenuPage tapCatalog() {
        wait.until(ExpectedConditions.elementToBeClickable(catalogItem)).click();
        return this;
    }

    public NavigationMenuPage tapCart() {
        wait.until(ExpectedConditions.elementToBeClickable(cartItem)).click();
        return this;
    }

    public NavigationMenuPage tapLogin() {
        wait.until(ExpectedConditions.elementToBeClickable(loginItem)).click();
        return this;
    }

    public NavigationMenuPage tapLogout() {
        wait.until(ExpectedConditions.elementToBeClickable(logoutItem)).click();
        return this;
    }

    public boolean isLogoutVisible() {
        try {
            return driver.findElement(logoutItem).isDisplayed();
        } catch (Exception e) {
            return false;
        }
    }

    public boolean isLoginVisible() {
        try {
            return driver.findElement(loginItem).isDisplayed();
        } catch (Exception e) {
            return false;
        }
    }
}
