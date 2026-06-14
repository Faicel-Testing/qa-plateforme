package com.qacart.todo.steps;

import com.qacart.todo.factory.DriverManager;
import com.qacart.todo.pages.SignupPage;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;
import org.openqa.selenium.WebDriver;
import org.testng.Assert;
import com.qacart.todo.steps.context.ScenarioContext;

public class signupNONRegressionSteps {
    
    private WebDriver driver;
    private final ScenarioContext scenarioContext = new ScenarioContext();
    @Given("User is in the signupNONReg page")
    public void userIsInTheSignupNONRegPage() {
        driver = DriverManager.get();
        SignupPage signupPage = new SignupPage(driver);
        signupPage.load("https://qacart-todo.herokuapp.com/");
        signupPage.clickSignup();
        Assert.assertTrue(signupPage.isSignupFormDisplayed());
    }

    @When("User2 fill the {string} and {string} and {string} and {string} and {string} in the field")
    public void user2FillForm(String firstname, String lastname, String email, String password, String confirmPassword) {
        SignupPage signupPage = new SignupPage(driver);
        signupPage.fillSignupForm(firstname, lastname, email, password, confirmPassword);
        signupPage.submitSignup();
    }

    @Then("GOOD2 AFTERNOON EE should be visible")
    public void good2AfterNoonShouldBeVisible() {
        // placeholder (tu adapteras au vrai message erreur/validation)
        Assert.assertTrue(new SignupPage(driver).isSignupFormDisplayed());
    }
}