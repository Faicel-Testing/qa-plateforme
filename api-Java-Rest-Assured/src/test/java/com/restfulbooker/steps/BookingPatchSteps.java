package com.restfulbooker.steps;

import com.restfulbooker.client.BookingClient;
import com.restfulbooker.context.ScenarioContext;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;
import io.restassured.path.json.JsonPath;

import static org.testng.Assert.assertEquals;
import static org.testng.Assert.assertNotNull;

/**
 * Steps BDD pour booking_patch.feature -- PATCH /booking/{id}.
 * Équivalent Java de features/steps/booking_patch_steps.py.
 */
public class BookingPatchSteps {

    private final ScenarioContext ctx;

    public BookingPatchSteps(ScenarioContext ctx) {
        this.ctx = ctx;
    }

    @When("^j'envoie PATCH /booking/\\{id\\} avec \\{\"firstname\": \"UpdatedName\"\\}$")
    public void patchFirstname() {
        ctx.setResponse(ctx.getBooking().patchBooking(ctx.getBookingId(), "UpdatedName", null, null));
    }

    @When("^j'envoie PATCH /booking/\\{id\\} avec \\{\"totalprice\": 999\\}$")
    public void patchTotalprice() {
        ctx.setResponse(ctx.getBooking().patchBooking(ctx.getBookingId(), null, null, 999));
    }

    @When("^j'envoie PATCH /booking/\\{id\\} avec \\{\"lastname\": \"Updated\", \"totalprice\": 500\\}$")
    public void patchLastnameAndPrice() {
        ctx.setResponse(ctx.getBooking().patchBooking(ctx.getBookingId(), null, "Updated", 500));
    }

    @When("^j'envoie PATCH /booking/\\{id\\} sans header d'authentification$")
    public void patchNoToken() {
        ctx.setResponse(new BookingClient().patchBooking(ctx.getBookingId(), "X", null, null));
    }

    @When("^j'envoie PATCH /booking/\\{id\\} avec un token invalide$")
    public void patchInvalidToken() {
        ctx.setResponse(new BookingClient("FAKE_TOKEN_INVALID").patchBooking(ctx.getBookingId(), "X", null, null));
    }

    @When("^j'envoie PATCH /booking/9999999 avec mon token$")
    public void patchInexistant() {
        ctx.setResponse(ctx.getBooking().patchBooking(9999999, "X", null, null));
    }

    @When("^j'envoie PATCH /booking/\\{id\\} avec un body vide \\{\\}$")
    public void patchEmptyBody() {
        ctx.setResponse(ctx.getBooking().patchBookingEmpty(ctx.getBookingId()));
    }

    // ── Then : assertions PATCH ───────────────────────────────────────────────

    @Then("^la reponse contient le nouveau lastname et totalprice$")
    public void checkLastnameAndPrice() {
        JsonPath json = ctx.getResponse().jsonPath();
        assertEquals(json.getString("lastname"), "Updated", "lastname invalide");
        assertEquals(json.getInt("totalprice"), 500, "totalprice invalide");
    }

    @Then("^la reservation n'a pas ete modifiee$")
    public void checkUnchanged() {
        JsonPath json = ctx.getResponse().jsonPath();
        assertNotNull(json.get("firstname"), "Reponse inattendue apres PATCH vide");
    }
}
