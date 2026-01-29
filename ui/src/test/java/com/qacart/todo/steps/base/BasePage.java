package com.qacart.todo.steps.base;

import org.openqa.selenium.WebDriver;

public class BasePage {
    protected WebDriver driver;
    public BasePage(WebDriver driver){
        this.driver=driver;
    }
    public void load(String url){
        driver.get(url);
    }
}
