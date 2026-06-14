package com.qacart.todo.steps.utils.quarantine;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;

import java.io.InputStream;
import java.util.Collections;
import java.util.List;
import java.util.Optional;

public class QuarantineRegistry {

    private static final String FILE_PATH = "quarantine/quarantine.json";
    private static List<QuarantineEntry> entries = Collections.emptyList();

    static {
        loadEntries();
    }

    private static void loadEntries() {
        try {
            ObjectMapper mapper = new ObjectMapper()
                    .registerModule(new JavaTimeModule())
                    .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);

            InputStream is = QuarantineRegistry.class
                    .getClassLoader()
                    .getResourceAsStream(FILE_PATH);

            if (is != null) {
                entries = mapper.readValue(is, new TypeReference<List<QuarantineEntry>>() {});
            } else {
                entries = Collections.emptyList(); // pas de fichier => pas de quarantine
            }

        } catch (Exception e) {
            // IMPORTANT: ne pas casser toute la suite de tests si parsing KO
            System.err.println("[Quarantine] Failed to load quarantine registry: " + e.getMessage());
            entries = Collections.emptyList();
        }
    }

    public static Optional<QuarantineEntry> find(String testName) {
        return entries.stream()
                .filter(e -> e.getTestName().equalsIgnoreCase(testName))
                .findFirst();
    }

    public static boolean isQuarantined(String testName) {
        return find(testName).isPresent();
    }

    public static boolean isExpired(String testName) {
        return find(testName)
                .map(QuarantineEntry::isExpired)
                .orElse(false);
    }

    public static List<QuarantineEntry> getAll() {
        return entries;
    }
}