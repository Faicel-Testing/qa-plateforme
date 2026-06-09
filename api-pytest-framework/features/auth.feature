@auth @us-001
Feature: US-001 -- Authentification (POST /auth)
  En tant que client API, je veux generer un token d'authentification
  afin d'effectuer des operations securisees sur les reservations.

  Background:
    Given l'API est disponible

  @positif @tc-001  # HBAPI-11
  Scenario: TC-001 -- Token valide (POST /auth)
    When j'envoie POST /auth avec username "admin" et password "password123"
    Then le status code est 200
    And la reponse contient un champ "token" non vide
    And la longueur du token est superieure a 10 caracteres

  @negatif @tc-002  # HBAPI-12
  Scenario: TC-002 -- Credentials incorrects (POST /auth)
    When j'envoie POST /auth avec username "wrong" et password "wrong"
    Then le status code est 200
    And la reponse contient {"reason": "Bad credentials"}

  @negatif @tc-003  # HBAPI-13
  Scenario: TC-003 -- Champs username et password manquants (POST /auth)
    When j'envoie POST /auth avec un body vide {}
    Then le status code est 200
    And la reponse contient {"reason": "Bad credentials"}

  @securite @tc-004  # HBAPI-14
  Scenario: TC-004 -- SQL injection dans username (POST /auth)
    When j'envoie POST /auth avec une injection SQL dans username
    Then le status code est 200
    And la reponse contient {"reason": "Bad credentials"}

  @securite @tc-005  # HBAPI-15
  Scenario: TC-005 -- XSS payload dans password (POST /auth)
    When j'envoie POST /auth avec un payload XSS dans password
    Then le status code est 200
    And la reponse contient {"reason": "Bad credentials"}
    And le payload est encode ou refuse -- aucune execution
