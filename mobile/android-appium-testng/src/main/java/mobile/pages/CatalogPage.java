package mobile.pages;

import java.time.Duration;
import java.util.List;

import io.appium.java_client.AppiumBy;
import io.appium.java_client.android.AndroidDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

public class CatalogPage {

    private final AndroidDriver driver;
    private final WebDriverWait wait;

    private static final String PKG = "com.saucelabs.mydemoapp.android:id/";

    // productTV = "Products" page heading (confirms we're on catalog screen)
    private final AppiumBy pageHeading     = (AppiumBy) AppiumBy.id(PKG + "productTV");
    // titleTV = product name on each catalog card (clickable=false)
    private final AppiumBy productTitles   = (AppiumBy) AppiumBy.id(PKG + "titleTV");
    private final AppiumBy productPrices   = (AppiumBy) AppiumBy.id(PKG + "priceTV");
    // productIV = product image on each card (clickable=true — opens product detail)
    private final AppiumBy productImages   = (AppiumBy) AppiumBy.id(PKG + "productIV");
    private final AppiumBy sortButton      = (AppiumBy) AppiumBy.id(PKG + "sortIV");
    // cartRL = toolbar cart container, clickable=true; cartIV inside is not clickable
    private final AppiumBy cartIcon        = (AppiumBy) AppiumBy.id(PKG + "cartRL");
    private final AppiumBy menuButton      = (AppiumBy) AppiumBy.id(PKG + "menuIV");

    public CatalogPage(AndroidDriver driver) {
        this.driver = driver;
        this.wait   = new WebDriverWait(driver, Duration.ofSeconds(60));
    }

    public CatalogPage waitForScreen() {
        wait.until(ExpectedConditions.visibilityOfElementLocated(pageHeading));
        return this;
    }

    public boolean isDisplayed() {
        try {
            return driver.findElements(pageHeading).size() > 0;
        } catch (Exception e) {
            return false;
        }
    }

    public int getProductCount() {
        return driver.findElements(productImages).size();
    }

    public List<WebElement> getProductNameElements() {
        return driver.findElements(productTitles);
    }

    public String getFirstProductName() {
        List<WebElement> names = driver.findElements(productTitles);
        return names.isEmpty() ? "" : names.get(0).getText();
    }

    public List<WebElement> getProductPriceElements() {
        return driver.findElements(productPrices);
    }

    public CatalogPage tapSortButton() {
        wait.until(ExpectedConditions.elementToBeClickable(sortButton)).click();
        return this;
    }

    public CatalogPage selectSortOption(String optionText) {
        wait.until(ExpectedConditions.elementToBeClickable(
            AppiumBy.androidUIAutomator("new UiSelector().text(\"" + optionText + "\")")
        )).click();
        return this;
    }

    public CatalogPage tapFirstProduct() {
        // productIV (product image) is clickable=true; titleTV is not clickable
        List<WebElement> images = wait.until(d -> {
            List<WebElement> els = driver.findElements(productImages);
            return els.isEmpty() ? null : els;
        });
        images.get(0).click();
        return this;
    }

    public CatalogPage tapProductByIndex(int index) {
        List<WebElement> images = driver.findElements(productImages);
        images.get(index).click();
        return this;
    }

    public String getCartBadgeCount() {
        // cartTV badge appears in toolbar only when cart has items
        try {
            return driver.findElement(AppiumBy.id(PKG + "cartTV")).getText();
        } catch (Exception e) {
            return "0";
        }
    }

    public CatalogPage tapCartIcon() {
        // cartRL is the clickable parent of cartIV in the toolbar
        wait.until(ExpectedConditions.elementToBeClickable(cartIcon)).click();
        return this;
    }

    public CatalogPage tapMenuButton() {
        wait.until(ExpectedConditions.elementToBeClickable(menuButton)).click();
        return this;
    }
}
