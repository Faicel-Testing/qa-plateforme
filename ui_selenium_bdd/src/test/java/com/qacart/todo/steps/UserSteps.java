package com.qacart.todo.steps;

import com.qacart.todo.factory.DriverManager;
import com.qacart.todo.pages.LoginPage;
import com.qacart.todo.pages.TodoPage;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;
import org.openqa.selenium.WebDriver;
import org.testng.Assert;
import com.qacart.todo.steps.context.ScenarioContext;

public class UserSteps {

    private WebDriver driver;
    private final ScenarioContext scenarioContext = new ScenarioContext();

    @Given("User is at the login page")
    public void userIsAtTheLoginPage() {
        driver = DriverManager.get();
        new LoginPage(driver).load("https://qacart-todo.herokuapp.com/");
    }

    @When("User fill the email and password and login")
    public void userFillTheEmailAndPasswordAndLogin() {
        new LoginPage(driver).login("hatem@example.com", "Test1234");
    }

    @Then("Welcome message should be displayed")
    public void welcomeMessageShouldBeDisplayed() {
        Assert.assertTrue(new TodoPage(driver).isWelcomeDisplayed());
    }
}