package com.automationexercise.config;

public class Config {
    public static final String BASE_URL = System.getProperty("base.url",
            System.getenv().getOrDefault("BASE_URL", "https://automationexercise.com"));

    public static final String TEST_EMAIL    = System.getProperty("test.email",
            System.getenv().getOrDefault("TEST_EMAIL", "test@example.com"));

    public static final String TEST_PASSWORD = System.getProperty("test.password",
            System.getenv().getOrDefault("TEST_PASSWORD", "Test@1234"));
}
