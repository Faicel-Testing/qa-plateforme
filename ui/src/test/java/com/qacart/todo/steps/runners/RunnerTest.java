package com.qacart.todo.steps.runners;

import io.cucumber.testng.AbstractTestNGCucumberTests;
import io.cucumber.testng.CucumberOptions;
import org.testng.annotations.DataProvider;

@CucumberOptions(
        features = "src/test/resources/features",
        glue = {"com.qacart.todo.steps"},
        tags = "not @ignore",
        plugin = {
                "pretty",
                "html:target/cucumber-reports/cucumber.html",
                "json:target/cucumber-reports/cucumber.json",
                "junit:target/cucumber-reports/cucumber.xml",
                "io.qameta.allure.cucumber7jvm.AllureCucumber7Jvm"
        },
        monochrome = true
        
)
public class RunnerTest extends AbstractTestNGCucumberTests {

    @Override
    @DataProvider(name = "scenarios", parallel = false)
    public Object[][] scenarios() {
        return super.scenarios();
    }
}
