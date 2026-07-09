package com.restfulbooker.steps;

import com.restfulbooker.client.HealthClient;
import com.restfulbooker.context.ScenarioContext;
import io.cucumber.java.en.When;

/**
 * Steps BDD pour health_check.feature -- GET /ping.
 * Équivalent Java de features/steps/health_check_steps.py.
 */
public class HealthCheckSteps {

    private final ScenarioContext ctx;

    public HealthCheckSteps(ScenarioContext ctx) {
        this.ctx = ctx;
    }

    @When("^j'envoie GET /ping$")
    public void ping() {
        ctx.setResponse(new HealthClient().ping());
    }
}
