package com.restfulbooker.steps;

import com.restfulbooker.client.BookingClient;
import com.restfulbooker.context.ScenarioContext;
import io.cucumber.java.en.When;

/**
 * Steps BDD pour booking_delete.feature -- DELETE /booking/{id}.
 * Équivalent Java de features/steps/booking_delete_steps.py.
 */
public class BookingDeleteSteps {

    private final ScenarioContext ctx;

    public BookingDeleteSteps(ScenarioContext ctx) {
        this.ctx = ctx;
    }

    @When("^j'envoie DELETE /booking/\\{id\\} avec mon token \\(Cookie\\)$")
    public void deleteBookingValid() {
        ctx.setResponse(ctx.getBooking().deleteBooking(ctx.getBookingId()));
    }

    @When("^j'envoie DELETE /booking/\\{id\\} sans header d'authentification$")
    public void deleteNoToken() {
        var respCreate = ctx.getBooking().createBooking();
        ctx.setBookingId(respCreate.jsonPath().getInt("bookingid"));
        ctx.setResponse(new BookingClient().deleteBooking(ctx.getBookingId()));
    }

    @When("^j'envoie DELETE /booking/\\{id\\} avec un token invalide$")
    public void deleteInvalidToken() {
        var respCreate = ctx.getBooking().createBooking();
        ctx.setBookingId(respCreate.jsonPath().getInt("bookingid"));
        ctx.setResponse(new BookingClient("FAKE_TOKEN_INVALID").deleteBooking(ctx.getBookingId()));
    }

    @When("^j'envoie DELETE /booking/9999999 avec mon token$")
    public void deleteInexistant() {
        ctx.setResponse(ctx.getBooking().deleteBooking(9999999));
    }

    @When("^j'envoie DELETE /booking/\\{id\\} une seconde fois$")
    public void deleteBookingTwice() {
        var resp = ctx.getBooking().createBooking();
        int bid = resp.jsonPath().getInt("bookingid");
        ctx.getBooking().deleteBooking(bid);
        ctx.setResponse(ctx.getBooking().deleteBooking(bid));
    }
}
