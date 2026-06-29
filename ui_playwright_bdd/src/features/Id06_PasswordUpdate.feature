@ui @id06 @profile @security
Feature: Password Update

  Background:
    Given I have a user in fixture
    And I open the login page
    When I login using fixture user
    Then I should be logged in
    And I navigate to the profile page

  Scenario: Id06_PasswordUpdate - update password successfully
    When I update my password with a valid new password
    Then a success message should be displayed

  Scenario: Id06_PasswordUpdate - update password with wrong current password
    When I update my password with an incorrect current password
    Then a password error message should be displayed
