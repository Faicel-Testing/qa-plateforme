package com.qacart.todo.pages;

import com.qacart.todo.base.BasePage;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;

public class SignupPage extends BasePage {

    public SignupPage(WebDriver driver) {
        super(driver);
    }

    private final By signupBtn = By.cssSelector("[data-testid=signup]");
    private final By firstName = By.cssSelector("[data-testid=first-name]");
    private final By lastName = By.cssSelector("[data-testid=last-name]");
    private final By email = By.cssSelector("[data-testid=email]");
    private final By password = By.cssSelector("[data-testid=password]");
    private final By confirmPassword = By.cssSelector("[data-testid=confirm-password]");
    private final By submit = By.cssSelector("[data-testid=submit]");
    private final By goLogin = By.cssSelector("[data-testid=go-login]");

    public void clickSignup() {
        driver.findElement(signupBtn).click();
    }

    public void fillSignupForm(String fn, String ln, String em, String pw, String cpw) {
        driver.findElement(firstName).clear();
        driver.findElement(firstName).sendKeys(fn);

        driver.findElement(lastName).clear();
        driver.findElement(lastName).sendKeys(ln);

        driver.findElement(email).clear();
        driver.findElement(email).sendKeys(em);

        driver.findElement(password).clear();
        driver.findElement(password).sendKeys(pw);

        driver.findElement(confirmPassword).clear();
        driver.findElement(confirmPassword).sendKeys(cpw);
    }

    public void submitSignup() {
        driver.findElement(submit).click();
    }

    public void signup(String fn, String ln, String em, String pw, String cpw) {
        clickSignup();
        fillSignupForm(fn, ln, em, pw, cpw);
        submitSignup();
    }

    public boolean isMessageDisplayed() {
        return driver.findElement(goLogin).isDisplayed();
    }

    public boolean isSignupFormDisplayed() {
        return driver.findElement(firstName).isDisplayed();
    }
}