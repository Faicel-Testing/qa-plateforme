@ui @api-setup @regression
Feature: Todo Management — API Setup

  # Pattern Senior : utilisateur créé via POST /api/v1/users/register (pas par l'UI signup)
  # Avantage : les tests Todo/Login sont indépendants du flux Signup
  #            → si la page Signup est cassée, ces tests passent quand même

  Background:
    Given I have a user created via API
    And I open the login page
    When I login using fixture user
    Then I should be logged in

  @smoke @critical
  Scenario: Id09_ApiSetup - add todo with API-created user
    When I add a new todo item
    Then I should see the new todo item in the list

  @smoke @critical
  Scenario: Id09_ApiSetup - delete todo with API-created user
    When I add a new todo item
    And I delete the todo item
    Then I should not see the deleted todo item in the list

  @negative
  Scenario: Id09_ApiSetup - unauthenticated user cannot access todo page
    When I try to add a todo item
    Then I should be redirected to login page
