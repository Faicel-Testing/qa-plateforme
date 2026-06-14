package com.qacart.todo.base;

import org.openqa.selenium.WebDriver;

public class BasePage {

    protected final WebDriver driver;

    public BasePage(WebDriver driver) {
        this.driver = driver;
    }

    public void load(String url) {
        driver.get(url);
    }
}