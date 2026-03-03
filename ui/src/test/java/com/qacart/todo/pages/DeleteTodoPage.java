package com.qacart.todo.pages;

import com.qacart.todo.base.BasePage;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;

public class DeleteTodoPage extends BasePage {

    public DeleteTodoPage(WebDriver driver) {
        super(driver);
    }

    private final By deleteBtn = By.cssSelector("[data-testid=delete]");

    public void deleteTodo() {
        driver.findElement(deleteBtn).click();
    }
}