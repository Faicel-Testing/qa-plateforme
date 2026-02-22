package mobile.core;

import java.time.Duration;

import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;

import io.appium.java_client.android.AndroidDriver;

public class BaseTest {

    private static final String APP_PACKAGE = "com.todoqacart";

    @BeforeMethod(alwaysRun = true)
    public void setUp() {
        System.out.println("✅ BaseTest.setUp CALLED");

        AndroidDriver driver = DriverFactory.createDriver();
        System.out.println("✅ Driver created = " + driver);

        driver.manage().timeouts().implicitlyWait(Duration.ofSeconds(5));

        // ✅ Assure que l'app est au premier plan
        driver.activateApp(APP_PACKAGE);
    }

    public AndroidDriver getDriver() {
        return DriverFactory.getDriver();
    }

    @AfterMethod(alwaysRun = true)
    public void tearDown() {
        AndroidDriver driver = getDriver();
        if (driver != null) {
            try {
                // ✅ ferme l'app (best effort)
                driver.terminateApp(APP_PACKAGE);
            } catch (Exception ignored) {
            } finally {
                // ✅ LE PLUS IMPORTANT: ferme la session Appium
                driver.quit();
            }
        }
        DriverFactory.unload();
    }
}
