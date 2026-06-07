@ui @signup @Id01 @negative @regression
Feature: Signup Validation

  Scenario: Id01_SignupNegative - signup with mismatched passwords should fail
    Given I open the signup page
    When I enter a valid email and mismatched passwords
    Then I should see a password mismatch error

  Scenario: Id01_SignupNegative - signup with invalid email format should fail
    Given I open the signup page
    When I enter an invalid email format
    Then I should see an invalid email error

  Scenario: Id01_SignupNegative - signup with missing first name should fail
    Given I open the signup page
    When I signup without first name
    Then I should see a required field error for first name

  Scenario: Id01_SignupNegative - signup with missing last name should fail
    Given I open the signup page
    When I signup without last name
    Then I should see a required field error for last name

  Scenario: Id01_SignupNegative - signup with missing email should fail
    Given I open the signup page
    When I signup without email
    Then I should see a required field error for email

  Scenario: Id01_SignupNegative - signup with missing password should fail
    Given I open the signup page
    When I signup without password
    Then I should see a required field error for password

  Scenario: Id01_SignupNegative - signup with weak password should fail
    Given I open the signup page
    When I enter a weak password
    Then I should see a password strength error
