@ui @todo @Id04 @regression
Feature: Todo Management

  Scenario: Id04_DeleteTodoTest - user can delete a todo item
    Given I have a user in fixture
    And I open the login page
    When I login using fixture user
    And I add a new todo item
    And I delete the todo item
    Then I should not see the deleted todo item in the list
