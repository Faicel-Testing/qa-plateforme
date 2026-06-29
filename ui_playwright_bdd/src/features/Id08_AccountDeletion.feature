@ui @id08 @profile @security
Feature: Account Deletion

  Background:
    Given I have a user in fixture
    And I open the login page
    When I login using fixture user
    Then I should be logged in
    And I navigate to the profile page

  Scenario: Id08_AccountDeletion - delete account successfully
    When I confirm account deletion
    Then I should be redirected to the home page

  Scenario: Id08_AccountDeletion - cancel account deletion
    When I cancel account deletion
    Then the deletion should be cancelled and I remain on the profile page
