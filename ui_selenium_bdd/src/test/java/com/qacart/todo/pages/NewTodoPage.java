package com.qacart.todo.pages;

import com.qacart.todo.base.BasePage;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;

public class NewTodoPage extends BasePage {

    public NewTodoPage(WebDriver driver) {
        super(driver);
    }

    private final By newTodoInput = By.cssSelector("[data-testid=new-todo]");
    private final By submitNewTask = By.cssSelector("[data-testid=submit-newTask]");

    public void addTodo(String item) {
        driver.findElement(newTodoInput).sendKeys(item);
        driver.findElement(submitNewTask).click();
    }
}