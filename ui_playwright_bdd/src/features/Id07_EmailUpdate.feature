@ui @id07 @profile @contact
Feature: Email Update

  Background:
    Given I have a user in fixture
    And I open the login page
    When I login using fixture user
    Then I should be logged in
    And I navigate to the profile page

  Scenario: Id07_EmailUpdate - update email successfully
    When I update my email with a valid new address
    Then a success message should be displayed

  Scenario: Id07_EmailUpdate - update email with already used address
    When I update my email with an already registered address
    Then an email error message should be displayed
