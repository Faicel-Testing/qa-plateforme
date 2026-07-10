@ui @login @Id05 @negative @regression
Feature: Login Validation

  Scenario: Id05_LoginNegativeTest - invalid credentials show an error
    Given I open the login page
    When I login with invalid credentials
    Then I should see a login error message

  Scenario: Id05_LoginNegative - login with invalid email format should fail
    Given I open the login page
    When I login with invalid email format
    Then I should see an invalid email error

  Scenario: Id05_LoginNegative - login with wrong password should fail
    Given I open the login page
    When I login with correct email and wrong password
    Then I should see an authentication error message

  Scenario: Id05_LoginNegative - login with non-existent email should fail
    Given I open the login page
    When I login with non-existent email
    Then I should see a user not found error

  Scenario: Id05_LoginNegative - login with empty email should fail
    Given I open the login page
    When I login with empty email
    Then I should see a required field error for email

  Scenario: Id05_LoginNegative - login with empty password should fail
    Given I open the login page
    When I login with empty password
    Then I should see a required field error for password

  Scenario: Id05_LoginNegative - login with both fields empty should fail
    Given I open the login page
    When I login with both fields empty
    Then I should see required field errors
