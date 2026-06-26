@ui @api-setup @regression
Feature: Todo Management — API Setup

  # Pattern Senior : utilisateur créé via POST /api/v1/users/register (pas par l'UI signup)
  # Background = précondition minimale partagée (user exists via API, zero UI signup)
  # Le login UI reste explicite dans chaque scénario — démontre l'isolation

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
    When I try to add a todo item
    Then I should see an empty todo list
