package com.restfulbooker.payloads;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Builders de payloads — équivalent Java de payloads/booking_payloads.py.
 */
public class BookingPayloads {

    public static Map<String, Object> createBooking() {
        return createBooking(Map.of());
    }

    /** Payload complet avec valeurs par défaut, surchargeables via {@code overrides}. */
    public static Map<String, Object> createBooking(Map<String, Object> overrides) {
        Map<String, Object> booking = new LinkedHashMap<>();
        booking.put("firstname", "Jim");
        booking.put("lastname", "Brown");
        booking.put("totalprice", 111);
        booking.put("depositpaid", true);

        Map<String, Object> dates = new LinkedHashMap<>();
        dates.put("checkin", "2025-01-01");
        dates.put("checkout", "2025-01-10");

        Map<String, Object> merged = new LinkedHashMap<>(overrides);
        if (merged.containsKey("checkin")) dates.put("checkin", merged.remove("checkin"));
        if (merged.containsKey("checkout")) dates.put("checkout", merged.remove("checkout"));
        booking.put("bookingdates", dates);
        booking.put("additionalneeds", "Breakfast");

        booking.putAll(merged);
        return booking;
    }

    public static Map<String, Object> createBookingWithoutField(String field) {
        Map<String, Object> booking = createBooking();
        booking.remove(field);
        return booking;
    }

    /** Payload sans le champ optionnel additionalneeds. */
    public static Map<String, Object> createBookingMinimal() {
        Map<String, Object> booking = new LinkedHashMap<>();
        booking.put("firstname", "Jim");
        booking.put("lastname", "Brown");
        booking.put("totalprice", 111);
        booking.put("depositpaid", true);
        Map<String, Object> dates = new LinkedHashMap<>();
        dates.put("checkin", "2025-01-01");
        dates.put("checkout", "2025-01-10");
        booking.put("bookingdates", dates);
        return booking;
    }

    public static Map<String, Object> updateBooking(Map<String, Object> overrides) {
        return createBooking(overrides);
    }

    public static Map<String, Object> patchBooking(String firstname, String lastname, Integer totalprice) {
        Map<String, Object> payload = new LinkedHashMap<>();
        if (firstname != null) payload.put("firstname", firstname);
        if (lastname != null) payload.put("lastname", lastname);
        if (totalprice != null) payload.put("totalprice", totalprice);
        return payload;
    }

    public static Map<String, Object> authPayload(String username, String password) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("username", username != null ? username : "admin");
        payload.put("password", password != null ? password : "password123");
        return payload;
    }
}
