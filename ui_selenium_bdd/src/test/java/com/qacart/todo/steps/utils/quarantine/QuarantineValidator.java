package com.qacart.todo.steps.utils.quarantine;

public class QuarantineValidator {

    public static void validate(String testName) {

        if (!QuarantineRegistry.isQuarantined(testName)) {
            return;
        }

        if (QuarantineRegistry.isExpired(testName)) {
            throw new RuntimeException(
                    "⚠ Test " + testName + " quarantine expired! Remove it from quarantine registry."
            );
        }

        System.out.println("🟡 Test in quarantine: " + testName);
    }
}