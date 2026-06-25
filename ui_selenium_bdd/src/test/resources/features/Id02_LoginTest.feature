@ui @login @Id02 @smoke @regression @critical
Feature: Login

  Scenario: Id02_LoginTest - user can login successfully
    Given I have a user in fixture
    And I open the login page
    When I login using fixture user
    Then I should be logged in

  Scenario: Id02_LoginTest - user can logout after login
    Given I have a user in fixture
    And I open the login page
    When I login using fixture user
    And I logout from the application
    Then I should be redirected to the login page

  Scenario: Id02_LoginTest - user can add a todo after login
    Given I have a user in fixture
    And I open the login page
    When I login using fixture user
    And I add a new todo item
    Then I should see the new todo item in the list
