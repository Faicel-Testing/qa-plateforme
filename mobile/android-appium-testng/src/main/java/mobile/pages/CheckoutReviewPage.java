package mobile.pages;

import java.time.Duration;

import io.appium.java_client.AppiumBy;
import io.appium.java_client.android.AndroidDriver;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

public class CheckoutReviewPage {

    private final AndroidDriver driver;
    private final WebDriverWait wait;

    private static final String PKG = "com.saucelabs.mydemoapp.android:id/";

    private final AppiumBy placeOrderBtn = (AppiumBy) AppiumBy.androidUIAutomator("new UiSelector().text(\"Place Order\")");
    private final AppiumBy totalPrice    = (AppiumBy) AppiumBy.id(PKG + "totalPriceTV");

    public CheckoutReviewPage(AndroidDriver driver) {
        this.driver = driver;
        this.wait   = new WebDriverWait(driver, Duration.ofSeconds(60));
    }

    public CheckoutReviewPage waitForScreen() {
        wait.until(ExpectedConditions.elementToBeClickable(placeOrderBtn));
        return this;
    }

    public boolean isDisplayed() {
        try {
            return driver.findElement(placeOrderBtn).isDisplayed();
        } catch (Exception e) {
            return false;
        }
    }

    public String getTotalPrice() {
        try {
            return driver.findElement(totalPrice).getText();
        } catch (Exception e) {
            return "";
        }
    }

    public CheckoutReviewPage tapPlaceOrder() {
        wait.until(ExpectedConditions.elementToBeClickable(placeOrderBtn)).click();
        return this;
    }
}
