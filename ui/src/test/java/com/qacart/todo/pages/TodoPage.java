package com.qacart.todo.pages;

import com.qacart.todo.base.BasePage;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;

import java.util.List;

public class TodoPage extends BasePage {

    public TodoPage(WebDriver driver) {
        super(driver);
    }

    private final By welcomeMessage = By.xpath("//h2[normalize-space()='Ready to mark some Todos as completed?']");
    private final By addBtn = By.cssSelector("[data-testid=add]");
    private final By todoItems = By.cssSelector("[data-testid=todo-item]");
    private final By deleteBtn = By.cssSelector("[data-testid=delete]");
    private final By noTodos = By.cssSelector("[data-testid=no-todos]");

    public boolean isWelcomeDisplayed() {
        return driver.findElement(welcomeMessage).isDisplayed();
    }

    public void clickAddTodo() {
        driver.findElement(addBtn).click();
    }

    // compat si tu l’utilises déjà
    public void ClickOnPlusButtonAdd() {
        clickAddTodo();
    }

    public boolean isTodoPresent(String text) {
        List<WebElement> items = driver.findElements(todoItems);
        for (WebElement item : items) {
            if (item.getText() != null && item.getText().trim().equalsIgnoreCase(text.trim())) {
                return true;
            }
        }
        return false;
    }

    public void deleteTodo(String text) {
        List<WebElement> items = driver.findElements(todoItems);
        for (WebElement item : items) {
            if (item.getText() != null && item.getText().trim().equalsIgnoreCase(text.trim())) {
                item.findElement(deleteBtn).click();
                return;
            }
        }
        throw new AssertionError("Todo not found: " + text);
    }

    public boolean isNoTodosDisplayed() {
        return driver.findElement(noTodos).isDisplayed();
    }
}