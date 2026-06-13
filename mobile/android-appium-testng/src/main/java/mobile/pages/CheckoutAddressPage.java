package mobile.pages;

import java.time.Duration;

import io.appium.java_client.AppiumBy;
import io.appium.java_client.android.AndroidDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

public class CheckoutAddressPage {

    private final AndroidDriver driver;
    private final WebDriverWait wait;

    private static final String PKG = "com.saucelabs.mydemoapp.android:id/";

    private final AppiumBy fullNameField = (AppiumBy) AppiumBy.id(PKG + "fullNameET");
    private final AppiumBy address1Field = (AppiumBy) AppiumBy.id(PKG + "address1ET");
    private final AppiumBy cityField     = (AppiumBy) AppiumBy.id(PKG + "cityET");
    private final AppiumBy stateField    = (AppiumBy) AppiumBy.id(PKG + "stateET");
    private final AppiumBy zipField      = (AppiumBy) AppiumBy.id(PKG + "zipET");
    private final AppiumBy countryField  = (AppiumBy) AppiumBy.id(PKG + "countryET");
    private final AppiumBy toPaymentBtn  = (AppiumBy) AppiumBy.id(PKG + "paymentBtn");

    public CheckoutAddressPage(AndroidDriver driver) {
        this.driver = driver;
        this.wait   = new WebDriverWait(driver, Duration.ofSeconds(60));
    }

    public CheckoutAddressPage waitForScreen() {
        wait.until(ExpectedConditions.visibilityOfElementLocated(fullNameField));
        return this;
    }

    public boolean isDisplayed() {
        try {
            return driver.findElement(fullNameField).isDisplayed();
        } catch (Exception e) {
            return false;
        }
    }

    private CheckoutAddressPage fillField(AppiumBy locator, String value) {
        WebElement field = wait.until(ExpectedConditions.visibilityOfElementLocated(locator));
        field.clear();
        field.sendKeys(value);
        return this;
    }

    public CheckoutAddressPage enterFullName(String name)    { return fillField(fullNameField, name); }
    public CheckoutAddressPage enterAddress(String address)  { return fillField(address1Field, address); }
    public CheckoutAddressPage enterCity(String city)        { return fillField(cityField, city); }
    public CheckoutAddressPage enterState(String state)      { return fillField(stateField, state); }
    public CheckoutAddressPage enterZip(String zip)          { return fillField(zipField, zip); }
    public CheckoutAddressPage enterCountry(String country)  { return fillField(countryField, country); }

    public CheckoutAddressPage fillValidAddress() {
        return enterFullName("Bob Smith")
            .enterAddress("123 Main Street")
            .enterCity("San Francisco")
            .enterState("California")
            .enterZip("94102")
            .enterCountry("United States");
    }

    public CheckoutAddressPage tapToPayment() {
        wait.until(ExpectedConditions.elementToBeClickable(toPaymentBtn)).click();
        return this;
    }
}
