package com.qacart.todo.factory;

import org.openqa.selenium.WebDriver;

public final class DriverManager {

    private static final ThreadLocal<WebDriver> DRIVER = new ThreadLocal<>();

    private DriverManager() {}

    public static void set(WebDriver driver) {
        DRIVER.set(driver);
    }

    public static WebDriver get() {
        return DRIVER.get();
    }

    public static void unload() {
        DRIVER.remove();
    }
}