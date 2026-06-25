package com.qacart.todo.listener;

import com.qacart.todo.steps.utils.reporting.EnvironmentWriter;
import com.qacart.todo.steps.utils.reporting.ExecutorWriter;
import org.testng.ISuite;
import org.testng.ISuiteListener;
import org.testng.ISuiteResult;
import org.testng.ITestContext;

import java.io.File;
import java.io.IOException;
import java.nio.file.*;

/**
 * TestNG suite listener — injecte dans target/allure-results :
 *   - categories.json   : classification des échecs (Infrastructure / Product / Framework)
 *   - environment.properties : KPIs calculés dynamiquement (pass rate, gate, durée…)
 *   - history/          : copie depuis le dernier rapport pour activer le Trend Allure
 */
public class AllureSuiteListener implements ISuiteListener {

    private long startTime;

    @Override
    public void onStart(ISuite suite) {
        startTime = System.currentTimeMillis();
        new File("target/allure-results").mkdirs();
        writeCategoriesJson();
        copyAllureHistory();
        try { ExecutorWriter.writeExecutor(); } catch (Exception ignored) {}
    }

    @Override
    public void onFinish(ISuite suite) {
        long durationMs = System.currentTimeMillis() - startTime;

        int passed = 0, failed = 0, skipped = 0;
        for (ISuiteResult result : suite.getResults().values()) {
            ITestContext ctx = result.getTestContext();
            passed  += ctx.getPassedTests().getAllResults().size();
            failed  += ctx.getFailedTests().getAllResults().size();
            skipped += ctx.getSkippedTests().getAllResults().size();
        }

        EnvironmentWriter.write(passed, failed, skipped, durationMs);
    }

    // ── categories.json ────────────────────────────────────────────────────────

    private void writeCategoriesJson() {
        String json = "[\n" +
            "  {\n" +
            "    \"name\": \"Infrastructure Issues\",\n" +
            "    \"messageRegex\": \".*TimeoutException.*|.*WebDriverException.*|.*ERR_NAME_NOT_RESOLVED.*|.*SessionNotCreatedException.*|.*Failed to initialize driver.*\",\n" +
            "    \"matchedStatuses\": [\"failed\", \"broken\"]\n" +
            "  },\n" +
            "  {\n" +
            "    \"name\": \"Product Defects\",\n" +
            "    \"messageRegex\": \".*AssertionError.*|.*AssertionFailedError.*|.*expected.*but was.*\",\n" +
            "    \"matchedStatuses\": [\"failed\"]\n" +
            "  },\n" +
            "  {\n" +
            "    \"name\": \"Test Framework Errors\",\n" +
            "    \"matchedStatuses\": [\"broken\"]\n" +
            "  }\n" +
            "]";
        writeFile("target/allure-results/categories.json", json);
    }

    // ── history copy for Trend chart ───────────────────────────────────────────

    private void copyAllureHistory() {
        Path src  = Path.of("target/allure-report/history");
        Path dest = Path.of("target/allure-results/history");
        if (!Files.exists(src)) return;
        try {
            dest.toFile().mkdirs();
            try (var stream = Files.walk(src)) {
                stream.forEach(s -> {
                    try {
                        Path d = dest.resolve(src.relativize(s));
                        if (Files.isDirectory(s)) d.toFile().mkdirs();
                        else Files.copy(s, d, StandardCopyOption.REPLACE_EXISTING);
                    } catch (IOException ignored) {}
                });
            }
        } catch (Exception e) {
            System.err.println("[AllureSuiteListener] history copy failed: " + e.getMessage());
        }
    }

    // ── helpers ────────────────────────────────────────────────────────────────

    private void writeFile(String path, String content) {
        try { Files.writeString(Path.of(path), content); }
        catch (Exception e) { System.err.println("[AllureSuiteListener] write failed " + path + ": " + e.getMessage()); }
    }
}
