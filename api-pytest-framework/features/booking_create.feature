@booking @us-004
Feature: US-004 -- Creer une reservation (POST /booking)
  En tant que client API, je veux creer une nouvelle reservation
  afin d'enregistrer un sejour hotelier dans le systeme.

  Background:
    Given l'API est disponible

  @smoke @critical @positif @tc-020  # HBAPI-30
  Scenario: TC-020 -- Creation avec tous les champs valides (POST /booking)
    When j'envoie POST /booking
    Then le status code est 200 ou 201
    And la reponse contient un champ "bookingid" entier > 0
    And la reponse contient les champs firstname, lastname, totalprice, depositpaid, bookingdates

  @positif @tc-021  # HBAPI-31
  Scenario: TC-021 -- Creation sans champ optionnel additionalneeds (POST /booking)
    When j'envoie POST /booking sans le champ optionnel additionalneeds
    Then le status code est 200 ou 201
    And la reponse contient un champ "bookingid" entier > 0

  @limite @tc-022  # HBAPI-32
  Scenario: TC-022 -- Dates checkin egale checkout (POST /booking)
    When j'envoie POST /booking avec checkin = checkout = 2026-07-01
    Then le status code est 200 ou 201

  @negatif @tc-023  # HBAPI-33
  Scenario: TC-023 -- Champ firstname manquant (POST /booking)
    When j'envoie POST /booking sans le champ requis firstname
    Then le status code est 400 ou 500

  @negatif @tc-024  # HBAPI-34
  Scenario: TC-024 -- Champ lastname manquant (POST /booking)
    When j'envoie POST /booking sans le champ requis lastname
    Then le status code est 400 ou 500

  @negatif @tc-025  # HBAPI-35
  Scenario: TC-025 -- Champ totalprice manquant (POST /booking)
    When j'envoie POST /booking sans le champ requis totalprice
    Then le status code est 400 ou 500

  @negatif @tc-026  # HBAPI-36
  Scenario: TC-026 -- Champ depositpaid manquant (POST /booking)
    When j'envoie POST /booking sans le champ requis depositpaid
    Then le status code est 400 ou 500

  @negatif @tc-027  # HBAPI-37
  Scenario: TC-027 -- Champ bookingdates manquant (POST /booking)
    When j'envoie POST /booking sans le champ requis bookingdates
    Then le status code est 400 ou 500

  @negatif @tc-028  # HBAPI-38
  Scenario: TC-028 -- totalprice negatif (POST /booking)
    When j'envoie POST /booking avec totalprice = -100
    Then le status code est 400 ou 500

  @negatif @tc-029  # HBAPI-39
  Scenario: TC-029 -- checkin posterieur a checkout (POST /booking)
    When j'envoie POST /booking avec checkin posterieur a checkout
    Then le status code est 400

  @negatif @tc-030  # HBAPI-40
  Scenario: TC-030 -- Body vide (POST /booking)
    When j'envoie POST /booking avec un body vide {}
    Then le status code est 400 ou 500

  @securite @tc-031  # HBAPI-41
  Scenario: TC-031 -- XSS payload dans firstname (POST /booking)
    When j'envoie POST /booking avec un payload XSS dans firstname
    Then le status code est 400 ou 200
    And le payload est encode ou refuse -- aucune execution
