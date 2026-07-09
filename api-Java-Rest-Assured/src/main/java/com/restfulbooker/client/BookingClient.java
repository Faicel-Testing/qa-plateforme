package com.restfulbooker.client;

import com.restfulbooker.payloads.BookingPayloads;
import io.restassured.response.Response;

import java.util.Map;

public class BookingClient extends BaseApiClient {

    private static final String ENDPOINT = "/booking";

    public BookingClient() {
        super();
    }

    public BookingClient(String token) {
        super(token);
    }

    // ── GET ──────────────────────────────────────────────────────────────────

    public Response getAllBookings() {
        return get(ENDPOINT);
    }

    public Response getAllBookings(Map<String, String> filters) {
        return get(ENDPOINT, filters);
    }

    public Response getBooking(Object bookingId) {
        return get(ENDPOINT + "/" + bookingId);
    }

    // ── CREATE ───────────────────────────────────────────────────────────────

    public Response createBooking() {
        return post(ENDPOINT, BookingPayloads.createBooking());
    }

    public Response createBookingMinimal() {
        return post(ENDPOINT, BookingPayloads.createBookingMinimal());
    }

    public Response createBookingWithoutField(String field) {
        return post(ENDPOINT, BookingPayloads.createBookingWithoutField(field));
    }

    public Response createBookingEmpty() {
        return post(ENDPOINT, Map.of());
    }

    public Response createBookingWithDates(String checkin, String checkout) {
        return post(ENDPOINT, BookingPayloads.createBooking(Map.of("checkin", checkin, "checkout", checkout)));
    }

    public Response createBookingWithPrice(int totalprice) {
        return post(ENDPOINT, BookingPayloads.createBooking(Map.of("totalprice", totalprice)));
    }

    public Response createBookingXss() {
        return post(ENDPOINT, BookingPayloads.createBooking(Map.of("firstname", "<script>alert(\"XSS\")</script>")));
    }

    // ── UPDATE (PUT) ─────────────────────────────────────────────────────────

    public Response updateBooking(Object bookingId, Map<String, Object> overrides) {
        return put(ENDPOINT + "/" + bookingId, BookingPayloads.updateBooking(overrides));
    }

    public Response updateBooking(Object bookingId) {
        return updateBooking(bookingId, Map.of());
    }

    public Response updateBookingWithoutField(Object bookingId, String field) {
        Map<String, Object> payload = BookingPayloads.updateBooking(Map.of());
        payload.remove(field);
        return put(ENDPOINT + "/" + bookingId, payload);
    }

    // ── PATCH ────────────────────────────────────────────────────────────────

    public Response patchBooking(Object bookingId, String firstname, String lastname, Integer totalprice) {
        return patch(ENDPOINT + "/" + bookingId, BookingPayloads.patchBooking(firstname, lastname, totalprice));
    }

    public Response patchBookingEmpty(Object bookingId) {
        return patch(ENDPOINT + "/" + bookingId, Map.of());
    }

    // ── DELETE ───────────────────────────────────────────────────────────────

    public Response deleteBooking(Object bookingId) {
        return delete(ENDPOINT + "/" + bookingId);
    }
}
