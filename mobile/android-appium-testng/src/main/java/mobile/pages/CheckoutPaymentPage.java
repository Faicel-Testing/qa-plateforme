package mobile.pages;

import java.time.Duration;

import io.appium.java_client.AppiumBy;
import io.appium.java_client.android.AndroidDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

public class CheckoutPaymentPage {

    private final AndroidDriver driver;
    private final WebDriverWait wait;

    private static final String PKG = "com.saucelabs.mydemoapp.android:id/";

    private final AppiumBy cardNumberField  = (AppiumBy) AppiumBy.id(PKG + "cardNumberET");
    private final AppiumBy expiryField      = (AppiumBy) AppiumBy.id(PKG + "expirationDateET");
    private final AppiumBy securityCodeField= (AppiumBy) AppiumBy.id(PKG + "securityCodeET");
    private final AppiumBy reviewOrderBtn   = (AppiumBy) AppiumBy.androidUIAutomator("new UiSelector().text(\"Review Order\")");

    public CheckoutPaymentPage(AndroidDriver driver) {
        this.driver = driver;
        this.wait   = new WebDriverWait(driver, Duration.ofSeconds(60));
    }

    public CheckoutPaymentPage waitForScreen() {
        wait.until(ExpectedConditions.visibilityOfElementLocated(cardNumberField));
        return this;
    }

    public boolean isDisplayed() {
        try {
            return driver.findElement(cardNumberField).isDisplayed();
        } catch (Exception e) {
            return false;
        }
    }

    private CheckoutPaymentPage fillField(AppiumBy locator, String value) {
        WebElement field = wait.until(ExpectedConditions.visibilityOfElementLocated(locator));
        field.clear();
        field.sendKeys(value);
        return this;
    }

    public CheckoutPaymentPage enterCardNumber(String card)    { return fillField(cardNumberField, card); }
    public CheckoutPaymentPage enterExpiry(String expiry)      { return fillField(expiryField, expiry); }
    public CheckoutPaymentPage enterSecurityCode(String code)  { return fillField(securityCodeField, code); }

    public CheckoutPaymentPage fillValidPayment() {
        return enterCardNumber("1234567890123456")
            .enterExpiry("03/30")
            .enterSecurityCode("123");
    }

    public CheckoutPaymentPage tapReviewOrder() {
        wait.until(ExpectedConditions.elementToBeClickable(reviewOrderBtn)).click();
        return this;
    }
}
