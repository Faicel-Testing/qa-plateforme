package com.qacart.todo.factory;

import org.openqa.selenium.WebDriver;

public final class DriverService {

    private DriverService() {}

    public static void start() {
        WebDriver driver = DriverFactory.initDriver();
        DriverManager.set(driver);
    }

    public static void stop() {
        WebDriver driver = DriverManager.get();
        if (driver != null) {
            driver.quit();
            DriverManager.unload();
        }
    }
}