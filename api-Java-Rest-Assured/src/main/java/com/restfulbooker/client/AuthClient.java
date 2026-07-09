package com.restfulbooker.client;

import com.restfulbooker.config.ConfigLoader;
import com.restfulbooker.payloads.BookingPayloads;
import io.restassured.response.Response;

import java.util.Map;

public class AuthClient extends BaseApiClient {

    private static final String ENDPOINT = "/auth";

    public Response createToken(String username, String password) {
        return post(ENDPOINT, BookingPayloads.authPayload(username, password));
    }

    public Response createToken() {
        return createToken(ConfigLoader.username(), ConfigLoader.password());
    }

    public Response createTokenEmpty() {
        return post(ENDPOINT, Map.of());
    }

    public String getToken() {
        Response response = createToken();
        return response.jsonPath().getString("token");
    }
}
