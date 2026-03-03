package com.qacart.todo.steps;

import com.qacart.todo.factory.DriverManager;
import com.qacart.todo.pages.SignupPage;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;
import org.openqa.selenium.WebDriver;
import org.testng.Assert;

public class SignupSteps {

    private WebDriver driver;

    @Given("User is in the signup page")
    public void userIsInTheSignupPage() {
        driver = DriverManager.get();
        new SignupPage(driver).load("https://qacart-todo.herokuapp.com/");
    }

    @When("User fill the {string} and {string} and {string} and {string} and {string} in the field")
    public void userFillTheForm(String firstname, String lastname, String email, String password, String confirmPassword) {
        new SignupPage(driver).signup(firstname, lastname, email, password, confirmPassword);
    }

    @Then("Signup is done correctly")
    public void signupIsDoneCorrectly() {
        Assert.assertTrue(new SignupPage(driver).isMessageDisplayed());
    }
}