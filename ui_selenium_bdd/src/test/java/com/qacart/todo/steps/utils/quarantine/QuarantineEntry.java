package com.qacart.todo.steps.utils.quarantine;

import java.time.LocalDate;

public class QuarantineEntry {

    private String testName;
    private String reason;
    private LocalDate expirationDate;

    public QuarantineEntry() {}

    public QuarantineEntry(String testName, String reason, LocalDate expirationDate) {
        this.testName = testName;
        this.reason = reason;
        this.expirationDate = expirationDate;
    }

    public String getTestName() {
        return testName;
    }

    public String getReason() {
        return reason;
    }

    public LocalDate getExpirationDate() {
        return expirationDate;
    }

    public boolean isExpired() {
        return LocalDate.now().isAfter(expirationDate);
    }

    @Override
    public String toString() {
        return "QuarantineEntry{" +
                "testName='" + testName + '\'' +
                ", reason='" + reason + '\'' +
                ", expirationDate=" + expirationDate +
                '}';
    }
}