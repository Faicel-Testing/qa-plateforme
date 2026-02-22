package mobile.pages;

import java.time.Duration;
import java.util.List;

import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;


import io.appium.java_client.AppiumBy;
import io.appium.java_client.android.AndroidDriver;
import mobile.config.ConfigLoader;

public class Test01_LoginPage {

    private final AndroidDriver driver;
    private final WebDriverWait wait;

    // ✅ Données maintenant dans config.properties
    private final String EMAIL = ConfigLoader.get("login.email");
    private final String PASSWORD = ConfigLoader.get("login.password");

    private final AppiumBy editTextFields =
            (AppiumBy) AppiumBy.className("android.widget.EditText");

    private final AppiumBy loginButton =
            (AppiumBy) AppiumBy.androidUIAutomator("new UiSelector().text(\"Login\")");

    private final AppiumBy logoQxCart =
            (AppiumBy) AppiumBy.className("android.widget.ImageView");

    public Test01_LoginPage(AndroidDriver driver) {
        this.driver = driver;
        this.wait = new WebDriverWait(driver, Duration.ofSeconds(30));
    }

    public Test01_LoginPage waitForLoginForm() {
        wait.until(d -> driver.findElements(editTextFields).size() >= 2);
        return this;
    }

    public Test01_LoginPage fillLoginForm() {
        List<WebElement> fields = driver.findElements(editTextFields);

        fields.get(0).clear();
        fields.get(0).sendKeys(EMAIL);

        fields.get(1).clear();
        fields.get(1).sendKeys(PASSWORD);

        return this;
    }

    public boolean isLogoDisplayed() {
        return wait.until(ExpectedConditions.visibilityOfElementLocated(logoQxCart)).isDisplayed();
    }
    public Test01_LoginPage clickLogin() {
        wait.until(ExpectedConditions.elementToBeClickable(loginButton)).click();
        return this;
    }
}
