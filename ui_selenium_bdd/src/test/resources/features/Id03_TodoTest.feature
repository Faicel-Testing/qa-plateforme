@ui @todo @Id03 @smoke @regression
Feature: Todo Management

  Scenario: Id03_TodoTest - user can add a todo item
    Given I have a user in fixture
    And I open the login page
    When I login using fixture user
    And I add a new todo item
    Then I should see the new todo item in the list
