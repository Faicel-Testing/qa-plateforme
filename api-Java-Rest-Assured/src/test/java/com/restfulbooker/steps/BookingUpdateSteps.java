package com.restfulbooker.steps;

import com.restfulbooker.client.BookingClient;
import com.restfulbooker.context.ScenarioContext;
import io.cucumber.java.en.When;

import java.util.Map;

/**
 * Steps BDD pour booking_update.feature -- PUT /booking/{id}.
 * Équivalent Java de features/steps/booking_update_steps.py.
 */
public class BookingUpdateSteps {

    private final ScenarioContext ctx;

    public BookingUpdateSteps(ScenarioContext ctx) {
        this.ctx = ctx;
    }

    @When("^j'envoie PUT /booking/\\{id\\} avec tous les champs et mon token \\(Cookie\\)$")
    public void putBookingValid() {
        ctx.setResponse(ctx.getBooking().updateBooking(
                ctx.getBookingId(),
                Map.of("firstname", "UpdatedJim", "lastname", "UpdatedBrown", "totalprice", 999)
        ));
    }

    @When("^j'envoie PUT /booking/\\{id\\} sans header d'authentification$")
    public void putBookingNoToken() {
        ctx.setResponse(new BookingClient().updateBooking(ctx.getBookingId()));
    }

    @When("^j'envoie PUT /booking/\\{id\\} avec un token invalide$")
    public void putBookingInvalidToken() {
        ctx.setResponse(new BookingClient("FAKE_TOKEN_INVALID").updateBooking(ctx.getBookingId()));
    }

    @When("^j'envoie PUT /booking/9999999 avec mon token$")
    public void putBookingInexistant() {
        ctx.setResponse(ctx.getBooking().updateBooking(9999999));
    }

    @When("^j'envoie PUT /booking/\\{id\\} sans le champ requis firstname$")
    public void putBookingMissingField() {
        ctx.setResponse(ctx.getBooking().updateBookingWithoutField(ctx.getBookingId(), "firstname"));
    }
}
