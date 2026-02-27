package com.qacart.todo.steps;

import com.qacart.todo.steps.factory.DriverFactory;
import com.qacart.todo.steps.pages.DeleteTodoPage;
import com.qacart.todo.steps.pages.LoginPage;
import com.qacart.todo.steps.pages.NewTodoPage;
import com.qacart.todo.steps.pages.TodoPage;
import com.qacart.todo.steps.utils.EnvUtils;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.testng.Assert;

import java.io.IOException;

public class DeleteTodoSteps {
    WebDriver driver;
    @Given("User is in the add todo page")
    public void UserIsInTheAddTodoPage() throws IOException {
        driver = DriverFactory.getDriver();
        new LoginPage(driver).load("https://qacart-todo.herokuapp.com/");
        new DeleteTodoPage(driver).DeleteTodo("hatem@example.com","Test1234");
        //driver.findElement(By.cssSelector("[data-testid=email]")).sendKeys("hatem@example.com");
        //driver.findElement(By.cssSelector("[data-testid=\"password\"]")).sendKeys("Test1234");
        //driver.findElement(By.cssSelector("[data-testid=\"submit\"]")).click();
        //driver.findElement(By.cssSelector("[data-testid=add]")).click();
        //driver.findElement(By.cssSelector("[data-testid=\"newtodo\"]")).sendKeys("Learn selenium");
        //driver.findElement(By.cssSelector("[data-testid=\"submit-newTask\"]")).click();
        new TodoPage(driver).ClickOnPlusButtonAdd();
        new NewTodoPage(driver).addTodo("Learn selenium");
    }
    @When("User delete the add todo page")
    public void UserDeleteTheAddTodoPage(){
        new DeleteTodoPage(driver).deleteTodo();
        // driver.findElement(By.cssSelector("[data-testid=\"delete\"]")).click();
    }
    @Then("add todo page is delete")
    public void AddTodoPageIsDelete(){
    boolean AddTodoPageIsDeleteDisplayed = new DeleteTodoPage(driver).AddTodoPageIsDeleteDisplayed();
    Assert.assertTrue(AddTodoPageIsDeleteDisplayed);
    driver.quit();
    }
}
