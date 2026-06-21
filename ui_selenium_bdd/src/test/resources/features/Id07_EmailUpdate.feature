@ui @Id07 @profile @contact @wip
Feature: Email Update

  Scenario: Id07_EmailUpdate - Update email successfully
    Given I am logged in
    When I am on the Profile page
    And I update my email with a valid address
    Then a confirmation email is sent to the new address

  Scenario: Id07_EmailUpdate - Update email with already used address
    Given I am logged in
    When I am on the Profile page
    And I update my email with an already used address
    Then an error message is displayed
