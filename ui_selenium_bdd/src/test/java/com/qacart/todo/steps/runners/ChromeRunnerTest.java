package com.qacart.todo.runners;

import io.cucumber.testng.AbstractTestNGCucumberTests;
import io.cucumber.testng.CucumberOptions;
import org.testng.annotations.BeforeClass;

@CucumberOptions(
    features = "src/test/resources/features",
    glue = {"com.qacart.todo.steps", "com.qacart.todo.hooks"},
    plugin = {"pretty", "io.qameta.allure.cucumber7jvm.AllureCucumber7Jvm"},
    monochrome = true
)
public class ChromeRunnerTest extends AbstractTestNGCucumberTests {

  @BeforeClass(alwaysRun = true)
  public void setChrome() {
    System.setProperty("browser", "chrome");
  }
}