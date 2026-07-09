package com.restfulbooker.listener;

import org.testng.IRetryAnalyzer;
import org.testng.ITestResult;

/**
 * Relance automatiquement un scénario en échec jusqu'à MAX_RETRIES fois.
 * Même logique que ui_selenium_bdd/.../listener/RetryAnalyzer.java.
 */
public class RetryAnalyzer implements IRetryAnalyzer {

    private static final int MAX_RETRIES = 2;
    private int retryCount = 0;

    @Override
    public boolean retry(ITestResult result) {
        if (retryCount < MAX_RETRIES) {
            retryCount++;
            return true;
        }
        return false;
    }
}
