package com.qacart.todo.steps.hooks;

import com.qacart.todo.steps.utils.quarantine.QuarantineValidator;
import io.cucumber.java.Before;
import io.cucumber.java.Scenario;

public class QuarantineHooks {

    @Before(order = 1)
    public void beforeScenario(Scenario scenario) {
        QuarantineValidator.validate(scenario.getName());
    }
}