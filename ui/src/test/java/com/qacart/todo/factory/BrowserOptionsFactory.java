package com.qacart.todo.factory;

import com.qacart.todo.utils.RunConfig;
import org.openqa.selenium.Capabilities;
import org.openqa.selenium.MutableCapabilities;
import org.openqa.selenium.chrome.ChromeOptions;
import org.openqa.selenium.firefox.FirefoxOptions;

public final class BrowserOptionsFactory {
  private BrowserOptionsFactory() {}

  public static Capabilities localCapabilities() {
    String browser = RunConfig.browser().toLowerCase();

    switch (browser) {
      case "firefox":
        FirefoxOptions fo = new FirefoxOptions();
        if (RunConfig.headless()) fo.addArguments("-headless");
        return fo;

      case "chrome":
      default:
        ChromeOptions co = new ChromeOptions();
        if (RunConfig.headless()) co.addArguments("--headless=new");
        co.addArguments("--window-size=1280,720");
        co.addArguments("--disable-gpu");
        co.addArguments("--no-sandbox");
        return co;
    }
  }

  public static MutableCapabilities remoteCapabilities() {
    // Selenium Grid accepte les mêmes capabilities
    return (MutableCapabilities) localCapabilities();
  }
}
