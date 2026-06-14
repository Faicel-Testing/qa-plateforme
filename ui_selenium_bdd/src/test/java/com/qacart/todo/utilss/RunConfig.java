package com.qacart.todo.utilss;

import java.time.Duration;

public final class RunConfig {
  private RunConfig() {}

  public static String browser() {
    return System.getProperty("browser", "chrome");
  }

  public static boolean headless() {
    return Boolean.parseBoolean(System.getProperty("headless", "true"));
  }

  public static boolean grid() {
    return Boolean.parseBoolean(System.getProperty("grid", "false"));
  }

  public static String gridUrl() {
    return System.getProperty("gridUrl", "http://localhost:4444/wd/hub");
  }

  public static Duration timeout() {
    long sec = Long.parseLong(System.getProperty("timeoutSec", "10"));
    return Duration.ofSeconds(sec);
  }
}