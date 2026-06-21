@ui @todo @Id03 @negative @regression
Feature: Todo Validation

  Scenario: Id03_TodoNegative - adding an empty todo should fail
    Given I have a user in fixture
    And I open the login page
    When I login using fixture user
    And I try to add an empty todo item
    Then I should see a validation error or the todo should not be added

  Scenario: Id03_TodoNegative - adding todo with only whitespace should fail
    Given I have a user in fixture
    And I open the login page
    When I login using fixture user
    And I try to add a todo with only whitespace
    Then I should see a validation error or the todo should not be added

  Scenario: Id03_TodoNegative - adding todo exceeding character limit should fail
    Given I have a user in fixture
    And I open the login page
    When I login using fixture user
    And I try to add a todo exceeding the character limit
    Then I should see a length validation error

  Scenario: Id03_TodoNegative - adding todo after logout should redirect
    Given I have a user in fixture
    And I open the login page
    When I login using fixture user
    And I logout from the application
    And I try to add a todo item
    Then I should be redirected to the login page
