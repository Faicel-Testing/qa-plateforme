package com.qacart.todo.steps.pages;

import com.qacart.todo.steps.base.BasePage;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;

import static org.openqa.selenium.By.*;

public class NewTodoPage extends BasePage {
    public NewTodoPage(WebDriver driver) {
        super(driver);
    }
   private final By remplirNewTodo = cssSelector("[data-testid=\"new-todo\"]");
   private final By clickNeweTodo = cssSelector("[data-testid=\"submit-newTask\"]");

   public void addTodo(String item){
   driver.findElement(remplirNewTodo).sendKeys("Learn selenium");
   driver.findElement(clickNeweTodo).click();
   }
}
