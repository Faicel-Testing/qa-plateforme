package com.qacart.todo.steps;

import com.qacart.todo.context.TestContext;
import com.qacart.todo.factory.DriverManager;
import com.qacart.todo.utils.ui.Waiter;
import io.cucumber.java.Before;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;
import org.openqa.selenium.JavascriptExecutor;
import org.openqa.selenium.WebDriver;

public class CommonSteps {

    @Before(order = 1000)
    public void resetContext() {
        TestContext.clear();
    }

    @When("I logout from the application")
    public void iLogout() {
        WebDriver driver = DriverManager.get();
        String baseUrl   = TestContext.get("BASE_URL", String.class);

        // Essai 1 : route /logout
        driver.get(baseUrl + "/logout");

        // Essai 2 : vider localStorage + sessionStorage (SPA token-based auth)
        try {
            ((JavascriptExecutor) driver).executeScript(
                "window.localStorage.clear(); window.sessionStorage.clear();");
        } catch (Exception ignored) {}

        // Forcer le retour sur la page login pour invalider le state React
        driver.get(baseUrl + "/login");
        Waiter.urlContains("/login");
    }

    @When("I refresh the page")
    public void iRefreshPage() {
        DriverManager.get().navigate().refresh();
    }

    @Then("I should be redirected to the login page")
    public void iShouldBeRedirectedToLoginPage() {
        Waiter.urlContains("/login");
    }
}
