package com.restfulbooker.reporting;

import java.io.File;
import java.io.FileWriter;
import java.time.Instant;

public class ExecutorWriter {

    public static void writeExecutor() {
        try {
            File dir = new File("target/allure-results");
            if (!dir.exists()) {
                dir.mkdirs();
            }

            long buildOrder = Instant.now().getEpochSecond();

            String json = "{\n" +
                    "  \"name\": \"Local Execution\",\n" +
                    "  \"type\": \"local\",\n" +
                    "  \"buildName\": \"API RestAssured Run\",\n" +
                    "  \"buildOrder\": " + buildOrder + ",\n" +
                    "  \"buildUrl\": \"\",\n" +
                    "  \"reportUrl\": \"\"\n" +
                    "}";

            try (FileWriter writer = new FileWriter("target/allure-results/executor.json")) {
                writer.write(json);
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
