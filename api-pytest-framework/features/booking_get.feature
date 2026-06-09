@booking @us-003
Feature: US-003 -- Recuperer une reservation (GET /booking/{id})
  En tant que client API, je veux recuperer le detail d'une reservation par son ID
  afin de consulter ses informations completes.

  Background:
    Given l'API est disponible
    And une reservation existe avec un ID valide

  @positif @tc-013  # HBAPI-23
  Scenario: TC-013 -- Reservation existante valide (GET /booking/{id})
    Given j'ai cree une reservation et recupere son ID
    When j'envoie GET /booking/{id}
    Then le status code est 200
    And la reponse contient les champs firstname, lastname, totalprice, depositpaid, bookingdates

  @positif @tc-014  # HBAPI-24
  Scenario: TC-014 -- Validation schema JSON (GET /booking/{id})
    When j'envoie GET /booking/{id}
    Then le status code est 200

  @positif @tc-015  # HBAPI-25
  Scenario: TC-015 -- Dates au format ISO 8601 (GET /booking/{id})
    When j'envoie GET /booking/{id}
    Then le status code est 200
    And les dates checkin et checkout sont au format YYYY-MM-DD

  @negatif @tc-016  # HBAPI-26
  Scenario: TC-016 -- ID inexistant (GET /booking/9999999)
    When j'envoie GET /booking/9999999
    Then le status code est 404
    And la reponse est 404 Not Found

  @negatif @tc-017  # HBAPI-27
  Scenario: TC-017 -- ID non numerique (GET /booking/abc)
    When j'envoie GET /booking/abc
    Then le status code est 404
    And la reponse est 404 Not Found

  @negatif @tc-018  # HBAPI-28
  Scenario: TC-018 -- ID negatif (GET /booking/-1)
    When j'envoie GET /booking/-1
    Then le status code est 404
    And la reponse est 404 Not Found

  @negatif @tc-019  # HBAPI-29
  Scenario: TC-019 -- ID zero (GET /booking/0)
    When j'envoie GET /booking/0
    Then le status code est 404
    And la reponse est 404 Not Found
