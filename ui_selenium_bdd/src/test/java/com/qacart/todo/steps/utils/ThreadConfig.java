package com.qacart.todo.utils;

public final class ThreadConfig {
  private static final ThreadLocal<String> BROWSER = new ThreadLocal<>();

  private ThreadConfig() {}

  public static void setBrowser(String browser) { BROWSER.set(browser); }
  public static String browser() { return BROWSER.get(); }
  public static void clear() { BROWSER.remove(); }
}