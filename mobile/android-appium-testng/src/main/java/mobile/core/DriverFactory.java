package mobile.core;

import java.net.URL;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Duration;

import io.appium.java_client.android.AndroidDriver;
import io.appium.java_client.android.options.UiAutomator2Options;
import mobile.config.ConfigLoader;

public class DriverFactory {

    private static final ThreadLocal<AndroidDriver> DRIVER = new ThreadLocal<>();

    public static AndroidDriver getDriver() {
        return DRIVER.get();
    }

    public static void unload() {
        DRIVER.remove();
    }

    private static String resolveAppPath(String rawPath) {
        if (rawPath == null || rawPath.isBlank()) {
            throw new RuntimeException("app.path est vide");
        }

        Path p = Paths.get(rawPath);

        // Si relatif => on le résout depuis le dossier où tu lances Maven (user.dir)
        if (!p.isAbsolute()) {
            p = Paths.get(System.getProperty("user.dir")).resolve(rawPath).normalize();
        }

        if (!Files.exists(p)) {
            throw new RuntimeException("APK introuvable: " + p.toAbsolutePath());
        }

        return p.toAbsolutePath().toString();
    }

    public static AndroidDriver createDriver() {
        return createDriver(3);
    }

    public static AndroidDriver createDriver(int maxAttempts) {
        Exception lastException = null;
        for (int attempt = 1; attempt <= maxAttempts; attempt++) {
            try {
                AndroidDriver d = _tryCreateDriver();
                DRIVER.set(d);
                return d;
            } catch (Exception e) {
                lastException = e;
                System.out.println("⚠ Driver creation attempt " + attempt + "/" + maxAttempts + " failed: " + e.getMessage());
                if (attempt < maxAttempts) {
                    try { Thread.sleep(10000); } catch (InterruptedException ignored) {}
                }
            }
        }
        throw new RuntimeException("Erreur création AndroidDriver", lastException);
    }

    private static AndroidDriver _tryCreateDriver() throws Exception {
        try {
            boolean noReset = ConfigLoader.getBool("noReset");

            String appPath = resolveAppPath(ConfigLoader.get("app.path"));
            System.out.println("✅ APK resolved path = " + appPath);

           UiAutomator2Options options = new UiAutomator2Options()
        .setPlatformName(ConfigLoader.get("platformName"))
        .setAutomationName(ConfigLoader.get("automationName"))
        .setDeviceName(ConfigLoader.get("deviceName"))
        .setApp(appPath)
        .setNoReset(noReset)
        .setNewCommandTimeout(Duration.ofSeconds(ConfigLoader.getInt("newCommandTimeout")))
        .setAutoGrantPermissions(true);

String udid = ConfigLoader.getOptional("udid");
if (udid != null) {
    options.setUdid(udid);
}

            System.out.println("🔥 CAPABILITIES = " + options.asMap());

            AndroidDriver driver = new AndroidDriver(new URL(ConfigLoader.get("appium.url")), options);
            return driver;

        } catch (Exception e) {
            throw e;
        }
    }
}