package com.restfulbooker.client;

import io.restassured.response.Response;

public class HealthClient extends BaseApiClient {

    private static final String ENDPOINT = "/ping";

    public Response ping() {
        return get(ENDPOINT);
    }
}
