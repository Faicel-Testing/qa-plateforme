package com.qacart.todo.pages;

import com.qacart.todo.base.BasePage;
import com.qacart.todo.utils.ui.ElementActions;
import com.qacart.todo.utils.ui.Waiter;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;

public class LoginPage extends BasePage {

    private static final By EMAIL     = By.cssSelector("[data-testid='email']");
    private static final By PASSWORD  = By.cssSelector("[data-testid='password']");
    private static final By SUBMIT    = By.cssSelector("[data-testid='submit']");
    private static final By ADD_BTN   = By.cssSelector("button:has(svg[data-testid='add'])");
    private static final By ERROR_MSG = By.cssSelector(".MuiAlert-message, .MuiFormHelperText-root.Mui-error");

    public LoginPage(WebDriver driver) {
        super(driver);
    }

    public void open(String baseUrl) {
        load(baseUrl + "/login");
        Waiter.visible(EMAIL);
    }

    public void login(String email, String password) {
        if (email != null && !email.isEmpty())       ElementActions.type(EMAIL, email);
        if (password != null && !password.isEmpty()) ElementActions.type(PASSWORD, password);
        ElementActions.click(SUBMIT);
    }

    public void assertLoggedIn() {
        Waiter.urlContains("/todo");
        Waiter.visible(ADD_BTN);
    }

    public boolean isErrorVisible() {
        try {
            new org.openqa.selenium.support.ui.WebDriverWait(driver, java.time.Duration.ofSeconds(15))
                .until(org.openqa.selenium.support.ui.ExpectedConditions
                    .presenceOfElementLocated(ERROR_MSG));
            return true;
        } catch (org.openqa.selenium.TimeoutException e) {
            return false;
        }
    }
}
