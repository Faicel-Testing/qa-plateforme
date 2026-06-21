@ui @todo @Id04 @negative @regression
Feature: Todo Deletion Validation

  Scenario: Id04_DeleteNegative - deleting non-existent todo should fail
    Given I have a user in fixture
    And I open the login page
    When I login using fixture user
    And I try to delete a non-existent todo item
    Then I should see an error or the deletion should be prevented

  Scenario: Id04_DeleteNegative - deleting already deleted todo should fail
    Given I have a user in fixture
    And I open the login page
    When I login using fixture user
    And I add a new todo item
    And I delete the todo item
    And I try to delete the same todo item again
    Then I should see an error or the deletion should fail

  Scenario: Id04_DeleteNegative - deleted todo should not reappear after refresh
    Given I have a user in fixture
    And I open the login page
    When I login using fixture user
    And I add a new todo item
    And I delete the todo item
    And I refresh the page
    Then I should not see the deleted todo item in the list

  Scenario: Id04_DeleteNegative - deleting after logout should redirect
    Given I have a user in fixture
    And I open the login page
    When I login using fixture user
    And I add a new todo item
    And I logout from the application
    And I try to delete a todo item
    Then I should be redirected to the login page
