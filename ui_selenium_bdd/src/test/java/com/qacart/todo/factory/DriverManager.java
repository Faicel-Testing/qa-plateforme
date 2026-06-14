package com.qacart.todo.factory;

import org.openqa.selenium.WebDriver;

public final class DriverManager {
  private static final ThreadLocal<WebDriver> TL = new ThreadLocal<>();

  private DriverManager() {}

  public static WebDriver get() {
    WebDriver driver = TL.get();
    if (driver == null) {
      throw new IllegalStateException("WebDriver is not initialized for this thread.");
    }
    return driver;
  }

  public static boolean isStarted() {
    return TL.get() != null;
  }

  public static void set(WebDriver driver) { TL.set(driver); }

  public static void unload() { TL.remove(); }
}