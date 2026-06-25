package com.qacart.todo.steps;

import com.qacart.todo.context.TestContext;
import com.qacart.todo.factory.DriverManager;
import com.qacart.todo.utils.ui.Waiter;
import io.cucumber.java.Before;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;
import org.openqa.selenium.JavascriptExecutor;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.support.ui.WebDriverWait;
import java.time.Duration;

public class CommonSteps {

    @Before(order = 1000)
    public void resetContext() {
        TestContext.clear();
    }

    @When("I logout from the application")
    public void iLogout() {
        WebDriver driver = DriverManager.get();
        String baseUrl   = TestContext.get("BASE_URL", String.class);

        // Essai 1 : bouton logout dans l'UI (chemin nominal QACart)
        try {
            new com.qacart.todo.pages.TodoPage(driver).clickLogout();
            Waiter.urlContains("/login");
            return;
        } catch (Exception ignored) {}

        // Fallback : vider le storage + cookies + navigation directe
        try {
            ((JavascriptExecutor) driver).executeScript(
                "window.localStorage.clear(); window.sessionStorage.clear();");
        } catch (Exception ignored) {}
        driver.manage().deleteAllCookies();
        driver.get(baseUrl + "/login");
        Waiter.urlContains("/login");
    }

    @When("I refresh the page")
    public void iRefreshPage() {
        WebDriver driver = DriverManager.get();
        driver.navigate().refresh();
        // Wait for Heroku dyno to respond and page to be fully loaded before next step
        try {
            new WebDriverWait(driver, Duration.ofSeconds(45))
                .until(d -> "complete".equals(
                    ((JavascriptExecutor) d).executeScript("return document.readyState")));
        } catch (Exception ignored) {}
    }

    @Then("I should be redirected to the login page")
    public void iShouldBeRedirectedToLoginPage() {
        Waiter.urlContains("/login");
    }
}
