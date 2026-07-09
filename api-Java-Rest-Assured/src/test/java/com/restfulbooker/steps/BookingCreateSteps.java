package com.restfulbooker.steps;

import com.restfulbooker.context.ScenarioContext;
import io.cucumber.java.en.When;

/**
 * Steps BDD pour booking_create.feature -- POST /booking.
 * Équivalent Java de features/steps/booking_create_steps.py.
 * (Le Then "bookingid entier > 0" est partagé avec booking_list -- voir CommonSteps.)
 */
public class BookingCreateSteps {

    private final ScenarioContext ctx;

    public BookingCreateSteps(ScenarioContext ctx) {
        this.ctx = ctx;
    }

    @When("^j'envoie POST /booking$")
    public void postBookingAllFields() {
        ctx.setResponse(ctx.getBooking().createBooking());
    }

    @When("^j'envoie POST /booking sans le champ optionnel additionalneeds$")
    public void postBookingMinimal() {
        ctx.setResponse(ctx.getBooking().createBookingMinimal());
    }

    @When("^j'envoie POST /booking avec checkin = checkout = 2026-07-01$")
    public void postBookingSameDates() {
        ctx.setResponse(ctx.getBooking().createBookingWithDates("2026-07-01", "2026-07-01"));
    }

    @When("^j'envoie POST /booking sans le champ requis firstname$")
    public void postBookingNoFirstname() {
        ctx.setResponse(ctx.getBooking().createBookingWithoutField("firstname"));
    }

    @When("^j'envoie POST /booking sans le champ requis lastname$")
    public void postBookingNoLastname() {
        ctx.setResponse(ctx.getBooking().createBookingWithoutField("lastname"));
    }

    @When("^j'envoie POST /booking sans le champ requis totalprice$")
    public void postBookingNoTotalprice() {
        ctx.setResponse(ctx.getBooking().createBookingWithoutField("totalprice"));
    }

    @When("^j'envoie POST /booking sans le champ requis depositpaid$")
    public void postBookingNoDepositpaid() {
        ctx.setResponse(ctx.getBooking().createBookingWithoutField("depositpaid"));
    }

    @When("^j'envoie POST /booking sans le champ requis bookingdates$")
    public void postBookingNoBookingdates() {
        ctx.setResponse(ctx.getBooking().createBookingWithoutField("bookingdates"));
    }

    @When("^j'envoie POST /booking avec totalprice = -100$")
    public void postBookingNegativePrice() {
        ctx.setResponse(ctx.getBooking().createBookingWithPrice(-100));
    }

    @When("^j'envoie POST /booking avec checkin posterieur a checkout$")
    public void postBookingInvertedDates() {
        ctx.setResponse(ctx.getBooking().createBookingWithDates("2026-12-31", "2026-01-01"));
    }

    @When("^j'envoie POST /booking avec un body vide \\{\\}$")
    public void postBookingEmpty() {
        ctx.setResponse(ctx.getBooking().createBookingEmpty());
    }

    @When("^j'envoie POST /booking avec un payload XSS dans firstname$")
    public void postBookingXss() {
        ctx.setResponse(ctx.getBooking().createBookingXss());
    }
}
