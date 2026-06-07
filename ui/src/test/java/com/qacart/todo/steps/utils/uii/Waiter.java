package com.qacart.todo.utils.ui;

import com.qacart.todo.factory.DriverManager;
import com.qacart.todo.utils.RunConfig;
import org.openqa.selenium.By;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

public final class Waiter {
  private Waiter() {}

  // ✅ rename: évite la collision avec java.lang.Object.wait()
  private static WebDriverWait waiter() {
    return new WebDriverWait(DriverManager.get(), RunConfig.timeout());
  }

  public static WebElement visible(By locator) {
    return waiter().until(ExpectedConditions.visibilityOfElementLocated(locator));
  }

  public static WebElement clickable(By locator) {
    return waiter().until(ExpectedConditions.elementToBeClickable(locator));
  }

  public static boolean urlContains(String fragment) {
    return waiter().until(ExpectedConditions.urlContains(fragment));
  }

  public static void invisibility(By locator) {
    waiter().until(ExpectedConditions.invisibilityOfElementLocated(locator));
  }
}