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
    }

    @When("User fill the {string} and {string} and {string} and {string} and {string} in the field")
    public void UserFillkvTheFirstnameAndLastnameAndEmailAndPasswordAndConfirmPasswordInTheField(String firstname, String lastname, String email, String password, String confirm_password) {
        new SignupPage(driver).signup("Faysal", "Testing", "faical@exemple.com", "1234AZE", "1234AZE");

    }

    @Then("Signup is done correctly")
    public void SignupIsDoneCorrectly() {
        boolean isMessageDisplayed = new SignupPage(driver).isMessageDisplayed();
        Assert.assertTrue(isMessageDisplayed);
           
        }
    }

