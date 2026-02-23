package mobile.pages;

import java.time.Duration;
import java.util.List;

import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

import io.appium.java_client.AppiumBy;
import io.appium.java_client.android.AndroidDriver;
import mobile.config.ConfigLoader;

public class Test02_SignupPage {

    private final AndroidDriver driver;
    private final WebDriverWait wait;

    // ✅ Test data from config.properties
    private final String FULLNAME = ConfigLoader.get("signup.fullname");
    private final String EMAIL    = ConfigLoader.get("signup.email");
    private final String PASSWORD = ConfigLoader.get("signup.password");

    // ✅ Locators
    private final AppiumBy signupButtonOnLogin =
            (AppiumBy) AppiumBy.androidUIAutomator("new UiSelector().text(\"Signup\")");

    private final AppiumBy editTextFields =
            (AppiumBy) AppiumBy.className("android.widget.EditText");

    private final AppiumBy signupButtonOnSignupScreen =
            (AppiumBy) AppiumBy.androidUIAutomator("new UiSelector().text(\"Signup\")");

    public Test02_SignupPage(AndroidDriver driver) {
        this.driver = driver;
        this.wait = new WebDriverWait(driver, Duration.ofSeconds(30));
    }

    // 1) Click Signup depuis l'écran Login
    public Test02_SignupPage goToSignupScreen() {
        wait.until(ExpectedConditions.elementToBeClickable(signupButtonOnLogin)).click();
        return this;
    }

    // 2) Attendre le formulaire Signup (3 champs)
    public Test02_SignupPage waitForSignupForm() {
        wait.until(d -> driver.findElements(editTextFields).size() >= 3);
        return this;
    }

    // 3) Remplir FullName / Email / Password
    public Test02_SignupPage fillSignupForm() {
        List<WebElement> fields = driver.findElements(editTextFields);

        // ✅ indices corrects : 0,1,2
        fields.get(2).clear();
        fields.get(2).sendKeys(FULLNAME);

        fields.get(3).clear();
        fields.get(3).sendKeys(EMAIL);

        fields.get(4).clear();
        fields.get(4).sendKeys(PASSWORD);

        return this;
    }

    // 4) Click Signup (écran signup)
    public Test02_SignupPage submitSignup() {
        wait.until(ExpectedConditions.elementToBeClickable(signupButtonOnSignupScreen)).click();
        return this;
    }
}
