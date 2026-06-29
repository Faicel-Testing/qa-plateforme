@ui @api-setup @regression
Feature: Todo Management — API Setup

  # Senior Pattern: user created via POST /api/v1/users/register (not UI signup)
  # Background = shared minimal precondition — zero UI signup, total isolation
  # Token visible in console output → proof of REST call

  Background:
    Given I have a user created via API

  @smoke @critical
  Scenario: Id09_ApiSetup - add todo with API-created user
    Given I open the login page
    When I login using fixture user
    Then I should be logged in
    When I add a new todo item
    Then I should see the new todo item in the list

  @smoke @critical
  Scenario: Id09_ApiSetup - delete todo with API-created user
    Given I open the login page
    When I login using fixture user
    Then I should be logged in
    When I add a new todo item
    And I delete the todo item
    Then I should not see the deleted todo item in the list

  @negative
  Scenario: Id09_ApiSetup - unauthenticated user sees empty todo list
    When I navigate directly to the todo page
    Then I should see an empty todo list
