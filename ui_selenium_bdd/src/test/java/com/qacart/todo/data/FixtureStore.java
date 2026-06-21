package com.qacart.todo.data;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.File;
import java.io.IOException;

public final class FixtureStore {

    private static final String FIXTURE_PATH = "src/test/resources/data/user.json";
    private static final ObjectMapper MAPPER  = new ObjectMapper();

    private FixtureStore() {}

    public static void save(User user) {
        try {
            new File("src/test/resources/data").mkdirs();
            MAPPER.writerWithDefaultPrettyPrinter().writeValue(new File(FIXTURE_PATH), user);
        } catch (IOException e) {
            throw new RuntimeException("Cannot save fixture user: " + e.getMessage(), e);
        }
    }

    public static User load() {
        File f = new File(FIXTURE_PATH);
        if (!f.exists()) return null;
        try {
            return MAPPER.readValue(f, User.class);
        } catch (IOException e) {
            return null;
        }
    }
}
