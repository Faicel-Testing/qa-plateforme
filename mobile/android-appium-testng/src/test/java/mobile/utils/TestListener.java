package mobile.utils;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;

import org.openqa.selenium.OutputType;
import org.testng.ITestListener;
import org.testng.ITestResult;

import io.appium.java_client.android.AndroidDriver;
import io.qameta.allure.Allure;
import mobile.core.BaseTest;

public class TestListener implements ITestListener {

    @Override
    public void onTestFailure(ITestResult result) {

        try {
            Object testClass = result.getInstance();
            if (!(testClass instanceof BaseTest)) return;

            AndroidDriver driver = ((BaseTest) testClass).getDriver();
            if (driver == null) return;

            String testName = result.getMethod().getMethodName();
            Path outDir = Path.of("target", "debug-artifacts");
            Files.createDirectories(outDir);

            // =========================
            // 1️⃣ Screenshot
            // =========================
            byte[] screenshot = driver.getScreenshotAs(OutputType.BYTES);
            Allure.addAttachment("Screenshot - " + testName,
                    "image/png",
                    new ByteArrayInputStream(screenshot),
                    ".png");

            File screenshotFile = driver.getScreenshotAs(OutputType.FILE);
            Files.copy(
                    screenshotFile.toPath(),
                    outDir.resolve(testName + "_FAIL.png"),
                    StandardCopyOption.REPLACE_EXISTING
            );

            // =========================
            // 2️⃣ Page Source
            // =========================
            String pageSource = driver.getPageSource();

            Allure.addAttachment("PageSource - " + testName,
                    "text/xml",
                    pageSource,
                    ".xml");

            Files.writeString(
                    outDir.resolve(testName + "_PageSource.xml"),
                    pageSource
            );

            // =========================
            // 3️⃣ Logcat (peut échouer selon Appium/config)
            // =========================
            try {
                String logcat = driver.manage().logs().get("logcat").getAll().toString();

                Allure.addAttachment("Logcat - " + testName,
                        "text/plain",
                        logcat,
                        ".txt");

                Files.writeString(
                        outDir.resolve(testName + "_Logcat.txt"),
                        logcat
                );
            } catch (Exception logcatErr) {
                System.out.println("⚠️ Logcat non disponible : " + logcatErr.getMessage());
            }

            System.out.println("🧨 Debug artifacts générés pour : " + testName);

        } catch (Exception e) {
            System.out.println("⚠️ Erreur dans TestListener : " + e.getMessage());
        }
    }
}
