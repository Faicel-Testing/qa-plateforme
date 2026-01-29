package com.qacart.todo.steps;

import com.qacart.todo.steps.factory.DriverFactory;
import com.qacart.todo.steps.pages.LoginPage;
import com.qacart.todo.steps.pages.TodoPage;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.testng.Assert;

public class UserSteps {
    WebDriver driver;
    @Given("User is at the login page")
    public void userIsAtTheLoginPage(){
        driver = DriverFactory.getDriver();
        new LoginPage(driver).load("https://qacart-todo.herokuapp.com/");
    }

    @When("User fill the email and password and login")
    public void userFillTheEmailAndPasswordAndLogin(){
        new LoginPage(driver).login("hatem@example.com","Test1234");

        }
    @Then("Welcome message should be displayed")
    public void welcomeMessageShouldBeDisplayed(){
       boolean isWelcomeDisplayed = new TodoPage(driver).isWelcomeDisplayed();
        Assert.assertTrue(isWelcomeDisplayed);
    //    driver.quit();
    }

}
