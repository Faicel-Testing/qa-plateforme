package com.qacart.todo.utils.reporting;

import com.qacart.todo.factory.DriverManager;
import org.openqa.selenium.OutputType;
import org.openqa.selenium.TakesScreenshot;
import org.openqa.selenium.WebDriver;

import java.nio.charset.StandardCharsets;

public final class ArtifactManager {
  private ArtifactManager() {}

  public static byte[] screenshot() {
    WebDriver driver = DriverManager.get();
    return ((TakesScreenshot) driver).getScreenshotAs(OutputType.BYTES);
  }

  public static byte[] pageSource() {
    String html = DriverManager.get().getPageSource();
    return html.getBytes(StandardCharsets.UTF_8);
  }

  public static String currentUrl() {
    return DriverManager.get().getCurrentUrl();
  }
}
