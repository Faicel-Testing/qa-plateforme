package com.qacart.todo.steps.pages;

import com.qacart.todo.steps.base.BasePage;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;

public class LoginPage extends BasePage {

    public LoginPage(WebDriver driver) {
        super(driver);
    }

    private final By emailInput = By.cssSelector("[data-testid=email]");
    private final By passwordInput = By.cssSelector("[data-testid=\"password\"]");
    private final By submit = By.cssSelector("[data-testid=\"submit\"]");

    public void login(String email, String password){
        driver.findElement(emailInput).sendKeys(email);
        driver.findElement(passwordInput).sendKeys(password);
        driver.findElement(submit).click();
    }

}
