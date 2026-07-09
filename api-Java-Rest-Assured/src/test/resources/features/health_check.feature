@health @us-008 @smoke
Feature: US-008 -- Health Check (GET /ping)
  En tant que client API, je veux verifier la disponibilite de l'API
  afin de m'assurer qu'elle est operationnelle avant de lancer les tests.

  Background:
    Given l'API est disponible

  @smoke @critical @positif @tc-051  # HBAPI-61
  Scenario: TC-051 -- Health check standard (GET /ping)
    When j'envoie GET /ping
    Then le status code est 201
    And le body de la reponse contient "Created"
