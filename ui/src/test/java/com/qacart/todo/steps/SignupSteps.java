package com.qacart.todo.steps;
import com.qacart.todo.steps.factory.DriverFactory;
import com.qacart.todo.steps.pages.LoginPage;
import com.qacart.todo.steps.pages.SignupPage;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.chrome.ChromeDriver;
import org.testng.Assert;

import java.time.Duration;

public class SignupSteps {
    WebDriver driver;

    @Given("User is in the signup page")
    public void UserIsInTheSignupPage() {
        driver = DriverFactory.getDriver();
        new SignupPage(driver).load("https://qacart-todo.herokuapp.com/");
        // driver.findElement(By.cssSelector("[data-testid=signup]")).click(),


    }

    @When("User fill the {string} and {string} and {string} and {string} and {string} in the field")
    public void UserFillTheFirstnameAndLastnameAndEmailAndPasswordAndConfirmPasswordInTheField(String firstname, String lastname, String email, String password, String confirm_password) {
        new SignupPage(driver).signup("Faysal", "Testing", "faical@exemple.com", "1234AZE", "1234AZE");

       //driver.findElement(By.cssSelector("[data-testid=first-name]")).sendKeys(firstname);
        //driver.findElement(By.cssSelector("[data-testid=last-name]")).sendKeys(lastname);
        //driver.findElement(By.cssSelector("[data-testid=email]")).sendKeys(email);
        //driver.findElement(By.cssSelector("[data-testid=password]")).sendKeys(password);
        //driver.findElement(By.cssSelector("[data-testid=confirm-password]")).sendKeys(confirm_password);
    }

    @Then("Signup is done correctly")
    public void SignupIsDoneCorrectly() {
        boolean isMessageDisplayed = new SignupPage(driver).isMessageDisplayed();
        Assert.assertTrue(isMessageDisplayed);
            //driver.findElement(By.cssSelector("[data-testid=submit]")).click();
        }
    }

