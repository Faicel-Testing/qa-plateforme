package com.qacart.todo.steps;

import com.qacart.todo.context.TestContext;
import com.qacart.todo.data.FixtureStore;
import com.qacart.todo.data.User;
import com.qacart.todo.factory.DriverManager;
import com.qacart.todo.pages.LoginPage;
import com.qacart.todo.pages.SignupPage;
import com.qacart.todo.steps.utils.EnvUtils;
import com.qacart.todo.steps.utils.data.TestDataFactory;
import com.qacart.todo.utils.ui.Waiter;
import io.cucumber.java.en.And;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;
import org.testng.Assert;

public class AuthSteps {

    private String baseUrl() {
        if (!TestContext.contains("BASE_URL")) {
            try {
                TestContext.set("BASE_URL", EnvUtils.getInstance().getURL());
            } catch (Exception e) {
                throw new RuntimeException("Cannot read BASE_URL: " + e.getMessage(), e);
            }
        }
        return TestContext.get("BASE_URL", String.class);
    }

    // ── Signup positive ────────────────────────────────────────────────────────

    @Given("I open the signup page")
    public void iOpenSignupPage() {
        new SignupPage(DriverManager.get()).open(baseUrl());
    }

    @When("I signup with a new random user")
    public void iSignupWithNewRandomUser() {
        User user = TestDataFactory.randomUser();
        TestContext.set("USER", user);
        new SignupPage(DriverManager.get()).signup(
            user.firstName, user.lastName, user.email, user.password);
    }

    @Then("I should be logged in after signup")
    public void iShouldBeLoggedInAfterSignup() {
        Waiter.urlContains("/todo");
    }

    @And("I save the created user in fixture")
    public void iSaveCreatedUserInFixture() {
        User user = TestContext.get("USER", User.class);
        FixtureStore.save(user);
    }

    // ── Signup negative ────────────────────────────────────────────────────────

    @When("I enter a valid email and mismatched passwords")
    public void iEnterMismatchedPasswords() {
        User u = TestDataFactory.randomUser();
        SignupPage page = new SignupPage(DriverManager.get());
        page.fillForm(u.firstName, u.lastName, u.email, "Password1!", "Different2!");
        page.clickSubmit();
    }

    @When("I enter an invalid email format")
    public void iEnterInvalidEmailFormat() {
        User u = TestDataFactory.randomUser();
        SignupPage page = new SignupPage(DriverManager.get());
        page.fillForm(u.firstName, u.lastName, "not-an-email", u.password, u.password);
        page.clickSubmit();
    }

    @When("I signup without first name")
    public void iSignupWithoutFirstName() {
        User u = TestDataFactory.randomUser();
        SignupPage page = new SignupPage(DriverManager.get());
        page.fillForm(null, u.lastName, u.email, u.password, u.password);
        page.clickSubmit();
    }

    @When("I signup without last name")
    public void iSignupWithoutLastName() {
        User u = TestDataFactory.randomUser();
        SignupPage page = new SignupPage(DriverManager.get());
        page.fillForm(u.firstName, null, u.email, u.password, u.password);
        page.clickSubmit();
    }

    @When("I signup without email")
    public void iSignupWithoutEmail() {
        User u = TestDataFactory.randomUser();
        SignupPage page = new SignupPage(DriverManager.get());
        page.fillForm(u.firstName, u.lastName, null, u.password, u.password);
        page.clickSubmit();
    }

    @When("I signup without password")
    public void iSignupWithoutPassword() {
        User u = TestDataFactory.randomUser();
        SignupPage page = new SignupPage(DriverManager.get());
        page.fillForm(u.firstName, u.lastName, u.email, null, null);
        page.clickSubmit();
    }

    @When("I enter a weak password")
    public void iEnterWeakPassword() {
        User u = TestDataFactory.randomUser();
        SignupPage page = new SignupPage(DriverManager.get());
        page.fillForm(u.firstName, u.lastName, u.email, "123", "123");
        page.clickSubmit();
    }

    @Then("I should see a password mismatch error")
    public void iShouldSeePasswordMismatchError() {
        Assert.assertTrue(new SignupPage(DriverManager.get()).isErrorVisible(),
            "Expected password mismatch error");
    }

    @Then("I should see an invalid email error")
    public void iShouldSeeInvalidEmailError() {
        boolean signupError = new SignupPage(DriverManager.get()).isErrorVisible();
        boolean loginError  = new LoginPage(DriverManager.get()).isErrorVisible();
        Assert.assertTrue(signupError || loginError, "Expected invalid email error");
    }

    @Then("I should see a required field error for first name")
    public void iShouldSeeRequiredFieldErrorForFirstName() {
        Assert.assertTrue(new SignupPage(DriverManager.get()).isErrorVisible(),
            "Expected required field error for first name");
    }

    @Then("I should see a required field error for last name")
    public void iShouldSeeRequiredFieldErrorForLastName() {
        Assert.assertTrue(new SignupPage(DriverManager.get()).isErrorVisible(),
            "Expected required field error for last name");
    }

    @Then("I should see a required field error for email")
    public void iShouldSeeRequiredFieldErrorForEmail() {
        boolean signupError = new SignupPage(DriverManager.get()).isErrorVisible();
        boolean loginError  = new LoginPage(DriverManager.get()).isErrorVisible();
        Assert.assertTrue(signupError || loginError, "Expected required field error for email");
    }

    @Then("I should see a required field error for password")
    public void iShouldSeeRequiredFieldErrorForPassword() {
        boolean signupError = new SignupPage(DriverManager.get()).isErrorVisible();
        boolean loginError  = new LoginPage(DriverManager.get()).isErrorVisible();
        Assert.assertTrue(signupError || loginError, "Expected required field error for password");
    }

    @Then("I should see a password strength error")
    public void iShouldSeePasswordStrengthError() {
        Assert.assertTrue(new SignupPage(DriverManager.get()).isErrorVisible(),
            "Expected password strength error");
    }

    // ── Login positive ─────────────────────────────────────────────────────────

    @Given("I have a user in fixture")
    public void iHaveUserInFixture() {
        User user = FixtureStore.load();
        if (user == null) {
            // auto-create via signup if fixture is missing
            user = TestDataFactory.randomUser();
            new SignupPage(DriverManager.get()).open(baseUrl());
            new SignupPage(DriverManager.get()).signup(
                user.firstName, user.lastName, user.email, user.password);
            Waiter.urlContains("/todo");
            FixtureStore.save(user);
            new LoginPage(DriverManager.get()).open(baseUrl());
        }
        TestContext.set("USER", user);
    }

    @Given("I open the login page")
    public void iOpenLoginPage() {
        new LoginPage(DriverManager.get()).open(baseUrl());
    }

    @When("I login using fixture user")
    public void iLoginUsingFixtureUser() {
        User user = TestContext.get("USER", User.class);
        new LoginPage(DriverManager.get()).login(user.email, user.password);
    }

    @Then("I should be logged in")
    public void iShouldBeLoggedIn() {
        new LoginPage(DriverManager.get()).assertLoggedIn();
    }

    // ── Login negative ─────────────────────────────────────────────────────────

    @When("I login with invalid credentials")
    public void iLoginWithInvalidCredentials() {
        new LoginPage(DriverManager.get()).login("invalid-user@mail.com", "WrongPass123!");
    }

    @When("I login with invalid email format")
    public void iLoginWithInvalidEmailFormat() {
        new LoginPage(DriverManager.get()).login("invalid-email", "Password123!");
    }

    @When("I login with correct email and wrong password")
    public void iLoginWithCorrectEmailWrongPassword() {
        User user = FixtureStore.load();
        if (user == null) user = new User("x", "x", "wrong@mail.com", "WrongPass!");
        new LoginPage(DriverManager.get()).login(user.email, "WrongPassword!");
    }

    @When("I login with non-existent email")
    public void iLoginWithNonExistentEmail() {
        new LoginPage(DriverManager.get())
            .login("missing" + System.currentTimeMillis() + "@mail.com", "Password123!");
    }

    @When("I login with empty email")
    public void iLoginWithEmptyEmail() {
        new LoginPage(DriverManager.get()).login("", "Password123!");
    }

    @When("I login with empty password")
    public void iLoginWithEmptyPassword() {
        new LoginPage(DriverManager.get()).login("user@example.com", "");
    }

    @When("I login with both fields empty")
    public void iLoginWithBothFieldsEmpty() {
        new LoginPage(DriverManager.get()).login("", "");
    }

    @Then("I should see a login error message")
    public void iShouldSeeLoginErrorMessage() {
        Assert.assertTrue(new LoginPage(DriverManager.get()).isErrorVisible(),
            "Expected login error message");
    }

    @Then("I should see an authentication error message")
    public void iShouldSeeAuthenticationError() {
        Assert.assertTrue(new LoginPage(DriverManager.get()).isErrorVisible(),
            "Expected authentication error message");
    }

    @Then("I should see a user not found error")
    public void iShouldSeeUserNotFoundError() {
        Assert.assertTrue(new LoginPage(DriverManager.get()).isErrorVisible(),
            "Expected user not found error");
    }

    @Then("I should see required field errors")
    public void iShouldSeeRequiredFieldErrors() {
        Assert.assertTrue(new LoginPage(DriverManager.get()).isErrorVisible(),
            "Expected required field errors");
    }
}
