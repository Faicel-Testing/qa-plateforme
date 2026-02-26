package com.qacart.todo.steps.hooks;

import com.qacart.todo.steps.factory.DriverFactory;
import io.cucumber.java.*;
import org.openqa.selenium.*;

public class Hooks {

    @Before
    public void setup() {
        DriverFactory.initDriver();
    }

    @AfterStep
    public void afterStep(Scenario scenario) {
        if (scenario.isFailed()) {
            try {
                WebDriver driver = DriverFactory.getDriver();
                if (driver != null) {
                    byte[] screenshot = ((TakesScreenshot) driver).getScreenshotAs(OutputType.BYTES);
                    scenario.attach(screenshot, "image/png", "FAILED_STEP_SCREENSHOT");
                }
            } catch (Exception ignored) {
                // ne pas faire échouer le teardown si screenshot impossible;
            }
        }
    }

    @After
    public void teardown() {
        WebDriver driver = DriverFactory.getDriver();
        if (driver != null) {
            driver.quit();
        }
    }
}
