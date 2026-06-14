package com.qacart.todo.runners;

import com.qacart.todo.utils.ThreadConfig;
import io.cucumber.testng.AbstractTestNGCucumberTests;
import io.cucumber.testng.CucumberOptions;
import org.testng.annotations.*;

@CucumberOptions(
    features = "src/test/resources/features",
    glue = {"com.qacart.todo.steps", "com.qacart.todo.hooks"},
    plugin = {"pretty", "io.qameta.allure.cucumber7jvm.AllureCucumber7Jvm"},
    monochrome = true
)
public class ParallelRunnerTest extends AbstractTestNGCucumberTests {

  private String browser; // ✅ une instance par <test> dans testng.xml

  @Parameters({"browser"})
  @BeforeTest(alwaysRun = true)
  public void beforeTest(@Optional("chrome") String browser) {
    this.browser = browser;
    System.out.println("=== TestNG <test> browser = " + browser + " | Thread=" + Thread.currentThread().getId());
  }

  @BeforeMethod(alwaysRun = true)
  public void beforeMethod() {
    // ✅ important: set ThreadLocal dans le thread du scénario
    ThreadConfig.setBrowser(browser);
    System.out.println(">>> Scenario thread browser=" + ThreadConfig.browser()
        + " | Thread=" + Thread.currentThread().getId());
  }

  @AfterMethod(alwaysRun = true)
  public void afterMethod() {
    ThreadConfig.clear();
  }

  @Override
  @DataProvider(parallel = true)
  public Object[][] scenarios() {
    return super.scenarios();
  }
}