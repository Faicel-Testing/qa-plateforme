@ui @todo @Id04 @regression
Feature: Todo Deletion

  Scenario: Id04_DeleteTodoTest - user can delete a todo item
    Given I have a user in fixture
    And I open the login page
    When I login using fixture user
    And I add a new todo item
    And I delete the todo item
    Then I should not see the deleted todo item in the list

  Scenario: Id04_DeleteTodoTest - user can add a new todo after deleting one
    Given I have a user in fixture
    And I open the login page
    When I login using fixture user
    And I add a new todo item
    And I delete the todo item
    And I add a new todo item
    Then I should see the new todo item in the list
