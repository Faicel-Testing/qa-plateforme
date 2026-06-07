@ui @signup @Id01 @smoke @regression @critical
Feature: Signup

  Scenario: Id01_SignupTest - user can signup successfully
    Given I open the signup page
    When I signup with a new random user
    Then I should be logged in after signup
    And I save the created user in fixture
