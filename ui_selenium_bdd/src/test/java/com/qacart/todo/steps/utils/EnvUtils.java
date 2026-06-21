package com.qacart.todo.steps.utils;

import java.io.IOException;
import java.util.Properties;

public class EnvUtils {
    private Properties prop;
    public static EnvUtils envUtils;

    private EnvUtils() throws IOException {
        String env = System.getProperty("env", "local").toUpperCase();
        switch (env) {
            case "PRODUCTION":
                prop = ConfigUtil.readConfig("src/test/resources/properties/production.properties");
                break;
            case "STAGING":
                prop = ConfigUtil.readConfig("src/test/resources/properties/staging.properties");
                break;
            case "LOCAL":
            default:
                prop = ConfigUtil.readConfig("src/test/resources/properties/local.properties");
                break;
        }
    }

    public static EnvUtils getInstance() throws IOException {
        envUtils = new EnvUtils();
        return envUtils;
    }

    public String getURL() {
        return prop.getProperty("URL");
    }

    public String getEmail() {
        return prop.getProperty("EMAIL", "");
    }

    public String getPassword() {
        return prop.getProperty("PASSWORD", "");
    }
}
