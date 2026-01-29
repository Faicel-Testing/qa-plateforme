package com.qacart.todo.steps.pages;

import com.qacart.todo.steps.base.BasePage;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;

public class DeleteTodoPage extends BasePage {
    public DeleteTodoPage(WebDriver driver) {
        super(driver);
    }

    private final By emailInput = By.cssSelector("[data-testid=email]");
    private final By passwordInput = By.cssSelector("[data-testid=\"password\"]");
    private final By submit = By.cssSelector("[data-testid=\"submit\"]");
    private final By addTodo = By.cssSelector("[data-testid=add]");
    private final By newTodo = By.cssSelector("[data-testid=\"new-todo\"]");
    private final By submitNewTask = By.cssSelector("[data-testid=\"submit-newTask\"]");
    private final By deleteTodo = By.cssSelector("[data-testid=\"delete\"]");

    private  final  By AddTodoPageIsDeleteDisplayed = By.cssSelector("[data-testid=\"delete\"]");

    public void DeleteTodo(String email, String password) {
        driver.findElement(emailInput).sendKeys(email);
        driver.findElement(passwordInput).sendKeys(password);
        driver.findElement(submit).click();
        driver.findElement(addTodo).click();
        driver.findElement(newTodo).sendKeys("Learn selenium");
        driver.findElement(submitNewTask).click();
       // driver.findElement(AddTodoPageIsDeleteDisplayed).isDisplayed();
    }

    public void deleteTodo() {
        driver.findElement(deleteTodo).click();

    }
    public boolean AddTodoPageIsDeleteDisplayed(){
       return driver.findElement(AddTodoPageIsDeleteDisplayed).isDisplayed();
    }
}