@ui @Id06 @profile @security @wip
Feature: Password Update

  Scenario: Id06_PasswordUpdate - Update password successfully
    Given I am logged in
    When I am on the Profile page
    And I update my password with a new valid password
    Then a success message is displayed

  Scenario: Id06_PasswordUpdate - Update password with wrong current password
    Given I am logged in
    When I am on the Profile page
    And I update my password with an incorrect current password
    Then an error message is displayed
