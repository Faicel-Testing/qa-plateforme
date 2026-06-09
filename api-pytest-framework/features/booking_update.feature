@booking @us-005 @auth
Feature: US-005 -- Mise a jour complete (PUT /booking/{id})
  En tant que client API authentifie, je veux mettre a jour entierement une reservation
  afin de modifier toutes ses informations en une seule requete.

  Background:
    Given l'API est disponible
    And j'ai un token d'authentification valide
    And une reservation existe avec son ID

  @critical @positif @tc-032  # HBAPI-42
  Scenario: TC-032 -- Mise a jour complete avec token valide (PUT /booking/{id})
    When j'envoie PUT /booking/{id} avec tous les champs et mon token (Cookie)
    Then le status code est 200
    And la reponse contient les champs firstname, lastname, totalprice, depositpaid, bookingdates
    And la reponse contient les donnees mises a jour

  @positif @tc-033  # HBAPI-43
  Scenario: TC-033 -- Persistence apres PUT (GET /booking/{id})
    When j'envoie GET /booking/{id}
    Then le status code est 200

  @negatif @tc-034  # HBAPI-44
  Scenario: TC-034 -- PUT sans authentification (PUT /booking/{id})
    When j'envoie PUT /booking/{id} sans header d'authentification
    Then le status code est 403

  @negatif @tc-035  # HBAPI-45
  Scenario: TC-035 -- PUT avec token invalide (PUT /booking/{id})
    When j'envoie PUT /booking/{id} avec un token invalide
    Then le status code est 403

  @negatif @tc-036  # HBAPI-46
  Scenario: TC-036 -- PUT sur ID inexistant (PUT /booking/9999999)
    When j'envoie PUT /booking/9999999 avec mon token
    Then le status code est 404 ou 405

  @negatif @tc-037  # HBAPI-47
  Scenario: TC-037 -- PUT sans champ requis firstname (PUT /booking/{id})
    When j'envoie PUT /booking/{id} sans le champ requis firstname
    Then le status code est 400 ou 403
