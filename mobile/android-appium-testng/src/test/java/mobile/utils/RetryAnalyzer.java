package mobile.utils;

import org.testng.IRetryAnalyzer;
import org.testng.ITestResult;

import io.qameta.allure.Allure;

public class RetryAnalyzer implements IRetryAnalyzer {

    private int count = 0;

    @Override
    public boolean retry(ITestResult result) {

        int max = RetryRules.resolveMaxRetry(result);

        if (count < max) {
            count++;

            String msg = String.format(
                "🔁 RETRY %d/%d -> %s [%s]",
                count,
                max,
                result.getMethod().getMethodName(),
                String.join(",", result.getMethod().getGroups())
            );

            System.out.println(msg);

            try {
                Allure.addAttachment("Retry", msg);
            } catch (Exception ignored) {}

            return true;
        }

        return false;
    }
}