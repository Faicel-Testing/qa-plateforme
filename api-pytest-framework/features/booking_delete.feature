@booking @us-007 @auth
Feature: US-007 -- Supprimer une reservation (DELETE /booking/{id})
  En tant que client API authentifie, je veux supprimer une reservation
  afin de l'effacer definitivement du systeme.

  Background:
    Given l'API est disponible
    And j'ai un token d'authentification valide

  @critical @positif @tc-045  # HBAPI-55
  Scenario: TC-045 -- DELETE avec token valide (DELETE /booking/{id})
    Given j'ai cree une reservation et recupere son ID
    When j'envoie DELETE /booking/{id} avec mon token (Cookie)
    Then le status code est 201
    And le body de la reponse contient "Created"

  @positif @tc-046  # HBAPI-56
  Scenario: TC-046 -- Verification suppression par GET apres DELETE
    Given j'ai supprime la reservation avec succes
    When j'envoie GET /booking/{id}
    Then le status code est 404
    And la reponse est 404 Not Found

  @negatif @tc-047  # HBAPI-57
  Scenario: TC-047 -- DELETE sans token (DELETE /booking/{id})
    When j'envoie DELETE /booking/{id} sans header d'authentification
    Then le status code est 403

  @negatif @tc-048  # HBAPI-58
  Scenario: TC-048 -- DELETE avec token invalide (DELETE /booking/{id})
    When j'envoie DELETE /booking/{id} avec un token invalide
    Then le status code est 403

  @negatif @tc-049  # HBAPI-59
  Scenario: TC-049 -- DELETE sur ID inexistant (DELETE /booking/9999999)
    When j'envoie DELETE /booking/9999999 avec mon token
    Then le status code est 404 ou 405

  @negatif @tc-050  # HBAPI-60
  Scenario: TC-050 -- Double DELETE sur le meme ID
    When j'envoie DELETE /booking/{id} une seconde fois
    Then le status code est 404 ou 405
