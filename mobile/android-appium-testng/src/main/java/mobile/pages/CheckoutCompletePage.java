package mobile.pages;

import java.time.Duration;

import io.appium.java_client.AppiumBy;
import io.appium.java_client.android.AndroidDriver;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

public class CheckoutCompletePage {

    private final AndroidDriver driver;
    private final WebDriverWait wait;

    private static final String PKG = "com.saucelabs.mydemoapp.android:id/";

    private final AppiumBy thankYouText       = (AppiumBy) AppiumBy.id(PKG + "completeTV");
    private final AppiumBy continueShoppingBtn= (AppiumBy) AppiumBy.androidUIAutomator("new UiSelector().text(\"Continue Shopping\")");

    public CheckoutCompletePage(AndroidDriver driver) {
        this.driver = driver;
        this.wait   = new WebDriverWait(driver, Duration.ofSeconds(60));
    }

    public CheckoutCompletePage waitForScreen() {
        wait.until(ExpectedConditions.visibilityOfElementLocated(thankYouText));
        return this;
    }

    public boolean isDisplayed() {
        try {
            return driver.findElement(thankYouText).isDisplayed();
        } catch (Exception e) {
            return false;
        }
    }

    public String getConfirmationText() {
        try {
            return driver.findElement(thankYouText).getText();
        } catch (Exception e) {
            return "";
        }
    }

    public boolean isOrderConfirmed() {
        String text = getConfirmationText().toUpperCase();
        return text.contains("THANK YOU") || text.contains("ORDER");
    }

    public CheckoutCompletePage tapContinueShopping() {
        wait.until(ExpectedConditions.elementToBeClickable(continueShoppingBtn)).click();
        return this;
    }
}
