package com.qacart.todo.factory;

import com.qacart.todo.utilss.RunConfig;
import org.openqa.selenium.Capabilities;
import org.openqa.selenium.MutableCapabilities;
import org.openqa.selenium.chrome.ChromeOptions;
import org.openqa.selenium.firefox.FirefoxOptions;
import org.openqa.selenium.logging.LoggingPreferences;

import java.util.logging.Level;

public final class BrowserOptionsFactory {
  private BrowserOptionsFactory() {}

  public static Capabilities localCapabilities() {
    String browser = RunConfig.browser().toLowerCase();

    switch (browser) {
      case "firefox":
        return firefoxOptions();
      case "chrome":
      default:
        return chromeOptions();
    }
  }

  public static MutableCapabilities remoteCapabilities() {
    // ✅ Grid: même logique de sélection que local
    String browser = RunConfig.browser().toLowerCase();
    switch (browser) {
      case "firefox":
        return firefoxOptions();
      case "chrome":
      default:
        return chromeOptions();
    }
  }

  // ✅ PUBLIC car DriverFactory en a besoin (ChromeDriver/FirefoxDriver)
  public static ChromeOptions chromeOptions() {
    ChromeOptions co = new ChromeOptions();

    if (RunConfig.headless()) co.addArguments("--headless=new");
    co.addArguments("--window-size=1280,720");
    co.addArguments("--disable-gpu");
    co.addArguments("--no-sandbox");
    co.addArguments("--disable-notifications");

    // Browser console logs (Chrome/Chromium)
    LoggingPreferences logs = new LoggingPreferences();
    logs.enable("browser", Level.ALL);
    co.setCapability("goog:loggingPrefs", logs);

    return co;
  }

  // ✅ PUBLIC car DriverFactory en a besoin (FirefoxDriver)
  public static FirefoxOptions firefoxOptions() {
    FirefoxOptions fo = new FirefoxOptions();
    if (RunConfig.headless()) fo.addArguments("-headless");
    return fo;
  }
}