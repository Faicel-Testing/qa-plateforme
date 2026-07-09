@booking @us-002
Feature: US-002 -- Lister les reservations (GET /booking)
  En tant que client API, je veux recuperer la liste de toutes les reservations
  afin de consulter les IDs disponibles et filtrer par criteres.

  Background:
    Given l'API est disponible

  @smoke @critical @positif @tc-006  # HBAPI-16
  Scenario: TC-006 -- Liste complete sans filtre (GET /booking)
    When j'envoie GET /booking
    Then le status code est 200
    And la reponse contient un champ "bookingid" entier > 0
    And la reponse est une liste de reservations

  @positif @tc-007  # HBAPI-17
  Scenario: TC-007 -- Filtre par firstname (GET /booking?firstname=Jim)
    When j'envoie GET /booking avec le filtre ?firstname=Jim
    Then le status code est 200

  @positif @tc-008  # HBAPI-18
  Scenario: TC-008 -- Filtre par lastname (GET /booking?lastname=Brown)
    When j'envoie GET /booking avec le filtre ?lastname=Brown
    Then le status code est 200

  @positif @tc-009  # HBAPI-19
  Scenario: TC-009 -- Filtre par checkin (GET /booking?checkin=2018-01-01)
    When j'envoie GET /booking avec le filtre ?checkin=2018-01-01
    Then le status code est 200
    And la reponse est une liste de reservations

  @positif @tc-010  # HBAPI-20
  Scenario: TC-010 -- Filtre par checkout (GET /booking?checkout=2019-01-01)
    When j'envoie GET /booking avec le filtre ?checkout=2019-01-01
    Then le status code est 200
    And la reponse est une liste de reservations

  @negatif @tc-011  # HBAPI-21
  Scenario: TC-011 -- Filtre firstname inexistant (GET /booking?firstname=XYZ)
    When j'envoie GET /booking avec ?firstname=XYZ_INEXISTANT
    Then le status code est 200
    And la reponse est une liste vide []

  @securite @tc-012  # HBAPI-22
  Scenario: TC-012 -- SQL injection dans filtre firstname (GET /booking)
    When j'envoie GET /booking avec une injection SQL dans le filtre firstname
    Then le status code est 200
    And la reponse est une liste vide []
    And le payload est encode ou refuse -- aucune execution
