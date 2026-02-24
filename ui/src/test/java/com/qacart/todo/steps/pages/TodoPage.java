package com.qacart.todo.steps.pages;

import com.qacart.todo.steps.base.BasePage;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;

public class TodoPage extends BasePage {
    public TodoPage(WebDriver driver) {
        super(driver);
    }
    // private final By welcomeMessage = By.cssSelector("[data-testid=\"welcome\"]");
    private final By welcomeMessage = By.xpath("//h2[normalize-space()='Ready to mark some Todos as completed?']");
    //The email and password
    private final By plusButton = By.cssSelector("[data-testid=add]");
    //private final By DeleteTheAddTodoPage = By.cssSelector("[data-testid=\"delete\"]");
    private final By TodoPageIsDeleteDisplayed = By.cssSelector("[data-testid=\"no-todos\"]");
    private final By TodoShouldAddedCorrectly = By.cssSelector("[data-testid=todo-item]");
    private final By remplirNewTodo = By.cssSelector("[data-testid=\"new-todo\"]");
    private final By submitClick = new By.ByCssSelector("[data-testid=\"submit-newTask\"]");

   // public void SubmitNewTodo(String item){
   // driver.findElement(remplirNewTodo).sendKeys(item);
   // driver.findElement(submitClick).click();
   // }

    //private final By addedTodo = By.cssSelector("[data-testid=\"newtodo\"]");
   //driver.findElement(By.cssSelector("[data-testid=\"newtodo\"]")).sendKeys("Learn selenium");

    public void ClickOnPlusButtonAdd(){
    driver.findElement(plusButton).click();
    }
    public boolean isWelcomeDisplayed(){
    return driver.findElement(welcomeMessage).isDisplayed();
    }

    //public String getLastTodoSteps(){
      //  return driver.findElements(TodoShouldAddedCorrectly).getText();
    //}
}
