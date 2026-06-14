package com.qacart.todo.utils.ui;

import com.qacart.todo.factory.DriverManager;
import org.openqa.selenium.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public final class ElementActions {
  private static final Logger log = LoggerFactory.getLogger(ElementActions.class);

  private ElementActions() {}

  public static void type(By locator, String value) {
    WebElement el = Waiter.visible(locator);
    el.clear();
    el.sendKeys(value);
    log.debug("TYPE {} => {}", locator, mask(locator, value));
  }

  public static void click(By locator) {
    try {
      Waiter.clickable(locator).click();
      log.debug("CLICK {}", locator);
    } catch (ElementClickInterceptedException | StaleElementReferenceException e) {
      log.warn("CLICK failed on {} ({}) -> JS click fallback", locator, e.getClass().getSimpleName());
      jsClick(locator);
    }
  }

  public static String text(By locator) {
    return Waiter.visible(locator).getText();
  }

  public static boolean displayed(By locator) {
    try { return Waiter.visible(locator).isDisplayed(); }
    catch (TimeoutException e) { return false; }
  }

  private static void jsClick(By locator) {
    WebElement el = Waiter.visible(locator);
    JavascriptExecutor js = (JavascriptExecutor) DriverManager.get();
    js.executeScript("arguments[0].click();", el);
  }

  private static String mask(By locator, String value) {
    String s = locator.toString().toLowerCase();
    if (s.contains("password")) return "******";
    return value;
  }
}
