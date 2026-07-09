package com.restfulbooker.config;

import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.Properties;

public class ConfigLoader {

    private static final Properties props = new Properties();

    static {
        String env = System.getProperty("env", "local");
        String path = "src/test/resources/properties/" + env + ".properties";
        try (InputStream is = new FileInputStream(path)) {
            props.load(is);
        } catch (IOException e) {
            throw new RuntimeException("Impossible de charger " + path, e);
        }
    }

    public static String get(String key) {
        String sysProp = System.getProperty(key);
        if (sysProp != null && !sysProp.isBlank()) {
            return sysProp.trim();
        }
        String envVal = System.getenv(key);
        if (envVal != null && !envVal.isBlank()) {
            return envVal.trim();
        }
        return props.getProperty(key);
    }

    public static String baseUrl() {
        return get("BASE_URL");
    }

    public static String username() {
        return get("API_USERNAME");
    }

    public static String password() {
        return get("API_PASSWORD");
    }
}
