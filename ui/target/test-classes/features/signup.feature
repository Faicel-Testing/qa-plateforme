@smoke
Feature: Signup Feature
  Scenario: User should be able to signup
    Given User is in the signup page
    When User fill the "Faysal" and "Testing" and "faical@exemple.com" and "1234AZE" and "1234AZE" in the field
    Then Signup is done correctly

