package com.restfulbooker.context;

import com.restfulbooker.client.AuthClient;
import com.restfulbooker.client.BookingClient;
import io.restassured.response.Response;

/**
 * État mutable partagé entre toutes les step classes d'un même scénario.
 * Instance unique par scénario, injectée via cucumber-picocontainer (DI par constructeur).
 * Équivalent Java de la fixture {@code ctx} (dict) de pytest-bdd.
 */
public class ScenarioContext {

    private AuthClient auth;
    private BookingClient booking;
    private String token;
    private Object bookingId;
    private Response response;

    public AuthClient getAuth() {
        return auth;
    }

    public void setAuth(AuthClient auth) {
        this.auth = auth;
    }

    public BookingClient getBooking() {
        return booking;
    }

    public void setBooking(BookingClient booking) {
        this.booking = booking;
    }

    public String getToken() {
        return token;
    }

    public void setToken(String token) {
        this.token = token;
    }

    public Object getBookingId() {
        return bookingId;
    }

    public void setBookingId(Object bookingId) {
        this.bookingId = bookingId;
    }

    public Response getResponse() {
        return response;
    }

    public void setResponse(Response response) {
        this.response = response;
    }
}
