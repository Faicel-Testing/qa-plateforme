package com.restfulbooker.steps;

import com.restfulbooker.context.ScenarioContext;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;
import io.restassured.path.json.JsonPath;

import java.util.Map;

import static org.testng.Assert.*;

/**
 * Steps BDD pour auth.feature -- POST /auth.
 * Équivalent Java de features/steps/auth_steps.py.
 */
public class AuthSteps {

    private final ScenarioContext ctx;

    public AuthSteps(ScenarioContext ctx) {
        this.ctx = ctx;
    }

    @When("^j'envoie POST /auth avec username \"admin\" et password \"password123\"$")
    public void postAuthValid() {
        ctx.setResponse(ctx.getAuth().createToken("admin", "password123"));
    }

    @When("^j'envoie POST /auth avec username \"wrong\" et password \"wrong\"$")
    public void postAuthInvalid() {
        ctx.setResponse(ctx.getAuth().createToken("wrong", "wrong"));
    }

    @When("^j'envoie POST /auth avec un body vide \\{\\}$")
    public void postAuthEmpty() {
        ctx.setResponse(ctx.getAuth().createTokenEmpty());
    }

    @When("^j'envoie POST /auth avec une injection SQL dans username$")
    public void postAuthSqlInjection() {
        ctx.setResponse(ctx.getAuth().createToken("' OR '1'='1", "test"));
    }

    @When("^j'envoie POST /auth avec un payload XSS dans password$")
    public void postAuthXss() {
        ctx.setResponse(ctx.getAuth().createToken("admin", "<script>alert(\"XSS\")</script>"));
    }

    // ── Then : assertions auth ────────────────────────────────────────────────

    @Then("^la reponse contient un champ \"token\" non vide$")
    public void checkTokenPresent() {
        JsonPath json = ctx.getResponse().jsonPath();
        String token = json.getString("token");
        assertNotNull(token, "Champ 'token' absent");
        assertFalse(token.isEmpty(), "Le token est vide");
    }

    @Then("^la longueur du token est superieure a 10 caracteres$")
    public void checkTokenLength() {
        String token = ctx.getResponse().jsonPath().getString("token");
        int length = token != null ? token.length() : 0;
        assertTrue(length > 10, "Token trop court (" + length + " chars) : " + token);
    }

    @Then("^la reponse contient \\{\"reason\": \"Bad credentials\"\\}$")
    public void checkBadCredentials() {
        Map<String, Object> body = ctx.getResponse().jsonPath().getMap("$");
        assertEquals(body.get("reason"), "Bad credentials", "Message d'erreur inattendu : " + body);
    }
}
