package com.qacart.todo.pages;

import com.qacart.todo.base.BasePage;
import com.qacart.todo.utils.ui.ElementActions;
import com.qacart.todo.utils.ui.Waiter;
import org.openqa.selenium.By;
import org.openqa.selenium.JavascriptExecutor;
import org.openqa.selenium.NoSuchElementException;
import org.openqa.selenium.StaleElementReferenceException;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

import java.time.Duration;
import java.util.List;

public class TodoPage extends BasePage {

    private static final By ADD_BTN     = By.cssSelector("button:has(svg[data-testid='add'])");
    private static final By LOGOUT_BTN  = By.cssSelector("[data-testid='logout']");
    private static final By NEW_TODO    = By.cssSelector("input[data-testid='new-todo']");
    private static final By SUBMIT_TODO = By.cssSelector("button[data-testid='submit-newTask']");
    private static final By TODO_ITEMS  = By.cssSelector("[data-testid='todo-item']");
    private static final By FIELD_ERROR = By.cssSelector(".MuiFormHelperText-root.Mui-error");
    private static final By ALERT_ERROR = By.cssSelector(".MuiAlert-message");

    public TodoPage(WebDriver driver) {
        super(driver);
    }

    public void open(String baseUrl) {
        load(baseUrl + "/todo");
        Waiter.visible(ADD_BTN);
    }

    public void clickLogout() {
        Waiter.visible(LOGOUT_BTN);
        ElementActions.click(LOGOUT_BTN);
    }

    public String addTodo(String text) {
        ElementActions.click(ADD_BTN);
        Waiter.urlContains("/todo/new");
        ElementActions.type(NEW_TODO, text);
        ElementActions.click(SUBMIT_TODO);
        Waiter.urlContains("/todo");
        return text;
    }

    public void attemptAddTodo(String text) {
        ElementActions.click(ADD_BTN);
        Waiter.urlContains("/todo/new");
        Waiter.visible(NEW_TODO);
        if (text != null && !text.isEmpty()) {
            ElementActions.type(NEW_TODO, text);
        }
        ElementActions.click(SUBMIT_TODO);
    }

    // Fix: attend la disparition de l'item après clic delete
    public boolean deleteTodo(String text) {
        WebDriverWait wait = new WebDriverWait(driver, Duration.ofSeconds(25));
        // Wait for list to be rendered before searching
        try { wait.until(d -> !driver.findElements(TODO_ITEMS).isEmpty() ||
                              !d.getCurrentUrl().contains("/todo/new")); }
        catch (Exception ignored) {}

        List<WebElement> items = driver.findElements(TODO_ITEMS);
        for (WebElement item : items) {
            try {
                if (item.getText().contains(text)) {
                    WebElement deleteBtn = item.findElement(By.cssSelector("[data-testid='delete']"));
                    deleteBtn.click();
                    // Wait for the item to disappear from DOM
                    By itemLocator = By.xpath(
                        "//*[@data-testid='todo-item'][contains(.,'" + text + "')]");
                    wait.until(ExpectedConditions.invisibilityOfElementLocated(itemLocator));
                    return true;
                }
            } catch (StaleElementReferenceException | NoSuchElementException e) {
                // Item may have already disappeared — treat as deleted
                return true;
            }
        }
        return false;
    }

    public boolean isTodoVisible(String text) {
        try {
            List<WebElement> items = driver.findElements(TODO_ITEMS);
            return items.stream().anyMatch(el -> {
                try { return el.getText().contains(text); }
                catch (StaleElementReferenceException e) { return false; }
            });
        } catch (Exception e) {
            return false;
        }
    }

    public void assertTodoPresent(String text) {
        // If Chrome 149 headless clears localStorage on refresh, React redirects to /login.
        // Wait up to 20s for ADD_BTN to confirm we're still on the todo page.
        new WebDriverWait(driver, Duration.ofSeconds(20))
            .until(ExpectedConditions.visibilityOfElementLocated(ADD_BTN));
        // API fetch: 60s for todo to appear (covers Heroku cold-start latency)
        new WebDriverWait(driver, Duration.ofSeconds(60))
            .until(d -> isTodoVisible(text));
    }

    public void assertTodoAbsent(String text) {
        new WebDriverWait(driver, Duration.ofSeconds(8))
            .until(ExpectedConditions.invisibilityOfElementLocated(
                By.xpath("//*[@data-testid='todo-item'][contains(.,'" + text + "')]")));
    }

    public boolean isErrorVisible() {
        return ElementActions.displayed(FIELD_ERROR) || ElementActions.displayed(ALERT_ERROR);
    }
}
