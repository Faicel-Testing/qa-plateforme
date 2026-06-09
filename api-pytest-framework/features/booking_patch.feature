@booking @us-006 @auth
Feature: US-006 -- Mise a jour partielle (PATCH /booking/{id})
  En tant que client API authentifie, je veux mettre a jour partiellement une reservation
  afin de modifier uniquement les champs necessaires.

  Background:
    Given l'API est disponible
    And j'ai un token d'authentification valide
    And une reservation existe avec son ID

  @critical @positif @tc-038  # HBAPI-48
  Scenario: TC-038 -- PATCH firstname uniquement (PATCH /booking/{id})
    When j'envoie PATCH /booking/{id} avec {"firstname": "UpdatedName"}
    Then le status code est 200

  @positif @tc-039  # HBAPI-49
  Scenario: TC-039 -- PATCH totalprice uniquement (PATCH /booking/{id})
    When j'envoie PATCH /booking/{id} avec {"totalprice": 999}
    Then le status code est 200

  @positif @tc-040  # HBAPI-50
  Scenario: TC-040 -- PATCH lastname et totalprice (PATCH /booking/{id})
    When j'envoie PATCH /booking/{id} avec {"lastname": "Updated", "totalprice": 500}
    Then le status code est 200
    And la reponse contient le nouveau lastname et totalprice

  @negatif @tc-041  # HBAPI-51
  Scenario: TC-041 -- PATCH sans token (PATCH /booking/{id})
    When j'envoie PATCH /booking/{id} sans header d'authentification
    Then le status code est 403

  @negatif @tc-042  # HBAPI-52
  Scenario: TC-042 -- PATCH avec token invalide (PATCH /booking/{id})
    When j'envoie PATCH /booking/{id} avec un token invalide
    Then le status code est 403

  @negatif @tc-043  # HBAPI-53
  Scenario: TC-043 -- PATCH sur ID inexistant (PATCH /booking/9999999)
    When j'envoie PATCH /booking/9999999 avec mon token
    Then le status code est 404 ou 405

  @limite @tc-044  # HBAPI-54
  Scenario: TC-044 -- PATCH avec body vide (PATCH /booking/{id})
    When j'envoie PATCH /booking/{id} avec un body vide {}
    Then le status code est 200
    And la reservation n'a pas ete modifiee
