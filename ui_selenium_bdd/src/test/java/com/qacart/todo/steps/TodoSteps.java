package com.qacart.todo.steps;

import com.qacart.todo.factory.DriverManager;
import com.qacart.todo.pages.LoginPage;
import com.qacart.todo.pages.NewTodoPage;
import com.qacart.todo.pages.TodoPage;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;
import org.openqa.selenium.WebDriver;
import org.testng.Assert;
import com.qacart.todo.steps.context.ScenarioContext;

public class TodoSteps {

    private WebDriver driver;
    private final String todoItem = "Learn selenium";
    private final ScenarioContext scenarioContext = new ScenarioContext();

    @Given("User is in the todo page")
    public void userIsInTheTodoPage() {
        driver = DriverManager.get();
        LoginPage loginPage = new LoginPage(driver);
        loginPage.load("https://qacart-todo.herokuapp.com/");
        loginPage.login("hatem@example.com", "Test1234");
        Assert.assertTrue(new TodoPage(driver).isWelcomeDisplayed());
    }

    @When("User add a new todo")
    public void userAddANewTodo() {
        TodoPage todoPage = new TodoPage(driver);
        todoPage.clickAddTodo();
        new NewTodoPage(driver).addTodo(todoItem);
    }

    @Then("Todo should added correctly")
    public void todoShouldAddedCorrectly() {
        Assert.assertTrue(new TodoPage(driver).isTodoPresent(todoItem));
    }
}