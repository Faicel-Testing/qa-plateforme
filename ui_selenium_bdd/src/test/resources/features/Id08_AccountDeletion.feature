@ui @Id08 @profile @security @wip
Feature: Account Deletion

  Scenario: Id08_AccountDeletion - Delete account successfully
    Given I am logged in
    When I am on the Profile page
    And I confirm account deletion
    Then I am redirected to the home page

  Scenario: Id08_AccountDeletion - Cancel account deletion
    Given I am logged in
    When I am on the Profile page
    And I cancel account deletion
    Then the deletion is cancelled
