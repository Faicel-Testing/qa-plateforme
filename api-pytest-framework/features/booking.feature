@booking @regression
Feature: Booking Management
  Gestion complète des réservations — US-API-002 à US-API-007.

  Background:
    Given the API is available
    And I have a valid auth token

  # US-API-002
  Scenario: Get all bookings
    When I get the list of all bookings
    Then the response status is 200
    And the response contains a list of booking ids

  # US-API-003
  Scenario: Get a booking by id
    Given a booking exists
    When I get the booking by its id
    Then the response status is 200
    And the response contains the booking details

  # US-API-004
  Scenario: Create a booking with valid data
    When I create a booking with valid data
    Then the response status is 200
    And the response contains the new booking id
    And the response contains the booking details

  # US-API-005
  Scenario: Update a booking with valid token
    Given a booking exists
    When I update the booking with valid data
    Then the response status is 200
    And the booking is updated

  Scenario: Update a booking without token
    Given a booking exists
    When I update the booking without token
    Then the response status is 403

  # US-API-006
  Scenario: Patch a booking with valid token
    Given a booking exists
    When I patch the booking firstname
    Then the response status is 200
    And the firstname is updated

  Scenario: Patch a booking without token
    Given a booking exists
    When I patch the booking without token
    Then the response status is 403

  # US-API-007
  Scenario: Delete a booking with valid token
    Given a booking exists
    When I delete the booking with valid token
    Then the response status is 201

  Scenario: Delete a booking without token
    Given a booking exists
    When I delete the booking without token
    Then the response status is 403
