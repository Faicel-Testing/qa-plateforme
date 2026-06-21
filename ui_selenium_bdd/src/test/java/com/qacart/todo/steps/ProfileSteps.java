package com.qacart.todo.steps;

import io.cucumber.java.PendingException;
import io.cucumber.java.en.And;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

public class ProfileSteps {

    @Given("I am logged in")
    public void iAmLoggedIn() {
        throw new PendingException("Profile features not yet implemented in QACart");
    }

    @When("I am on the Profile page")
    public void iAmOnProfilePage() {
        throw new PendingException("Profile page not yet implemented in QACart");
    }

    @When("I update my password with a new valid password")
    public void iUpdatePasswordValid() {
        throw new PendingException();
    }

    @When("I update my password with an incorrect current password")
    public void iUpdatePasswordWrongCurrent() {
        throw new PendingException();
    }

    @Then("a success message is displayed")
    public void aSuccessMessageIsDisplayed() {
        throw new PendingException();
    }

    @Then("an error message is displayed")
    public void anErrorMessageIsDisplayed() {
        throw new PendingException();
    }

    @When("I update my email with a valid address")
    public void iUpdateEmailValid() {
        throw new PendingException();
    }

    @When("I update my email with an already used address")
    public void iUpdateEmailDuplicate() {
        throw new PendingException();
    }

    @Then("a confirmation email is sent to the new address")
    public void aConfirmationEmailIsSent() {
        throw new PendingException();
    }

    @When("I confirm account deletion")
    public void iConfirmAccountDeletion() {
        throw new PendingException();
    }

    @When("I cancel account deletion")
    public void iCancelAccountDeletion() {
        throw new PendingException();
    }

    @Then("I am redirected to the home page")
    public void iAmRedirectedToHomePage() {
        throw new PendingException();
    }

    @Then("the deletion is cancelled")
    public void theDeletionIsCancelled() {
        throw new PendingException();
    }
}
