package com.restfulbooker.client;

import com.restfulbooker.config.ConfigLoader;
import io.restassured.RestAssured;
import io.restassured.response.Response;
import io.restassured.specification.RequestSpecification;

import java.util.Map;

public class BaseApiClient {

    protected final String baseUrl;
    protected final String token;

    public BaseApiClient() {
        this(null);
    }

    public BaseApiClient(String token) {
        this.baseUrl = ConfigLoader.baseUrl();
        this.token = token;
    }

    private RequestSpecification spec() {
        RequestSpecification spec = RestAssured.given()
                .baseUri(baseUrl)
                .contentType("application/json")
                .relaxedHTTPSValidation();
        if (token != null) {
            spec = spec.cookie("token", token);
        }
        return spec;
    }

    protected Response get(String endpoint) {
        return spec().get(endpoint);
    }

    protected Response get(String endpoint, Map<String, ?> queryParams) {
        if (queryParams == null || queryParams.isEmpty()) {
            return get(endpoint);
        }
        return spec().queryParams(queryParams).get(endpoint);
    }

    protected Response post(String endpoint, Object body) {
        return spec().body(body).post(endpoint);
    }

    protected Response put(String endpoint, Object body) {
        return spec().body(body).put(endpoint);
    }

    protected Response patch(String endpoint, Object body) {
        return spec().body(body).patch(endpoint);
    }

    protected Response delete(String endpoint) {
        return spec().delete(endpoint);
    }
}
