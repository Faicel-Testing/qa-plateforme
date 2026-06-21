@ui @login @Id02 @smoke @regression @critical
Feature: Login

  Scenario: Id02_LoginTest - user can login successfully
    Given I have a user in fixture
    And I open the login page
    When I login using fixture user
    Then I should be logged in
