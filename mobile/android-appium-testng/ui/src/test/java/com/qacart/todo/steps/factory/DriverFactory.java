package com.qacart.todo.steps.factory;

import org.openqa.selenium.WebDriver;
import org.openqa.selenium.chrome.ChromeOptions;
import org.openqa.selenium.remote.RemoteWebDriver;

import java.net.URL;
import java.time.Duration;

public class DriverFactory {

    private static WebDriver driver;

    public static WebDriver initDriver() {
        try {
            boolean isCI = "true".equalsIgnoreCase(System.getenv("CI"));
            String remoteUrl = System.getenv("SELENIUM_REMOTE_URL");

            ChromeOptions options = new ChromeOptions();

            if (isCI) {
                options.addArguments("--headless=new");
                options.addArguments("--no-sandbox");
                options.addArguments("--disable-dev-shm-usage");
                options.addArguments("--disable-gpu");
                options.addArguments("--window-size=1920,1080");

                driver = new RemoteWebDriver(new URL(remoteUrl), options);
            } else {
                driver = new org.openqa.selenium.chrome.ChromeDriver(options);
            }

            driver.manage().timeouts().implicitlyWait(Duration.ofSeconds(5));
            return driver;

        } catch (Exception e) {
            throw new RuntimeException("Failed to initialize driver", e);
        }
    }

    public static WebDriver getDriver() {
        return driver;
    }
}
