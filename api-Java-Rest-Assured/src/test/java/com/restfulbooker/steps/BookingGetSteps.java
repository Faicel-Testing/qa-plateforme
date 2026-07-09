package com.restfulbooker.steps;

import com.restfulbooker.context.ScenarioContext;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;
import io.restassured.path.json.JsonPath;

import java.util.Map;
import java.util.regex.Pattern;

import static org.testng.Assert.assertTrue;

/**
 * Steps BDD pour booking_get.feature -- GET /booking/{id}.
 * Équivalent Java de features/steps/booking_get_steps.py.
 */
public class BookingGetSteps {

    private static final Pattern DATE_PATTERN = Pattern.compile("^\\d{4}-\\d{2}-\\d{2}$");

    private final ScenarioContext ctx;

    public BookingGetSteps(ScenarioContext ctx) {
        this.ctx = ctx;
    }

    @When("^j'envoie GET /booking/9999999$")
    public void getBookingInexistant() {
        ctx.setResponse(ctx.getBooking().getBooking(9999999));
    }

    @When("^j'envoie GET /booking/-1$")
    public void getBookingNegatif() {
        ctx.setResponse(ctx.getBooking().getBooking(-1));
    }

    @When("^j'envoie GET /booking/abc$")
    public void getBookingString() {
        ctx.setResponse(ctx.getBooking().getBooking("abc"));
    }

    @When("^j'envoie GET /booking/0$")
    public void getBookingZero() {
        ctx.setResponse(ctx.getBooking().getBooking(0));
    }

    @Then("^les dates checkin et checkout sont au format YYYY-MM-DD$")
    public void checkDateFormat() {
        JsonPath json = ctx.getResponse().jsonPath();
        Map<String, Object> dates = json.getMap("bookingdates");
        for (String key : new String[]{"checkin", "checkout"}) {
            String value = String.valueOf(dates.get(key));
            assertTrue(DATE_PATTERN.matcher(value).matches(),
                    "Date " + key + " invalide : '" + value + "' (attendu YYYY-MM-DD)");
        }
    }
}
