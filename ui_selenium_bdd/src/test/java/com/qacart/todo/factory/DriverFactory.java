package com.qacart.todo.factory;

import com.qacart.todo.utilss.RunConfig;
import io.github.bonigarcia.wdm.WebDriverManager;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.firefox.FirefoxDriver;
import org.openqa.selenium.remote.RemoteWebDriver;

import java.net.URL;

public final class DriverFactory {

    private DriverFactory() {}

    public static WebDriver initDriver() {

        try {
            // --- Selenium Grid ---
            if (RunConfig.grid()) {
                return new RemoteWebDriver(
                        new URL(RunConfig.gridUrl()),
                        BrowserOptionsFactory.remoteCapabilities()
                );
            }

            // --- Local (multi-browser) ---
            String browser = RunConfig.browser().toLowerCase();

            switch (browser) {
                case "firefox":
                    WebDriverManager.firefoxdriver().setup();
                    return new FirefoxDriver(BrowserOptionsFactory.firefoxOptions());

                case "chrome":
                default:
                    WebDriverManager.chromedriver().setup();
                    return new ChromeDriver(BrowserOptionsFactory.chromeOptions());
            }

        } catch (Exception e) {
            throw new RuntimeException("Failed to initialize driver", e);
        }
    }
}