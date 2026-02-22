package com.qacart.todo.steps;

import com.qacart.todo.steps.factory.DriverFactory;
import com.qacart.todo.steps.pages.SignupPage;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;

public class signupNONRegressionSteps {
    WebDriver driver;

    @Given("User is in the signupNONReg page")
    public void UserIsInTheSignupNONReg_page() {
        driver = DriverFactory.getDriver();
        new SignupPage(driver).load("https://qacart-todo.herokuapp.com/");
        driver.findElement(By.cssSelector("[data-testid=signup]")).click();

    }

    @When("User2 fill the {string} and {string} and {string} and {string} and {string} in the field")
    public void User2FillTheFirstnameAndLastnameAndEmailAndPasswordAndConfirmPasswordInTheField(String firstname, String lastname, String email, String password, String confirm_password) {
       // new SignupPage(driver).signup("Faysal", "Testing", "faical@exemple.com", "1234AZE", "1234AZE");

        driver.findElement(By.cssSelector("[data-testid=first-name]")).sendKeys(firstname);
        driver.findElement(By.cssSelector("[data-testid=last-name]")).sendKeys(lastname);
        driver.findElement(By.cssSelector("[data-testid=email]")).sendKeys(email);
        driver.findElement(By.cssSelector("[data-testid=password]")).sendKeys(password);
        driver.findElement(By.cssSelector("[data-testid=confirm-password]")).sendKeys(confirm_password);
    }

    @Then("GOOD2 AFTERNOON EE should be visible")
    public void GOOD2AFTERNOONEEshouldbevisible() {
        // boolean isMessageDisplayed = driver.findElement(By.cssSelector("[data-testid=\"go-login\"]")).isDisplayed();
        // Assert.assertTrue(isMessageDisplayed);
        //driver.findElement(By.cssSelector("[data-testid=submit]")).click();
    }
}
