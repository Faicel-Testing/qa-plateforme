package mobile.pages;

import java.time.Duration;
import java.util.List;

import io.appium.java_client.AppiumBy;
import io.appium.java_client.android.AndroidDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

public class CartPage {

    private final AndroidDriver driver;
    private final WebDriverWait wait;

    private static final String PKG = "com.saucelabs.mydemoapp.android:id/";

    // Cart item components (confirmed via adb dump)
    private final AppiumBy itemNames        = (AppiumBy) AppiumBy.id(PKG + "titleTV");
    private final AppiumBy removeButtons    = (AppiumBy) AppiumBy.id(PKG + "removeBt");
    // "Proceed To Checkout" uses cartBt on cart screen (same ID as "Add to cart" on detail)
    private final AppiumBy proceedButton    = (AppiumBy) AppiumBy.id(PKG + "cartBt");
    private final AppiumBy goShoppingButton = (AppiumBy) AppiumBy.androidUIAutomator("new UiSelector().text(\"Go Shopping\")");
    private final AppiumBy cartContainer    = (AppiumBy) AppiumBy.id(PKG + "cartCL");

    public CartPage(AndroidDriver driver) {
        this.driver = driver;
        this.wait   = new WebDriverWait(driver, Duration.ofSeconds(60));
    }

    public CartPage waitForScreen() {
        wait.until(d -> driver.findElements(cartContainer).size() > 0
            || driver.findElements(goShoppingButton).size() > 0);
        return this;
    }

    public boolean isDisplayed() {
        try {
            return driver.findElements(cartContainer).size() > 0
                || driver.findElements(goShoppingButton).size() > 0;
        } catch (Exception e) {
            return false;
        }
    }

    public boolean isEmpty() {
        return driver.findElements(goShoppingButton).size() > 0;
    }

    public int getItemCount() {
        return driver.findElements(itemNames).size();
    }

    public List<WebElement> getItemNames() {
        return driver.findElements(itemNames);
    }

    public String getFirstItemName() {
        List<WebElement> names = driver.findElements(itemNames);
        return names.isEmpty() ? "" : names.get(0).getText();
    }

    public CartPage removeFirstItem() {
        List<WebElement> btns = driver.findElements(removeButtons);
        if (!btns.isEmpty()) btns.get(0).click();
        return this;
    }

    public CartPage tapProceedToCheckout() {
        wait.until(ExpectedConditions.elementToBeClickable(proceedButton)).click();
        return this;
    }

    public CartPage tapGoShopping() {
        wait.until(ExpectedConditions.elementToBeClickable(goShoppingButton)).click();
        return this;
    }
}
