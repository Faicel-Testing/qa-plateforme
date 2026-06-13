package mobile.pages;

import java.time.Duration;

import io.appium.java_client.AppiumBy;
import io.appium.java_client.android.AndroidDriver;
import mobile.config.ConfigLoader;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

public class LoginPage {

    private final AndroidDriver driver;
    private final WebDriverWait wait;

    private static final String PKG = "com.saucelabs.mydemoapp.android:id/";

    private final AppiumBy usernameField = (AppiumBy) AppiumBy.id(PKG + "nameET");
    private final AppiumBy passwordField = (AppiumBy) AppiumBy.id(PKG + "passwordET");
    private final AppiumBy loginButton   = (AppiumBy) AppiumBy.id(PKG + "loginBtn");
    private final AppiumBy errorMessage  = (AppiumBy) AppiumBy.id(PKG + "errorTV");

    public LoginPage(AndroidDriver driver) {
        this.driver = driver;
        this.wait   = new WebDriverWait(driver, Duration.ofSeconds(60));
    }

    public LoginPage waitForScreen() {
        wait.until(ExpectedConditions.visibilityOfElementLocated(usernameField));
        return this;
    }

    public LoginPage enterUsername(String username) {
        WebElement field = wait.until(ExpectedConditions.visibilityOfElementLocated(usernameField));
        field.clear();
        field.sendKeys(username);
        return this;
    }

    public LoginPage enterPassword(String password) {
        WebElement field = wait.until(ExpectedConditions.visibilityOfElementLocated(passwordField));
        field.clear();
        field.sendKeys(password);
        return this;
    }

    public LoginPage clickLogin() {
        wait.until(ExpectedConditions.elementToBeClickable(loginButton)).click();
        return this;
    }

    public LoginPage loginAs(String username, String password) {
        return enterUsername(username).enterPassword(password).clickLogin();
    }

    public LoginPage loginWithValidCredentials() {
        return loginAs(
            ConfigLoader.get("login.email"),
            ConfigLoader.get("login.password")
        );
    }

    public boolean isErrorDisplayed() {
        try {
            return wait.until(ExpectedConditions.visibilityOfElementLocated(errorMessage)).isDisplayed();
        } catch (Exception e) {
            return false;
        }
    }

    public String getErrorMessage() {
        try {
            return wait.until(ExpectedConditions.visibilityOfElementLocated(errorMessage)).getText();
        } catch (Exception e) {
            return "";
        }
    }

    public boolean isLoginScreenDisplayed() {
        try {
            return driver.findElement(loginButton).isDisplayed();
        } catch (Exception e) {
            return false;
        }
    }

    /** Navigate to the login screen via the hamburger menu, then wait for the form. */
    public LoginPage openFromMenu() {
        new NavigationMenuPage(driver).openMenu().tapLogin();
        return waitForScreen();
    }
}
