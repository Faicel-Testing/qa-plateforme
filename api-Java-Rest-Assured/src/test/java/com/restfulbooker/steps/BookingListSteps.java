package com.restfulbooker.steps;

import com.restfulbooker.context.ScenarioContext;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

import java.util.List;
import java.util.Map;

import static org.testng.Assert.assertEquals;
import static org.testng.Assert.assertTrue;

/**
 * Steps BDD pour booking_list.feature -- GET /booking.
 * Équivalent Java de features/steps/booking_list_steps.py.
 */
public class BookingListSteps {

    private final ScenarioContext ctx;

    public BookingListSteps(ScenarioContext ctx) {
        this.ctx = ctx;
    }

    @When("^j'envoie GET /booking$")
    public void getBookingList() {
        ctx.setResponse(ctx.getBooking().getAllBookings());
    }

    @When("^j'envoie GET /booking avec le filtre \\?firstname=Jim$")
    public void getFilterFirstnameJim() {
        ctx.setResponse(ctx.getBooking().getAllBookings(Map.of("firstname", "Jim")));
    }

    @When("^j'envoie GET /booking avec le filtre \\?lastname=Brown$")
    public void getFilterLastnameBrown() {
        ctx.setResponse(ctx.getBooking().getAllBookings(Map.of("lastname", "Brown")));
    }

    @When("^j'envoie GET /booking avec le filtre \\?checkin=2018-01-01$")
    public void getFilterCheckin() {
        ctx.setResponse(ctx.getBooking().getAllBookings(Map.of("checkin", "2018-01-01")));
    }

    @When("^j'envoie GET /booking avec le filtre \\?checkout=2019-01-01$")
    public void getFilterCheckout() {
        ctx.setResponse(ctx.getBooking().getAllBookings(Map.of("checkout", "2019-01-01")));
    }

    @When("^j'envoie GET /booking avec \\?firstname=XYZ_INEXISTANT$")
    public void getFilterUnknownFirstname() {
        ctx.setResponse(ctx.getBooking().getAllBookings(Map.of("firstname", "XYZ_INEXISTANT_99999")));
    }

    @When("^j'envoie GET /booking avec une injection SQL dans le filtre firstname$")
    public void getFilterSqlInjection() {
        ctx.setResponse(ctx.getBooking().getAllBookings(Map.of("firstname", "' OR '1'='1")));
    }

    // ── Then : assertions liste ───────────────────────────────────────────────

    @Then("^la reponse est une liste de reservations$")
    public void checkBookingList() {
        List<?> body = ctx.getResponse().jsonPath().getList("$");
        assertTrue(body != null, "Attendu une liste");
    }

    @Then("^la reponse est une liste vide \\[\\]$")
    public void checkEmptyList() {
        List<?> body = ctx.getResponse().jsonPath().getList("$");
        assertEquals(body.size(), 0, "Attendu [], recu " + body.size() + " element(s) : " + body);
    }
}
