package mobile.pages;

import java.time.Duration;

import io.appium.java_client.AppiumBy;
import io.appium.java_client.android.AndroidDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

public class ProductDetailPage {

    private final AndroidDriver driver;
    private final WebDriverWait wait;

    private static final String PKG = "com.saucelabs.mydemoapp.android:id/";

    private final AppiumBy productName    = (AppiumBy) AppiumBy.id(PKG + "titleTV");
    private final AppiumBy productPrice   = (AppiumBy) AppiumBy.id(PKG + "priceTV");
    private final AppiumBy productDesc    = (AppiumBy) AppiumBy.id(PKG + "descTV");
    private final AppiumBy addToCartBtn   = (AppiumBy) AppiumBy.id(PKG + "cartBt");
    private final AppiumBy quantityMinus  = (AppiumBy) AppiumBy.id(PKG + "minusIV");
    private final AppiumBy quantityPlus   = (AppiumBy) AppiumBy.id(PKG + "plusIV");
    private final AppiumBy quantityDisplay= (AppiumBy) AppiumBy.id(PKG + "noTV");
    private final AppiumBy backButton     = (AppiumBy) AppiumBy.accessibilityId("Navigate up");

    // UiScrollable expression to scroll cartBt into view
    private static final String SCROLL_TO_CART =
        "new UiScrollable(new UiSelector().scrollable(true))" +
        ".scrollIntoView(new UiSelector().resourceId(\"" + PKG + "cartBt\"))";

    public ProductDetailPage(AndroidDriver driver) {
        this.driver = driver;
        this.wait   = new WebDriverWait(driver, Duration.ofSeconds(60));
    }

    public ProductDetailPage waitForScreen() {
        // Product name is visible immediately; cartBt is below the fold — scroll to it
        wait.until(ExpectedConditions.visibilityOfElementLocated(productName));
        wait.until(d -> {
            try {
                return driver.findElement(AppiumBy.androidUIAutomator(SCROLL_TO_CART));
            } catch (Exception e) {
                return null;
            }
        });
        return this;
    }

    public boolean isDisplayed() {
        try {
            return driver.findElement(productName).isDisplayed();
        } catch (Exception e) {
            return false;
        }
    }

    public String getProductName() {
        try {
            return driver.findElement(productName).getText();
        } catch (Exception e) {
            return "";
        }
    }

    public String getProductPrice() {
        try {
            return driver.findElement(productPrice).getText();
        } catch (Exception e) {
            return "";
        }
    }

    public String getProductDescription() {
        try {
            return driver.findElement(productDesc).getText();
        } catch (Exception e) {
            return "";
        }
    }

    public String getQuantity() {
        try {
            return driver.findElement(quantityDisplay).getText();
        } catch (Exception e) {
            return "1";
        }
    }

    public ProductDetailPage increaseQuantity() {
        wait.until(ExpectedConditions.elementToBeClickable(quantityPlus)).click();
        return this;
    }

    public ProductDetailPage decreaseQuantity() {
        wait.until(ExpectedConditions.elementToBeClickable(quantityMinus)).click();
        return this;
    }

    public ProductDetailPage tapAddToCart() {
        wait.until(ExpectedConditions.elementToBeClickable(addToCartBtn)).click();
        return this;
    }

    public ProductDetailPage goBack() {
        driver.navigate().back();
        return this;
    }
}
