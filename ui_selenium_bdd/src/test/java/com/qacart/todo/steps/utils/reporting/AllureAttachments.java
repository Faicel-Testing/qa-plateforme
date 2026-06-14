package com.qacart.todo.steps.utils.reporting;

import com.qacart.todo.factory.DriverManager;
import io.qameta.allure.Allure;
import io.qameta.allure.Attachment;
import org.openqa.selenium.OutputType;
import org.openqa.selenium.TakesScreenshot;
import java.io.File;
import java.io.FileInputStream;
import org.openqa.selenium.logging.LogEntries;
import org.openqa.selenium.logging.LogType;

import org.openqa.selenium.remote.RemoteWebDriver;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;

public final class AllureAttachments {

  private AllureAttachments() {}

  // Version sûre: crée un vrai attachment fichier côté allure-results
  public static void addText(String name, String message) {
    Allure.addAttachment(name, "text/plain",
        new ByteArrayInputStream(message.getBytes(StandardCharsets.UTF_8)), ".txt");
  }

  public static void addScreenshot(String name) {
    byte[] bytes = ((TakesScreenshot) DriverManager.get()).getScreenshotAs(OutputType.BYTES);
    Allure.addAttachment(name, "image/png", new ByteArrayInputStream(bytes), ".png");
  }

  public static void addPageSource(String name) {
    byte[] bytes = DriverManager.get().getPageSource().getBytes(StandardCharsets.UTF_8);
    Allure.addAttachment(name, "text/html", new ByteArrayInputStream(bytes), ".html");
  }

  public static void addUrl(String name) {
    addText(name, DriverManager.get().getCurrentUrl());
  }

  public static void addFile(String name, String path, String mime, String ext) {
  try (FileInputStream fis = new FileInputStream(new File(path))) {
    Allure.addAttachment(name, mime, fis, ext);
  } catch (Exception e) {
    addText("ATTACHMENT ERROR", "Cannot attach file: " + path + " => " + e);
  }
}

public static void addDriverInfo() {
  try {
    var d = DriverManager.get();
    if (d instanceof RemoteWebDriver) {
      RemoteWebDriver r = (RemoteWebDriver) d;
      addText("SessionId", String.valueOf(r.getSessionId()));
      addText("Capabilities", String.valueOf(r.getCapabilities()));
    } else {
      addText("DriverInfo", d.getClass().getName());
    }
  } catch (Exception e) {
    addText("ATTACHMENT ERROR", e.toString());
  }
}

public static void addBrowserConsoleLogs() {
  try {
    LogEntries entries = DriverManager.get().manage().logs().get(LogType.BROWSER);
    StringBuilder sb = new StringBuilder();
    entries.forEach(e -> sb.append(e.getLevel())
        .append(" | ")
        .append(e.getTimestamp())
        .append(" | ")
        .append(e.getMessage())
        .append("\n"));
    addText("Browser console logs", sb.length() == 0 ? "No console logs" : sb.toString());
  } catch (Exception e) {
    addText("Browser console logs", "Not available: " + e);
  }
}
}