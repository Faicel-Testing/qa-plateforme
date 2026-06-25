package com.qacart.todo.listener;

import org.testng.IRetryAnalyzer;
import org.testng.ITestResult;

/**
 * Relance automatiquement un scénario échoué jusqu'à MAX_RETRIES fois.
 * TestNG crée une instance par invocation DataProvider (= par scénario Cucumber).
 */
public class RetryAnalyzer implements IRetryAnalyzer {

    private static final int MAX_RETRIES = 2;
    private int count = 0;

    @Override
    public boolean retry(ITestResult result) {
        if (count < MAX_RETRIES) {
            count++;
            System.out.printf("[RETRY] %s — tentative %d/%d%n",
                    result.getName(), count, MAX_RETRIES);
            return true;
        }
        return false;
    }
}
