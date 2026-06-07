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

public class DeleteTodoSteps {

    private WebDriver driver;
    private final String todoItem = "Learn selenium";

    @Given("User is in the add todo page")
    public void userIsInTheAddTodoPage() {
        driver = DriverManager.get();

        LoginPage loginPage = new LoginPage(driver);
        loginPage.load("https://qacart-todo.herokuapp.com/");
        loginPage.login("hatem@example.com", "Test1234");

        TodoPage todoPage = new TodoPage(driver);
        Assert.assertTrue(todoPage.isWelcomeDisplayed());

        todoPage.clickAddTodo();
        new NewTodoPage(driver).addTodo(todoItem);
        Assert.assertTrue(todoPage.isTodoPresent(todoItem));
    }

    @When("User delete the add todo page")
    public void userDeleteTheAddTodoPage() {
        new TodoPage(driver).deleteTodo(todoItem);
    }

    @Then("add todo page is delete")
    public void addTodoPageIsDelete() {
        Assert.assertFalse(new TodoPage(driver).isTodoPresent(todoItem));
    }
}