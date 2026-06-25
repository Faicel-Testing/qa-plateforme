@ui @signup @Id01 @smoke @regression @critical
Feature: Signup

  Scenario: Id01_SignupTest - user can signup successfully
    Given I open the signup page
    When I signup with a new random user
    Then I should be logged in after signup
    And I save the created user in fixture

  Scenario: Id01_SignupTest - user can add a todo item right after signup
    Given I open the signup page
    When I signup with a new random user
    And I add a new todo item
    Then I should see the new todo item in the list

  Scenario: Id01_SignupTest - user is redirected to login page after logging out
    Given I open the signup page
    When I signup with a new random user
    And I logout from the application
    Then I should be redirected to the login page
