package com.qacart.todo.steps;

import com.qacart.todo.steps.factory.DriverFactory;
import com.qacart.todo.steps.pages.LoginPage;
import com.qacart.todo.steps.pages.NewTodoPage;
import com.qacart.todo.steps.pages.TodoPage;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.testng.Assert;

import java.time.Duration;

public class TodoSteps {
    WebDriver driver;
    @Given("User is in the todo page")
    public void userIsInTheTodoPage(){
        driver = DriverFactory.getDriver();
        LoginPage loginPage = new LoginPage(driver);
        loginPage.load("https://qacart-todo.herokuapp.com/");
        loginPage.login("hatem@example.com","Test1234");

    }
    @When("User add a new todo")
    public void userAddANewTodo(){
      //driver.findElement(By.cssSelector("[data-testid=add]")).click();
      new TodoPage(driver).ClickOnPlusButtonAdd();
        //driver.findElement(By.cssSelector("[data-testid=\"newtodo\"]")).sendKeys("Learn selenium");
        new NewTodoPage(driver).addTodo("Learn selenium");
        //new TodoPage(driver).SubmitNewTodo("Learn selenium")
      //driver.findElement(By.cssSelector("[data-testid=\"submit-newTask\"]")).click();
    }
    @Then("Todo should added correctly")
    public void TodoShouldAddedCorrectly(){
        String text = driver.findElement(By.cssSelector("[data-testid=todo-item]")).getText();
       Assert.assertEquals(text, "Learn selenium");
       driver.quit();

    }
}
