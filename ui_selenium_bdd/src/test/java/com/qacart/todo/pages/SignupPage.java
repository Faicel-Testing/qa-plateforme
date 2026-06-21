package com.qacart.todo.pages;

import com.qacart.todo.base.BasePage;
import com.qacart.todo.utils.ui.ElementActions;
import com.qacart.todo.utils.ui.Waiter;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;

public class SignupPage extends BasePage {

    private static final By FIRST_NAME  = By.cssSelector("[data-testid='first-name']");
    private static final By LAST_NAME   = By.cssSelector("[data-testid='last-name']");
    private static final By EMAIL       = By.cssSelector("[data-testid='email']");
    private static final By PASSWORD    = By.cssSelector("[data-testid='password']");
    private static final By CONFIRM_PW  = By.cssSelector("[data-testid='confirm-password']");
    private static final By SUBMIT      = By.cssSelector("[data-testid='submit']");
    private static final By FIELD_ERROR = By.cssSelector(".MuiFormHelperText-root.Mui-error");
    private static final By ALERT_ERROR = By.cssSelector(".MuiAlert-message");

    public SignupPage(WebDriver driver) {
        super(driver);
    }

    public void open(String baseUrl) {
        load(baseUrl + "/signup");
        Waiter.visible(FIRST_NAME);
    }

    public void fillForm(String firstName, String lastName, String email,
                         String password, String confirmPassword) {
        if (firstName != null)    ElementActions.type(FIRST_NAME, firstName);
        if (lastName != null)     ElementActions.type(LAST_NAME, lastName);
        if (email != null)        ElementActions.type(EMAIL, email);
        if (password != null)     ElementActions.type(PASSWORD, password);
        if (confirmPassword != null) ElementActions.type(CONFIRM_PW, confirmPassword);
    }

    public void clickSubmit() {
        ElementActions.click(SUBMIT);
    }

    public void signup(String firstName, String lastName, String email, String password) {
        fillForm(firstName, lastName, email, password, password);
        clickSubmit();
    }

    public boolean isErrorVisible() {
        // 15s pour validation async (Heroku peut être lent)
        By combined = By.cssSelector(".MuiFormHelperText-root.Mui-error, .MuiAlert-message");
        try {
            new org.openqa.selenium.support.ui.WebDriverWait(driver, java.time.Duration.ofSeconds(15))
                .until(org.openqa.selenium.support.ui.ExpectedConditions
                    .presenceOfElementLocated(combined));
            return true;
        } catch (org.openqa.selenium.TimeoutException e) {
            return false;
        }
    }

    public void assertSignedUp() {
        Waiter.urlContains("/todo");
    }
}
