package com.automationexercise.runners;

import org.junit.platform.suite.api.*;

@Suite
@IncludeEngines("cucumber")
@SelectClasspathResource("features")
@ConfigurationParameter(key = "cucumber.plugin", value =
        "pretty," +
        "io.qameta.allure.cucumber7jvm.AllureCucumber7Jvm," +
        "json:target/cucumber-reports/cucumber.json")
@ConfigurationParameter(key = "cucumber.publish.quiet", value = "true")
public class TestRunner {
}
