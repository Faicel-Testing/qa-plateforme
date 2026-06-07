package com.qacart.todo.hooks;

import com.qacart.todo.factory.DriverService;
import io.cucumber.java.After;
import io.cucumber.java.Before;

public class Hooks {

    @Before
    public void beforeScenario() {
        DriverService.start();
    }

    @After
    public void afterScenario() {
        DriverService.stop();
    }
}