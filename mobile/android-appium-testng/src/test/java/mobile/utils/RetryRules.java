package mobile.utils;

import org.testng.ITestResult;
import mobile.config.ConfigLoader;

import java.util.Arrays;

public class RetryRules {

    public static int resolveMaxRetry(ITestResult result) {

        String[] groups = result.getMethod().getGroups();

        if (groups == null || groups.length == 0) {
            return 0;
        }

        // 🔥 Priorité quarantine > regression > smoke
        if (Arrays.stream(groups).anyMatch(g -> g.equalsIgnoreCase("quarantine"))) {
            return get("retry.max.quarantine");
        }

        if (Arrays.stream(groups).anyMatch(g -> g.equalsIgnoreCase("regression"))) {
            return get("retry.max.regression");
        }

        // smoke ou autre → pas de retry
        return 0;
    }

    private static int get(String key) {
        try {
            return ConfigLoader.getInt(key);
        } catch (Exception e) {
            return 0;
        }
    }
}