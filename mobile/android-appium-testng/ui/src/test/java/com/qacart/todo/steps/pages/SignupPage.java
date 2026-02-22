package com.qacart.todo.steps.pages;


import com.qacart.todo.steps.base.BasePage;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;

public class SignupPage extends BasePage {
    public SignupPage(WebDriver driver) {
        super(driver);
    }

    private final By signupInput = By.cssSelector("[data-testid=signup]");
    private final By firstanmeInput = By.cssSelector("[data-testid=first-name]");
    private final By lastanmeInput = By.cssSelector("[data-testid=last-name]");
    private final By emailInput = By.cssSelector("[data-testid=email]");
    private final By passwordInput = By.cssSelector("[data-testid=password]");
    private final By confirmpasswordInput = By.cssSelector("[data-testid=confirm-password]");
    private final By submit = By.cssSelector("[data-testid=submit]");
    private final By SignupIsDoneCorrectly = By.cssSelector("[data-testid=\"go-login\"]");


    public void signup(String firstname, String lastname, String email, String password, String confirmpassword) {
        driver.findElement(signupInput).click();
        driver.findElement(firstanmeInput).sendKeys(firstname);
        driver.findElement(lastanmeInput).sendKeys(lastname);
        driver.findElement(emailInput).sendKeys(email);
        driver.findElement(passwordInput).sendKeys(password);
        driver.findElement(confirmpasswordInput).sendKeys(confirmpassword);
        driver.findElement(submit).click();
        //driver.findElement(SignupIsDoneCorrectly).isDisplayed();
    }

    public boolean isMessageDisplayed() {
     return driver.findElement(SignupIsDoneCorrectly).isDisplayed();
    }
}
